use std::sync::{Arc, Mutex};
use tauri::{WebviewUrl, WebviewWindowBuilder};

const PORT: u16 = 8766;
type ServerProcess = Arc<Mutex<Option<std::process::Child>>>;

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

/// Sidecar binary filename: PyInstaller appends .exe on Windows.
fn sidecar_name() -> String {
    format!("job-radar-server{}", std::env::consts::EXE_SUFFIX)
}

/// Resolve the bundled sidecar binary.
///
/// Search order:
/// 1. Next to the Tauri binary — packaged .app (macOS) or install dir (Windows)
/// 2. job-radar-server/ directory next to the binary — Windows NSIS resources
/// 3. Contents/Resources/job-radar-server/ — macOS .app, copied post-build
/// 4. dist/job-radar-server/ relative to repo root — dev PyInstaller build
fn find_sidecar() -> Option<std::path::PathBuf> {
    let exe = std::env::current_exe().ok()?;
    let exe = exe.canonicalize().unwrap_or(exe);
    let bin_dir = exe.parent()?;
    let name = sidecar_name();

    // 1. Packaged: next to the Tauri binary
    let next_to_bin = bin_dir.join(&name);
    if next_to_bin.exists() {
        return Some(next_to_bin);
    }

    // 2. Packaged: job-radar-server/ resource dir next to the binary (Windows)
    let resource_sibling = bin_dir.join("job-radar-server").join(&name);
    if resource_sibling.exists() {
        return Some(resource_sibling);
    }

    // 3. Packaged: in Contents/Resources/job-radar-server/ (macOS)
    let resources = bin_dir
        .parent()  // Contents/
        .map(|p| p.join("Resources/job-radar-server").join(&name));
    if let Some(p) = resources {
        if p.exists() {
            return Some(p);
        }
    }

    // 4. Dev: PyInstaller dist relative to repo root (walk up to pyproject.toml)
    let mut p = exe.as_path();
    for _ in 0..10 {
        if let Some(parent) = p.parent() {
            if parent.join("pyproject.toml").exists() {
                let candidate = parent.join("dist/job-radar-server").join(&name);
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

    let mut command = std::process::Command::new(&sidecar);
    command
        .args(["start", "--no-open", "--port", &PORT.to_string()])
        .stdout(std::process::Stdio::null())
        .stderr(std::process::Stdio::null());
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        const CREATE_NO_WINDOW: u32 = 0x0800_0000;
        command.creation_flags(CREATE_NO_WINDOW);
    }
    let child = command.spawn().ok();

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

fn stop_server(server_proc: &ServerProcess) {
    if let Ok(mut guard) = server_proc.lock() {
        if let Some(mut child) = guard.take() {
            let _ = child.kill();
            let _ = child.wait();
        }
    }
}

/// Returns the Job Radar data directory (~/.job-radar)
fn dirs_path() -> std::path::PathBuf {
    let home = std::env::var("HOME")
        .or_else(|_| std::env::var("USERPROFILE"))
        .unwrap_or_else(|_| ".".to_string());
    std::path::PathBuf::from(home).join(".job-radar")
}

#[tauri::command]
fn open_external(url: String) {
    // Only http(s) URLs may leave the app; everything else is dropped.
    if !(url.starts_with("https://") || url.starts_with("http://")) {
        return;
    }
    #[cfg(target_os = "macos")]
    let _ = std::process::Command::new("open").arg(&url).spawn();
    #[cfg(target_os = "windows")]
    {
        use std::os::windows::process::CommandExt;
        const CREATE_NO_WINDOW: u32 = 0x0800_0000;
        // `start` is a cmd builtin; the empty string is the window title slot.
        let _ = std::process::Command::new("cmd")
            .args(["/C", "start", "", &url])
            .creation_flags(CREATE_NO_WINDOW)
            .spawn();
    }
    #[cfg(all(unix, not(target_os = "macos")))]
    let _ = std::process::Command::new("xdg-open").arg(&url).spawn();
}

fn encode_query_component(value: &str) -> String {
    value
        .bytes()
        .flat_map(|byte| match byte {
            b'A'..=b'Z' | b'a'..=b'z' | b'0'..=b'9' | b'-' | b'_' | b'.' | b'~' => {
                vec![byte as char]
            }
            b' ' => vec!['+'],
            _ => {
                let encoded = format!("%{:02X}", byte);
                encoded.chars().collect()
            }
        })
        .collect()
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let server_proc: ServerProcess = Arc::new(Mutex::new(None));
    let server_proc_setup = server_proc.clone();
    let server_proc_window = server_proc.clone();
    let server_proc_exit = server_proc.clone();

    let app = tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![open_external])
        .setup(move |app| {
            let (child, warnings) = start_server();
            *server_proc_setup.lock().unwrap() = child;

            let url = if is_job_radar_server(PORT) {
                WebviewUrl::External(
                    format!("http://127.0.0.1:{}/", PORT)
                        .parse()
                        .expect("invalid server URL"),
                )
            } else if !warnings.is_empty() {
                let msg = encode_query_component(&warnings.join(" "));
                WebviewUrl::App(format!("index.html?startup_warning={}", msg).into())
            } else {
                WebviewUrl::App("index.html".into())
            };

            WebviewWindowBuilder::new(app, "main", url)
                .title("Job Radar")
                .inner_size(1400.0, 900.0)
                .min_inner_size(880.0, 600.0)
                .resizable(true)
                .build()?;

            Ok(())
        })
        .on_window_event(move |_window, event| {
            if let tauri::WindowEvent::Destroyed = event {
                stop_server(&server_proc_window);
            }
        })
        .build(tauri::generate_context!())
        .expect("error while building tauri application");

    app.run(move |_app_handle, event| {
        if matches!(
            event,
            tauri::RunEvent::ExitRequested { .. } | tauri::RunEvent::Exit
        ) {
            stop_server(&server_proc_exit);
        }
    });
}
