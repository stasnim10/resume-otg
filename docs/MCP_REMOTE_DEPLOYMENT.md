# Resume OTG remote connector deployment

Intended connector address: `https://mcp.resumeotg.app/mcp`. The Render service
has deployed; custom-domain DNS and the Streamlit consent-screen rollout are
still pending. Do not advertise this address as ready to connect yet.

## Deployment status — October 1, 2026

- Render service `resume-otg-mcp`, ID `srv-daulp37pn0mc7386gmf0`, runs commit
  `c4ee63f110c189298907c93b9c54e8361e5169b0` from `codex/mcp-connector`.
  It uses the **Free ($0/month)** compute plan.
- Render assigned `resume-otg-mcp.onrender.com`. Its HTTPS `/health` returns
  200; protected-resource discovery returns the intended custom-domain resource
  and Supabase authorization server. Unauthenticated `/mcp` returns 401 with
  the correct discovery challenge.
- Render has registered `mcp.resumeotg.app`, awaiting DNS. Name.com needs a
  CNAME: host `mcp`, target `resume-otg-mcp.onrender.com`, TTL 300.
- Supabase project `xraxyqzbtpsurjyquxfy` remains on its Free plan. Migration
  003 is applied: RLS is enabled on connector approvals, the resume bucket is
  private, four storage policies exist, and all eight existing public tables
  have the restrictive direct-app-session policy.
- OAuth Server and Dynamic OAuth Apps are enabled. Auth Site URL is
  `https://app.resumeotg.app`, authorization path `/`, and the
  `public.mcp_access_token_hook` is enabled. The public JWKS exposes an ES256 key.
- Live SQL checks confirmed an existing account can still read its profile
  through a direct app session, while an OAuth session for that same account
  sees zero profile rows and zero settings rows. An unapproved synthetic OAuth
  session sees no resume objects or connector approvals.
- The Render workspace currently shows an older Flask service
  (`resume-optimizer-otg`, root `resume_optimizer_web`, start `gunicorn app:app`),
  rather than the live Streamlit service at `resume-otg.onrender.com`. Locate the
  correct hosting account before deploying the consent screen; do not replace
  the older service by assumption.
- Pending: Name.com sign-in/DNS, custom-domain TLS verification, correct
  Streamlit deployment, and real-client consent/tool/export/revocation tests.

## Existing domains

- Name.com manages DNS.
- `www.resumeotg.app` points to Vercel (marketing site).
- `app.resumeotg.app` points to `resume-otg.onrender.com` (Streamlit).
- Add a separate Render web service for the MCP endpoint. Do not replace the
  existing app or its DNS records.

## Supabase

1. Back up and review the database, then apply
   `supabase/migrations/003_mcp_connector.sql`. It creates a private Word-file
   bucket, account-owned connector approvals, storage policies, and a token hook.
   The migration also restricts existing public tables to direct app sessions:
   OAuth clients must not read stored AI API keys or unrelated account data.
2. Enable OAuth Server and Dynamic Client Registration under Authentication.
3. Use asymmetric JWT signing keys (ES256 or RS256).
4. Set the Auth Site URL to `https://app.resumeotg.app` and the OAuth authorization
   path to `/`. Supabase adds `authorization_id` to the query string; the Streamlit
   app shows consent after its normal sign-in gate. Preserve existing Google
   callback configuration. If Google sign-in loses the request on a fresh tab,
   sign in first and restart the connector flow.
5. Enable the Custom Access Token Hook `public.mcp_access_token_hook`. The remote
   server strictly requires `https://mcp.resumeotg.app/mcp` in the access token
   audience. Default Supabase tokens with only `authenticated` are rejected.
   If a token hook already exists, merge this logic into it rather than replacing
   existing claims logic. The configured hook preserves the Storage audience.

## Render and DNS

1. Create a new Docker web service from this repository, using
   `resume_optimizer_local/Dockerfile.mcp` and repository root build context.
   `render.yaml` contains a blueprint for this new service.
2. Set `SUPABASE_URL` and `SUPABASE_ANON_KEY` to the same project as the app.
   Set `MCP_PUBLIC_URL=https://mcp.resumeotg.app/mcp`. No service-role key is used.
3. Add `mcp.resumeotg.app` as the Render service's custom domain.
4. In Name.com, add a CNAME with host `mcp` and the exact `.onrender.com` target
   Render assigns to this new service, TTL 300. Wait for Render's TLS certificate.
5. Deploy the updated Streamlit app. After the connector passes live verification,
   set its `MCP_PUBLIC_URL` secret/env var to the same URL. Until that setting is
   present, Settings shows “not live yet” instead of offering a working link.

## Verify before enabling the link

- `/health` returns 200 over HTTPS.
- `/.well-known/oauth-protected-resource/mcp` advertises the MCP resource and
  the Supabase authorization server. An unauthenticated MCP request returns 401
  with the metadata challenge.
- Add Resume OTG in Claude's custom connectors using the public URL. Complete
  sign-in, consent, and tool discovery. Confirm the resource audience hook works
  with the real OAuth exchange and Supabase Storage accepts the resulting token.
- Save a Word resume in Settings → MCP / AI Apps; submit a job description in
  the connected chat. Check tailoring and the signed download URL (10 minutes).
- Test with two accounts: neither can read the other's source or exports.
- Disconnect in Settings and confirm old tokens no longer run tools.
- Confirm OAuth tokens cannot access any existing public data tables.

## Validation limits

Local checks cover JWT validation, OAuth discovery/challenges, source-safe Word
export, and user-scoped path construction. Database RLS, token hooks, live OAuth
sign-in and DNS/TLS require the actual Supabase and Render deployment to validate.
The backend is deployed and the checks listed above passed. The complete
connector flow is not yet verified or ready to advertise.

Source references:
- https://supabase.com/docs/guides/auth/oauth-server/getting-started
- https://supabase.com/docs/guides/auth/oauth-server/mcp-authentication
- https://supabase.com/docs/guides/auth/oauth-server/token-security
