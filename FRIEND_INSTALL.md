# Job Radar Friend Install

This is the current practical install path for a small macOS beta.

## Install

### GitHub Release DMG

1. Download the latest beta DMG:
   `https://github.com/samclimateman/job-radar-friends/releases`
2. Open `Job.Radar.dmg`.
3. Drag **Job Radar.app** to **Applications**.
4. Open **Job Radar**.

This beta is not Apple Developer ID notarized yet. If macOS blocks the first launch, right-click **Job Radar.app**, choose **Open**, then confirm.

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

1. Complete the first-run onboarding.
2. Add 3-10 organization career pages.
3. Prefer real job board URLs such as Greenhouse, Lever, Ashby, Workable, SmartRecruiters, Personio, or RSS feeds.
4. If a source is flagged **Needs manual check**, open it, verify it is a real vacancies page, then mark it checked in Source Health.
5. Start the first scan and review Jobs and Source Health.

## AI Setup

AI is optional for the current core loop. Strategy scoring is deterministic.

Provider setup links are shown in the app:

- OpenAI API keys: `https://platform.openai.com/api-keys`
- Claude / Anthropic API keys: `https://console.anthropic.com/settings/keys`
- Ollama local install: `https://ollama.com/download`

Keys are saved in `~/.job-radar/.env` only if you add them from the legacy settings page. The React onboarding flow does not require API keys.

## Data

Local data lives in:

```text
~/.job-radar/
```

Back up the SQLite database with:

```bash
job-radar backup
```
