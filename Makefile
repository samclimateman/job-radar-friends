.PHONY: dev dev-api dev-ui build-sidecar build-app sign clean test

# Run the old HTML server (admin/settings pages)
dev:
	.venv/bin/job-radar start

# Run FastAPI backend for the React dashboard
dev-api:
	.venv/bin/uvicorn job_radar.api.main:app --port 8766 --reload

# Run React frontend dev server (proxies /api → :8766)
dev-ui:
	cd frontend && npm run dev

# Build React frontend for production
build-frontend:
	cd frontend && npm run build

test:
	.venv/bin/pytest

# Compile the Python server into a standalone binary via PyInstaller
build-sidecar:
	.venv/bin/pip install pyinstaller
	.venv/bin/pyinstaller job-radar-server.spec --noconfirm
	@echo "Sidecar built: dist/job-radar-server/job-radar-server"

# Build the full Tauri .app, copy the sidecar in, then ad-hoc sign
build-app: build-sidecar
	export PATH="$$HOME/.cargo/bin:$$PATH" && cargo tauri build
	@APP="src-tauri/target/release/bundle/macos/Job Radar.app/Contents/Resources" && \
	 mkdir -p "$$APP/job-radar-server" && \
	 cp -R dist/job-radar-server/ "$$APP/job-radar-server/" && \
	 echo "Sidecar copied into .app bundle"
	$(MAKE) sign
	@echo "Done: src-tauri/target/release/bundle/macos/Job Radar.app"

# Ad-hoc sign — no Apple account needed, right-click → Open works reliably
sign:
	@APP="src-tauri/target/release/bundle/macos/Job Radar.app" && \
	 codesign --deep --force --sign - "$$APP/Contents/Resources/job-radar-server/job-radar-server" && \
	 codesign --deep --force --sign - "$$APP" && \
	 echo "Ad-hoc signed. Friends: right-click → Open on first launch."

# Build Tauri in dev mode (opens window, no sidecar needed)
tauri-dev:
	export PATH="$$HOME/.cargo/bin:$$PATH" && cargo tauri dev

clean:
	rm -rf dist build __pycache__ *.egg-info
