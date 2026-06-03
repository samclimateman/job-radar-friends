use std::sync::{Arc, Mutex};
use tauri::{WebviewUrl, WebviewWindowBuilder};

const PORT: u16 = 8766;

fn is_port_open(port: u16) -> bool {
    std::net::TcpStream::connect(("127.0.0.1", port)).is_ok()
}

fn is_job_radar_server(port: u16) -> bool {
    use std::io::{Read, Write};

    let Ok(mut stream) = std::net::TcpStream::connect(("127.0.0.1", port)) else {
        return false;
    };
    let _ = stream.set_read_timeout(Some(std::time::Duration::from_millis(800)));
    let _ = stream.set_write_timeout(Some(std::time::Duration::from_millis(800)));

    if stream
        .write_all(b"GET /api/health HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n")
        .is_err()
    {
        return false;
    }

    let mut response = String::new();
    if stream.read_to_string(&mut response).is_err() {
        return false;
    }

    response.contains("\"app\":\"job-radar\"") || response.contains("\"app\": \"job-radar\"")
}

/// Resolve the bundled sidecar binary.
///
/// Search order:
/// 1. Next to the Tauri binary (Contents/MacOS/) — packaged .app
/// 2. Contents/Resources/job-radar-server/ — if copied there post-build
/// 3. dist/job-radar-server/ relative to repo root — dev PyInstaller build
fn find_sidecar() -> Option<std::path::PathBuf> {
    let exe = std::env::current_exe().ok()?;
    let exe = exe.canonicalize().unwrap_or(exe);
    let macos_dir = exe.parent()?;

    // 1. Packaged: next to the Tauri binary
    let next_to_bin = macos_dir.join("job-radar-server");
    if next_to_bin.exists() {
        return Some(next_to_bin);
    }

    // 2. Packaged: in Contents/Resources/job-radar-server/
    let resources = macos_dir
        .parent()  // Contents/
        .map(|p| p.join("Resources/job-radar-server/job-radar-server"));
    if let Some(p) = resources {
        if p.exists() {
            return Some(p);
        }
    }

    // 3. Dev: PyInstaller dist relative to repo root (walk up to pyproject.toml)
    let mut p = exe.as_path();
    for _ in 0..10 {
        if let Some(parent) = p.parent() {
            if parent.join("pyproject.toml").exists() {
                let candidate = parent.join("dist/job-radar-server/job-radar-server");
                if candidate.exists() {
                    return Some(candidate);
                }
            }
            p = parent;
        }
    }

    None
}

/// Start the bundled job-radar server sidecar.
///
/// The sidecar is a PyInstaller-compiled `job-radar start --no-open` binary.
/// Returns the child process handle for clean shutdown, plus any warning messages.
fn start_server() -> (Option<std::process::Child>, Vec<String>) {
    if is_job_radar_server(PORT) {
        // Already running (e.g. dev mode with server started separately)
        return (None, vec![]);
    }

    let log_dir = dirs_path();
    let _ = std::fs::create_dir_all(&log_dir);
    let log_path = log_dir.join("startup.log");

    if is_port_open(PORT) {
        let msg = format!(
            "Port {} is already in use by another local process. Close that process and relaunch Job Radar.",
            PORT
        );
        let _ = std::fs::write(&log_path, format!("[ERROR] {}\n", msg));
        return (None, vec![msg]);
    }

    let Some(sidecar) = find_sidecar() else {
        let msg = "job-radar server binary not found. Run `make build-sidecar` to build it.".to_string();
        let _ = std::fs::write(&log_path, format!("[ERROR] {}\n", msg));
        return (None, vec![msg]);
    };

    let child = std::process::Command::new(&sidecar)
        .args(["start", "--no-open", "--port", &PORT.to_string()])
        .stdout(std::process::Stdio::null())
        .stderr(std::process::Stdio::null())
        .spawn()
        .ok();

    if child.is_none() {
        let msg = format!("Failed to start Job Radar server from: {}", sidecar.display());
        let _ = std::fs::write(&log_path, format!("[ERROR] {}\n", msg));
        return (None, vec![msg]);
    }

    // Wait up to 10s for the server to bind
    for _ in 0..20 {
        std::thread::sleep(std::time::Duration::from_millis(500));
        if is_job_radar_server(PORT) {
            break;
        }
    }

    (child, vec![])
}

/// Returns the Job Radar data directory (~/.job-radar)
fn dirs_path() -> std::path::PathBuf {
    let home = std::env::var("HOME").unwrap_or_else(|_| "/tmp".to_string());
    std::path::PathBuf::from(home).join(".job-radar")
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let server_proc: Arc<Mutex<Option<std::process::Child>>> = Arc::new(Mutex::new(None));
    let server_proc_setup = server_proc.clone();

    tauri::Builder::default()
        .setup(move |app| {
            let (child, warnings) = start_server();
            *server_proc_setup.lock().unwrap() = child;

            let url = if is_job_radar_server(PORT) {
                WebviewUrl::External(
                    format!("http://127.0.0.1:{}/", PORT)
                        .parse()
                        .expect("invalid server URL"),
                )
            } else {
                WebviewUrl::App("index.html".into())
            };

            let win = WebviewWindowBuilder::new(app, "main", url)
                .title("Job Radar")
                .inner_size(1400.0, 900.0)
                .min_inner_size(880.0, 600.0)
                .resizable(true)
                .build()?;

            if !warnings.is_empty() {
                let msg = warnings.join(" ");
                let escaped = msg.replace('\\', "\\\\").replace('"', "\\\"").replace('\n', " ");
                let _ = win.eval(&format!(
                    r#"window.addEventListener('load', function() {{
                        var b = document.createElement('div');
                        b.style.cssText = 'position:fixed;top:0;left:0;right:0;z-index:9999;background:#fff0c2;color:#7a4b00;padding:8px 16px;font:13px/1.4 system-ui,sans-serif;border-bottom:1px solid #e8c96a';
                        b.textContent = '{escaped}';
                        document.body.prepend(b);
                    }}, {{once:true}});"#
                ));
            }

            Ok(())
        })
        .on_window_event(move |_window, event| {
            if let tauri::WindowEvent::Destroyed = event {
                if let Ok(mut guard) = server_proc.lock() {
                    if let Some(ref mut child) = *guard {
                        let _ = child.kill();
                        let _ = child.wait();
                    }
                }
            }
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
