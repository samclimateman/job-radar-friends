.PHONY: dev build-sidecar build-app clean

# Run the Python server directly (no Tauri)
dev:
	.venv/bin/job-radar start

# Compile the Python server into a standalone binary via PyInstaller
build-sidecar:
	.venv/bin/pip install pyinstaller
	.venv/bin/pyinstaller job-radar-server.spec --noconfirm
	@echo "Sidecar built: dist/job-radar-server/job-radar-server"

# Build the full Tauri .app (requires build-sidecar first)
# After Tauri builds the .app, copy the PyInstaller sidecar into Resources/
build-app: build-sidecar
	export PATH="$$HOME/.cargo/bin:$$PATH" && cargo tauri build
	@APP="src-tauri/target/release/bundle/macos/Job Radar.app/Contents/Resources" && \
	 mkdir -p "$$APP/job-radar-server" && \
	 cp -R dist/job-radar-server/ "$$APP/job-radar-server/" && \
	 echo "Sidecar copied into .app bundle"
	@echo "App built: src-tauri/target/release/bundle/macos/Job Radar.app"

# Build Tauri in dev mode (hot-reload, opens window immediately)
tauri-dev:
	export PATH="$$HOME/.cargo/bin:$$PATH" && cargo tauri dev

clean:
	rm -rf dist build __pycache__ *.egg-info
