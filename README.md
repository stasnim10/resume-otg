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

## Required Hosted Secrets

For hosted deployment, configure these secrets:

```toml
SUPABASE_URL = "https://YOUR_PROJECT.supabase.co"
SUPABASE_ANON_KEY = "YOUR_SUPABASE_ANON_KEY"
HOSTED_WEB = "true"
```

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
