# Resume OTG remote connector deployment

Connector address: `https://mcp.resumeotg.app/mcp`.

## Deployment status — October 1, 2026

- MCP service `resume-otg-mcp` (`srv-daulp37pn0mc7386gmf0`) runs on Render Free.
  HTTPS health and discovery return 200; unauthenticated MCP returns 401 with
  the correct discovery challenge.
- Replacement Streamlit service `resume-otg` (`srv-dav0p559fdbs73aoet6g`) in STOTG
  runs `codex/mcp-connector`, application commit `9872027`.
  Its Render URL is `https://resume-otg-uvgw.onrender.com/`.
- Name.com CNAME `app` now points to `resume-otg-uvgw.onrender.com`, TTL 300.
  Public resolver 1.1.1.1 confirms the new target. HTTPS serves the replacement's
  Google callback component; the app health endpoint returns 200.
- Name.com CNAME `mcp` points to `resume-otg-mcp.onrender.com`, TTL 300.
  Landing-page apex and `www` records are unchanged.
- The old Streamlit service `srv-dan9906gekts7385uueg` remains running in
  My Workspace at `https://resume-otg.onrender.com/` (health 200). Only its app
  custom-domain attachment was removed to transfer the hostname. It was not
  deleted or suspended. The older STOTG Flask service is also unchanged.
- Supabase Free project `xraxyqzbtpsurjyquxfy` has OAuth Server, dynamic client
  registration, private resume storage, migration 003 and the audience hook.
  Auth Site URL is `https://app.resumeotg.app`; consent path is `/`.
  Redirect allowlists include `https://app.resumeotg.app/**` so Google sign-in
  retains the opaque `authorization_id`. Render's redirect environment value
  is `https://app.resumeotg.app/`.
- Live PKCE verification completed Google sign-in, explicit consent, code/token
  exchange, JWT signature/issuer/resource audience/client ID checks, MCP
  initialize and tool discovery. A synthetic DOCX passed preparation, paragraph
  replacement, export and signed download; the saved source hash was unchanged.
- After cutover, Google sign-in returned to `app.resumeotg.app` with the consent
  request intact and the credential fragment cleared. Denying consent returned
  `access_denied` with no authorization code.
- Disconnecting the temporary verification client immediately blocked its old
  access token from running tools. Actual OAuth REST requests returned zero
  profile and user-settings rows. Earlier SQL checks also covered unapproved
  OAuth sessions and direct-app-session access.
- Ten focused local regression checks passed. Supabase security advisors report
  no RLS issues; the pre-existing leaked-password-protection warning remains.
- A synthetic source and exported Word file remain in the verification account's
  private MCP storage. Upload the actual resume in Settings before real use.

## Existing domains

- `www.resumeotg.app`: Vercel marketing site.
- `app.resumeotg.app`: replacement Streamlit service.
- `mcp.resumeotg.app`: separate OAuth-protected MCP service.

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
   callback configuration. The app preserves the opaque request ID through
   Google sign-in and transfers tokens through its local Streamlit component.
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
Live protocol verification passed with a temporary PKCE client and synthetic
resume. Claude/ChatGPT client-specific onboarding and a complete two-real-account
browser test are not covered by that verification.

Source references:
- https://supabase.com/docs/guides/auth/oauth-server/getting-started
- https://supabase.com/docs/guides/auth/oauth-server/mcp-authentication
- https://supabase.com/docs/guides/auth/oauth-server/token-security
