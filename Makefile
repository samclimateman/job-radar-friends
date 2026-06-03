.PHONY: dev dev-api dev-ui build-sidecar build-app build-dmg sign clean test public-check

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

public-check:
	.venv/bin/python scripts/public_check.py

# Compile the Python server into a standalone binary via PyInstaller
build-sidecar:
	.venv/bin/pip install pyinstaller
	.venv/bin/pyinstaller job-radar-server.spec --noconfirm
	@echo "Sidecar built: dist/job-radar-server/job-radar-server"

# Build the full Tauri .app, copy the sidecar in, then ad-hoc sign
build-app: build-frontend build-sidecar
	export PATH="$$HOME/.cargo/bin:$$PATH" && cargo tauri build --bundles app
	@APP="src-tauri/target/release/bundle/macos/Job Radar.app/Contents/Resources" && \
	 mkdir -p "$$APP/job-radar-server" && \
	 cp -R dist/job-radar-server/ "$$APP/job-radar-server/" && \
	 echo "Sidecar copied into .app bundle"
	$(MAKE) sign
	@echo "Done: src-tauri/target/release/bundle/macos/Job Radar.app"

build-dmg: build-app
	@DMG_ROOT="dist/dmg-root" && \
	 DMG_PATH="dist/Job Radar.dmg" && \
	 rm -rf "$$DMG_ROOT" "$$DMG_PATH" && \
	 mkdir -p "$$DMG_ROOT" && \
	 cp -R "src-tauri/target/release/bundle/macos/Job Radar.app" "$$DMG_ROOT/" && \
	 ln -s /Applications "$$DMG_ROOT/Applications" && \
	 hdiutil create -volname "Job Radar" -srcfolder "$$DMG_ROOT" -ov -format UDZO "$$DMG_PATH" && \
	 echo "Done: $$DMG_PATH"

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
