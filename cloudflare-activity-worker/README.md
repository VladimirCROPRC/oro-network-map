# ORO activity log Worker

This Worker runs on `oro.proconect.online/*`, records popup views in D1, and
proxies all non-API requests to the existing GitHub Pages origin.

## Cloudflare setup

1. Create a D1 database named `oro-activity-log`.
2. Replace `REPLACE_WITH_D1_DATABASE_ID` in `wrangler.jsonc`.
3. Apply `migrations/0001_activity_logs.sql` to the production database.
4. Deploy the Worker and verify the route `oro.proconect.online/*`.
5. Keep the existing Cloudflare Access application on the same hostname.

The Worker reads the authenticated email from Cloudflare Access `ctx.access`.
Log rows older than 90 days are deleted by the daily scheduled handler.
