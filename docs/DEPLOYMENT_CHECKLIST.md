# Deployment Checklist & Infrastructure Plan

## Hosting Choice: Render vs. Railway

**CHOOSE ONE:**

### Option A: Render (Recommended)
- Free tier: Yes (good for MVP launch)
- Includes PostgreSQL: Yes (perfect for us)
- Simplicity: 8/10
- Setup time: 30 min
- Cost: $0 first year, then $7-20/month if scaling

### Option B: Railway
- Free tier: Limited (need to verify)
- Includes PostgreSQL: Yes
- Simplicity: 7/10
- Setup time: 20 min
- Cost: $5-10/month

**Decision:** `[x] Render  [ ] Railway`  
**Why:** Render is the better MVP default because it gives us a simpler hosted path for both the app and PostgreSQL in one place, while keeping early costs low. It also matches the current need for reliability and straightforward setup more than aggressive flexibility.

---

## Database Setup

### Current State:
- SQLite at: `resume_optimizer_local/career_profile.db`
- Single-user (no isolation)
- Local file only

### New State (After Deployment):
- PostgreSQL on Render
- Multi-tenant (user isolation)
- Cloud-hosted

### Migration Plan:
- [ ] Export SQLite data if any seed or demo data is worth preserving
- [ ] Create PostgreSQL schema matching current SQLite tables and constraints
- [ ] Replace any SQLite-only SQL or connection logic
- [ ] Test PostgreSQL connection locally with environment variables
- [ ] Verify all read/write queries work with PostgreSQL
- [ ] Add user isolation to every profile, optimization, and history query

**Status:** `[x] Planned  [ ] In Progress  [ ] Done`

---

## Authentication System

### Current State:
- No production-ready authentication
- Likely relies on local or implicit user context rather than secure login
- User isolation is not yet guaranteed

### New State:
- Supabase Auth for signup and login
- Users create account with email + password
- Each user can only see their own data
- Session tokens manage persistence

### What You Need:
- [ ] Create Supabase project on free tier
- [ ] Design signup, login, logout, and password reset flow
- [ ] Add `users` ownership model to app data
- [ ] Filter every database query by authenticated `user_id`
- [ ] Define how Streamlit stores and refreshes session state
- [ ] Add protected-route behavior for logged-out users

**Status:** `[x] Planned  [ ] In Progress  [ ] Done`

---

## Deployment Configuration

### `requirements.txt`
- [ ] All dependencies pinned to specific versions
- Example:

```txt
streamlit==1.44.1
psycopg2-binary==2.9.10
sqlalchemy==2.0.40
python-dotenv==1.0.1
```

### Environment Variables
- [ ] `DATABASE_URL`
- [ ] `SUPABASE_URL`
- [ ] `SUPABASE_ANON_KEY`
- [ ] `SUPABASE_SERVICE_ROLE_KEY` if server-side flows require it
- [ ] `OPENAI_API_KEY` if optimization logic depends on it
- [ ] `APP_ENV=production`

### App Start Command
- [ ] Confirm production start command for hosted Streamlit app
- Candidate:

```bash
streamlit run streamlit_app.py --server.port=$PORT --server.address=0.0.0.0
```

### Config Files
- [ ] Add or verify `requirements.txt`
- [ ] Add `.streamlit/config.toml` for production-safe settings if needed
- [ ] Add `.env.example` documenting required secrets
- [ ] Add health-check notes for startup debugging

**Status:** `[x] Planned  [ ] In Progress  [ ] Done`

---

## Testing Before Deployment

- [ ] Run test suite locally
- [ ] Verify app launches locally with production-like environment variables
- [ ] Test login and logout flow
- [ ] Test new-user signup flow
- [ ] Test one full resume optimization journey end to end
- [ ] Test database writes and reads on PostgreSQL
- [ ] Confirm no user can access another user's data
- [ ] Capture before and after screenshots for major flows

**Status:** `[x] Planned  [ ] In Progress  [ ] Done`

---

## Logging & Monitoring

### Logging to Add
- [ ] File uploaded
- [ ] Profile import started
- [ ] Profile items detected
- [ ] Fit score calculated
- [ ] Optimization started
- [ ] Optimization completed
- [ ] Download triggered
- [ ] Login success/failure
- [ ] Database connection error

### Monitoring Plan
- [ ] Use platform logs in Render during MVP phase
- [ ] Track critical errors manually after each deployment
- [ ] Review user-reported failures within 24 hours
- [ ] Add lightweight analytics after core flows are stable

**Status:** `[x] Planned  [ ] In Progress  [ ] Done`

---

## Security & User Isolation

- [ ] Do not commit secrets to the repo
- [ ] Confirm all user data is scoped by authenticated `user_id`
- [ ] Validate file uploads safely
- [ ] Limit database permissions to app-required access only
- [ ] Sanitize logs so resumes and personal data are not dumped in plaintext
- [ ] Review password and session handling through Supabase defaults

**Status:** `[x] Planned  [ ] In Progress  [ ] Done`

---

## Rollback Plan

If deployment fails or user testing shows serious regressions:

- [ ] Revert to the previous stable Render deploy
- [ ] Disable the broken feature flag or revert the last merge
- [ ] Restore known-good environment variables if config caused the issue
- [ ] Verify login, upload, and optimization flows after rollback
- [ ] Log what failed before attempting a new deploy

**Goal:** Roll back to a stable version in under 10 minutes.

---

## MVP Launch Checklist

Before first public deployment:

- [ ] Hosting decision confirmed
- [ ] PostgreSQL instance created
- [ ] Supabase auth configured
- [ ] All required environment variables added
- [ ] Dependencies pinned
- [ ] Local tests pass
- [ ] Local app works against cloud database
- [ ] User isolation verified
- [ ] Logging added to critical flows
- [ ] Screenshots captured for baseline
- [ ] One friend/internal tester can log in and complete the flow

---

## Post-Deploy Smoke Test

Immediately after deployment:

- [ ] App loads from public URL
- [ ] Signup works
- [ ] Login works
- [ ] Resume upload works
- [ ] Optimization completes without crash
- [ ] Download/export works
- [ ] Data persists across refresh
- [ ] Logs show no critical errors

---

## Decision Summary

- Hosting: Render
- Database: PostgreSQL
- Auth: Supabase Auth
- Priority before deploy: PostgreSQL migration, user isolation, auth, and dependency pinning
- Do not deploy until at least one full end-to-end cloud-connected test passes
