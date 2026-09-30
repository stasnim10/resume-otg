# Resume OTG

Resume OTG is a guided resume optimization and job application workflow app built for job seekers who want more control, more clarity, and less chaos.

The current product is a hosted Streamlit application with:
- guided onboarding
- career profile creation and editing
- AI-assisted resume optimization
- review-first draft flow
- Supabase-backed authentication and user data
- a Job Tracker for managing applications, notes, and optimization history

## Current Product

The active application lives in:
- [resume_optimizer_local/streamlit_app.py](resume_optimizer_local/streamlit_app.py)

This is the version that reflects the current launch direction.

## Core Capabilities

- Guided onboarding for first-time users
- Career Profile storage and reuse
- Resume optimization with explainable review flow
- Manual and AI-assisted job targeting flows
- Job Tracker with statuses, notes, and optimization history
- Supabase-backed auth, settings, and user-scoped data

## Tech Stack

- `Streamlit` for the application UI
- `Supabase` for authentication and database storage
- `Python` for product logic and orchestration
- `Next.js` in [`website/`](website/) for the marketing site

## Main App Setup

```bash
cd resume_optimizer_local
pip install -r requirements.txt
python3 -m streamlit run streamlit_app.py
```

## Connect AI Apps with MCP (Local)

Use Python 3.10 or newer. Open **Settings → MCP / AI Apps** in the local app, save a Word resume once,
install `resume_optimizer_local/requirements-mcp.txt`, and copy the generated
MCP configuration into a client that supports local stdio servers. Restart
the client, then paste: “Use Resume OTG to tailor my saved resume to this job
and export the Word file: [job URL or description].”

The connected AI uses `prepare_resume_for_job` to read the source and targeting
instructions, then `export_tailored_resume` to apply exact paragraph replacements.
Exports preserve existing paragraph formatting, leave the original unchanged,
and are available as binary MCP resources and in the app’s MCP settings download
section. The AI client receives resume content; review the final claims yourself.
No additional AI provider key is needed. Sites requiring login or JavaScript may
require a pasted description. Only body paragraphs are editable through this flow.

This local connection uses the local saved resume. A separate OAuth-protected
remote connector for hosted accounts is prepared for `mcp.resumeotg.app`, with
private Supabase resume storage and expiring Word download links. Deployment,
DNS and OAuth configuration are still required; the URL is not live yet.
See [remote connector deployment](docs/MCP_REMOTE_DEPLOYMENT.md) for setup and
the checks required before enabling the hosted connection link.

## Required Hosted Secrets

For hosted deployment, configure these secrets:

```toml
SUPABASE_URL = "https://YOUR_PROJECT.supabase.co"
SUPABASE_ANON_KEY = "YOUR_SUPABASE_ANON_KEY"
HOSTED_WEB = "true"
SUPABASE_OAUTH_REDIRECT_TO = "https://your-app-url.streamlit.app"
```

Also enable the Google provider in Supabase Auth and add the same redirect URL to
both Supabase Auth redirect settings and your Google OAuth client configuration.

## Repository Structure

```text
resume_optimizer_local/    Streamlit product app
website/                   Marketing website
supabase/migrations/       Database schema and migration files
assets/                    Brand and marketing assets
docs/                      Internal product and implementation notes
```

## Important Notes

- The legacy folders in this repository may still contain older prototype work.
- The launch-focused app is the Streamlit product in `resume_optimizer_local/`.
- Supabase migrations live in `supabase/migrations/`.

## Ownership

This repository is proprietary.

See [LICENSE](LICENSE) for usage restrictions and copyright terms.
