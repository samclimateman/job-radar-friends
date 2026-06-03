# Job Radar Frontend

React/Tailwind dashboard for the Job Radar public beta desktop app.

The production frontend is built into `frontend/dist` and served by the bundled Python/FastAPI sidecar inside the Tauri app. During development, Vite proxies API requests to the local backend on `127.0.0.1:8766`.

## Commands

From the repo root:

```bash
make dev-api
make dev-ui
make build-frontend
make public-check
```

From this directory:

```bash
npm run dev
npm run build
```

## Versioning

Do not manually edit `CURRENT_VERSION` in `src/App.tsx`.

Use the root release helpers instead:

```bash
make version-bump-patch
make version-check
```

The version checker keeps the React update banner, package metadata, Python metadata, and Tauri/Rust metadata synchronized.
