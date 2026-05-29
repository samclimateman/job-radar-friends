# Job Radar Friend Install

This is the current practical install path for a tech-comfortable friend on macOS.

## Install

### Easiest macOS path

Double-click:

```text
Install Job Radar.command
```

This creates the local Python environment, installs dependencies, creates
`~/Applications/Job Radar.app`, and opens the app. After that, launch it from
Finder, the Dock, or:

```text
Open Job Radar.command
```

If the app does not open, check:

```text
~/.job-radar/launcher.log
```

### Terminal path

```bash
git clone <repo-url> job-radar
cd job-radar
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/job-radar setup
.venv/bin/job-radar install-app
```

Then open `~/Applications/Job Radar.app` once and choose **Keep in Dock**.

## First Run

1. Paste 10-50 career-page URLs.
2. Add your search strategy:
   - target locations
   - industries
   - role types
   - seniority
   - positive keywords
   - negative keywords
   - dealbreakers
3. Optional: configure AI provider links in **AI Setup**.
4. Click **Refresh Now**.

## AI Setup

AI is optional for the current core loop. Strategy scoring is deterministic.

Provider setup links are shown in the app:

- OpenAI API keys: `https://platform.openai.com/api-keys`
- Claude / Anthropic API keys: `https://console.anthropic.com/settings/keys`
- Ollama local install: `https://ollama.com/download`

Keys are saved in `~/.job-radar/.env`. Later versions should use macOS Keychain.

## Data

Local data lives in:

```text
~/.job-radar/
```

Back up the SQLite database with:

```bash
job-radar backup
```
