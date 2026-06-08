# Protected Mega Report Gate

This Worker serves `reports/mega_validation_report_latest.html` only after a Discord OAuth login confirms that the user currently has an allowed role in the configured Discord server. Deploy and check commands copy the report into `report-gate/public/` first, so only the HTML asset is uploaded to Cloudflare.

The primary Worker name is `scoring-bot-report`. The legacy `screening-bot-report-gate` Worker is deployed with the same code and assets so existing report links continue to work.

## Flow

1. A request to `/`, `/report`, or `/mega_validation_report_latest.html` reaches the Worker first.
2. The Worker redirects unauthenticated users to Discord OAuth with `identify guilds.members.read`.
3. The callback fetches `/users/@me/guilds/{guild.id}/member` and stores the OAuth access token plus the latest allowed roles in an encrypted, HttpOnly session cookie.
4. Protected requests re-check `/users/@me/guilds/{guild.id}/member` after a short cache window, so role removals are reflected without hammering Discord's API.
5. Access is granted only when the current member `roles` array contains one of `DISCORD_ALLOWED_ROLE_IDS`.
6. The report is served with `Cache-Control: private, no-store` and a guard script that checks `/auth/check` every 120 seconds while the page is open.

## Local commands

```bash
cd report-gate
npm ci
npm run check
npm run dev
```

## Required Discord setup

Create or reuse a Discord application and add this redirect URI:

```text
https://<worker-domain>/auth/callback
```

If you use both `*.workers.dev` and a custom domain, register both callback URLs.

## Cloudflare Worker configuration

Non-secret settings are in `wrangler.jsonc`:

| Variable | Purpose |
|---|---|
| `DISCORD_GUILD_ID` | Discord server ID to check |
| `DISCORD_ALLOWED_ROLE_IDS` | Comma-separated role IDs allowed to view the report |
| `ACCESS_PURCHASE_URL` | Purchase page shown when a logged-in Discord user does not have an allowed role |
| `REPORT_ASSET_PATH` | Report asset path, normally `/mega_validation_report_latest.html` |
| `SESSION_TTL_SECONDS` | Signed session cookie lifetime |
| `PUBLIC_BASE_URL` | Optional fixed public origin, such as `https://reports.example.com` |

Secrets must be set in Cloudflare, not committed:

```bash
cd report-gate
npx wrangler secret put DISCORD_CLIENT_ID
npx wrangler secret put DISCORD_CLIENT_SECRET
npx wrangler secret put SESSION_SECRET
```

Generate a random session secret before setting it:

```bash
node -e "console.log(crypto.randomUUID() + crypto.randomUUID())"
```

## Deploy

```bash
cd report-gate
npm ci
npm run deploy:dry-run
npm run deploy
npm run deploy:legacy
```

For GitHub Actions auto-deploy, set repository secrets:

| Secret | Purpose |
|---|---|
| `CLOUDFLARE_API_TOKEN` | Token with permission to deploy this Worker |
| `CLOUDFLARE_ACCOUNT_ID` | Cloudflare account ID |

The existing `Mega Validation Report` workflow deploys both the primary Worker and legacy Worker after regenerating the report when those two Cloudflare secrets are present.
