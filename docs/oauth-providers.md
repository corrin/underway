# OAuth Provider Setup

## Google

- **Console:** https://console.cloud.google.com/ > APIs & Credentials > OAuth 2.0 Client IDs
- **Dev redirect URI:** `https://underway-lakeland.ngrok.io/api/oauth/google/callback`
- **Prod redirect URI:** `https://www.underway.today/api/oauth/google/callback`
- **Test users:** OAuth consent screen > Test users (required while app is in "Testing" mode)
- **Scopes:** `openid`, `userinfo.email`, `calendar`, `tasks`

## Microsoft 365

- **Console:** https://portal.azure.com/ > App registrations
- **Dev redirect URI:** `https://underway-lakeland.ngrok.io/api/oauth/o365/callback`
- **Prod redirect URI:** `https://www.underway.today/api/oauth/o365/callback`

## Todoist

- **Console:** https://developer.todoist.com/appconsole.html
- **Install URL:** https://app.todoist.com/app/install/86992_513a68d619156bdfd5a3babb
- **Verification token:** `86992_2389c34962803737e5912167` (for webhooks, not currently used)
- **Dev redirect URI:** `https://underway-lakeland.ngrok.io/api/oauth/todoist/callback`
- **Prod redirect URI:** `https://www.underway.today/api/oauth/todoist/callback`
- **Note:** Todoist only allows one redirect URI per app. Dev and prod need separate app registrations.
