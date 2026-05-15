# CEACStatusBot Web

🎉 **Deployed Online:** The service is already deployed and available online. You can directly use it at [ceac.mikezhuang.cn](https://ceac.mikezhuang.cn).

[中文文档](README.Chinese.md)

> **Nonprofit personal project.** If CEACStatusBot helps you, voluntary support helps cover server and maintenance costs. Premium can be upgraded by sharing a Xiaohongshu post with the site link, screenshots, and your experience, then contacting the admin; or by leaving your account email in the donation note for manual review. Contact: `ceac-admin@mikezhuang.cn`.
>
> <img src="frontend/public/support/buy-me-a-coffee.jpg" alt="Support CEACStatusBot" width="180" />
>
> Small print: this is a non-official service and is not affiliated with the U.S. Department of State, CEAC, GTS, or CITIC Bank. Donations are voluntary support, not a purchase of official services, and do not guarantee visa results, passport progress, slot availability, or booking success.

CEACStatusBot Web is a self-hosted U.S. visa CEAC status monitoring dashboard. It provides account registration and login, email verification codes, password reset, multiple visa profiles, status history, email notifications, an admin console, and a production security baseline for deployment on your own server.

This project is a modified version released under the GPLv3 license. It preserves and adapts ideas around CEAC status querying and captcha recognition from the original [Andision/CEACStatusBot](https://github.com/Andision/CEACStatusBot) project.

## Features

- FastAPI backend, SQLite database, APScheduler queue scheduler, and a standalone Worker for query jobs.
- React + Vite + TypeScript frontend console with dark/light themes and Chinese/English language switching.
- Open registration with email verification for both signup and password reset.
- Standard accounts can create 1 CEAC profile, and automatic checks still run about once per hour; after `Issued`, checks slow to once per day and stop after one week. Standard accounts get 1 manual refresh per day and a limited daily email quota. Premium accounts can create 5 profiles and use high query/email quotas. Admins are exempt.
- Enabled profiles are queued once per hour at a random minute. After a profile enters `Issued`, automatic CEAC checks slow down to once per day and stop automatically after one week.
- When a CEAC profile enters `Approved` or `Issued`, status emails invite the user to enter UID/HAL and enable GTS passport appointment slot monitoring.
- GTS passport appointment monitoring is bound to a CEAC profile. It polls at a random 5-10 minute interval by default, with separate switches for automatic polling and slot-change email notifications. Once slots are found, polling slows to roughly once per hour until the user confirms they have booked and stops monitoring.
- `Approved`, `Issued`, Issued auto-stop, and GTS slot emails include a small nonprofit support note and the same donation QR image used on the website. Negative CEAC statuses such as `Refused` do not include the donation block.
- Creating an enabled profile automatically queues one initial CEAC query. `Query now` creates manual jobs. The frontend polls job status and refreshes the profile and timeline after completion. Non-admin accounts have a daily manual query limit.
- No email is sent when status is unchanged. Status changes or CEAC last-updated changes are written to history and trigger notifications.
- Supports both a system default SMTP sender and per-user custom SMTP settings.
- Admins can manage account tiers and Worker priority, and view profile summaries, system query logs, security events, and default sender configuration.
- Query logs record manual/automatic sources, absolute timestamps, duration, success/failure, and error messages.
- The frontend includes a custom SVG favicon/brand icon and an optional ICP record footer link.

## Account Initialization

Local demo accounts are not created by default. For public deployments, create accounts through the registration flow, or create the first admin account directly in the production database.

If you only need local demo accounts during development, temporarily set `SEED_DEFAULT_USERS=true` and provide `DEFAULT_ADMIN_EMAIL` / `DEFAULT_ADMIN_PASSWORD`. Do not enable this switch in public deployments.

## Local Development

Install backend dependencies:

```bash
pip install uv
uv sync
```

Copy the environment file:

```bash
cp .env.example .env
```

Start the backend:

```bash
uv run uvicorn CEACStatusBot.web.main:app --reload --host 127.0.0.1 --port 8000
```

Start the Worker in another terminal:

```bash
uv run python -m CEACStatusBot.web.worker
```

Start the frontend:

```bash
cd frontend
npm install
npm run dev
```

Open `http://127.0.0.1:5173`. VS Code debug configuration lives in `.vscode/launch.json` and does not automatically open a browser.

## Environment Variables

| Variable | Default | Description |
| --- | --- | --- |
| `DATABASE_PATH` | `ceacstatusbot.sqlite3` | SQLite database path |
| `SECRET_KEY` | Development default | Session signing secret. Must be changed for public deployments |
| `CREDENTIAL_KEY_FILE` | Empty | AES-256-GCM master key file path. Production recommendation: `/opt/ceacstatusbot-runtime/secrets/credential-master.key` |
| `ENCRYPTION_KEY` | Empty | Compatibility/migration key for old Fernet ciphertext. It is not used as the new credential master key |
| `SYSTEM_FROM_EMAIL` | Empty | Default system sender email |
| `SYSTEM_EMAIL_PASSWORD` | Empty | Default system sender password/app password. In production, prefer saving it through the admin console so it is stored encrypted |
| `SYSTEM_SMTP_HOST` | `smtp.exmail.qq.com` | System SMTP host |
| `SYSTEM_SMTP_PORT` | `465` | System SMTP port |
| `SYSTEM_SMTP_USE_SSL` | `true` | Whether to use SMTP SSL |
| `CORS_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` | Frontend origins allowed to access the backend |
| `CSRF_TRUSTED_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` | Trusted Origin / Referer values for sensitive requests |
| `ALLOWED_HOSTS` | `localhost,127.0.0.1,ceac.mikezhuang.cn` | Host header allowlist enforced by the app |
| `TRUSTED_PROXY_IPS` | `127.0.0.1,::1` | Reverse proxies whose `X-Forwarded-For` value is trusted |
| `API_MAX_BODY_BYTES` | `131072` | Maximum API request body size |
| `COOKIE_SECURE` | `false` | Defaults to `false` locally. Must be `true` behind HTTPS in production |
| `SESSION_IDLE_TIMEOUT_MINUTES` | `720` | Automatic logout after inactivity |
| `SESSION_ABSOLUTE_TIMEOUT_DAYS` | `14` | Maximum database session lifetime |
| `AUTH_LOGIN_IP_DEVICE_LIMIT_PER_MINUTE` | `10` | Login attempt limit per IP/device |
| `AUTH_LOGIN_EMAIL_FAILURE_LIMIT_PER_15_MINUTES` | `5` | Failed-login threshold before account/email cooldown |
| `AUTH_CODE_EMAIL_LIMIT_PER_HOUR` | `3` | Verification-code emails per address per hour |
| `AUTH_CODE_IP_DEVICE_LIMIT_PER_10_MINUTES` | `3` | Verification-code requests per IP/device window |
| `STANDARD_API_LIMIT_PER_MINUTE` | `120` | Authenticated API limit for standard accounts |
| `PREMIUM_API_LIMIT_PER_MINUTE` | `300` | Authenticated API limit for Premium accounts |
| `ADMIN_API_LIMIT_PER_MINUTE` | `600` | Authenticated API limit for admins |
| `QUERY_JOB_TIMEOUT_SECONDS` | `360` | Marks running query jobs as failed after this many seconds. Queue wait time does not count |
| `WORKER_POLL_INTERVAL_SECONDS` | `1` | Worker polling interval for the SQLite job queue. GTS midnight burst jobs need second-level pickup |
| `STANDARD_DAILY_MANUAL_QUERY_LIMIT` | `1` | Daily CEAC/GTS manual query limit for standard accounts |
| `PREMIUM_DAILY_MANUAL_QUERY_LIMIT` | `1000` | Daily CEAC/GTS manual query limit for Premium accounts |
| `STANDARD_DAILY_EMAIL_LIMIT` | `5` | Daily CEAC/GTS business email limit for standard accounts. Signup and password-reset codes are not counted |
| `PREMIUM_DAILY_EMAIL_LIMIT` | `1000` | Daily CEAC/GTS business email limit for Premium accounts |
| `SEED_DEFAULT_USERS` | `false` | Local demo account seed switch. Must remain `false` in public deployments |
| `DEFAULT_ADMIN_EMAIL` | Empty | Seed admin email, only used when `SEED_DEFAULT_USERS=true` |
| `DEFAULT_ADMIN_PASSWORD` | Empty | Seed admin password, only used when `SEED_DEFAULT_USERS=true` |
| `DEFAULT_USER_EMAIL` | Empty | Seed regular user email, only used when `SEED_DEFAULT_USERS=true` |
| `DEFAULT_USER_PASSWORD` | Empty | Seed regular user password, only used when `SEED_DEFAULT_USERS=true` |
| `VITE_ICP_RECORD_NUMBER` | Empty | ICP record number shown in the frontend footer, for example `沪ICP备2026015123号-1` |

Common Tencent Exmail settings:

- SMTP: `smtp.exmail.qq.com`
- SMTP SSL port: `465`
- IMAP: `imap.exmail.qq.com`
- IMAP SSL port: `993`

The current web application only needs SMTP. IMAP is not used for status querying or notifications.

## Query And Notification Logic

Each enabled visa profile stores `nextCheckAt`. The scheduler scans due profiles every minute and writes automatic query jobs into the SQLite queue. The standalone Worker consumes the queue, calls CEAC, records query logs, updates status history, and sends email notifications.

Creating an enabled profile automatically queues one initial CEAC query, and this initial automatic query does not consume the daily manual quota. `Query now` does not run the scraper directly in the web process. It creates a `manual` job and returns a job ID. The frontend polls job status, then refreshes the profile and status timeline. CEAC failure messages are shown on the profile detail page so users can tell whether they should check their inputs or retry later because CEAC is slow. CEAC `Query now` and GTS `Check slots now` share the same daily manual query quota: Standard accounts default to 1 per day, Premium accounts default to 1000 per day, and admin accounts are exempt. CEAC/GTS business emails also have daily account-level quotas: Standard defaults to 5 per day and Premium defaults to 1000 per day. Worker priority uses smaller numbers first; Premium defaults to 50 and Standard defaults to 100, while admins can override either value.

The system compares the latest history item with the current CEAC result:

- Exact match: only records the query log; no notification is sent.
- Status or CEAC last-updated changed: writes a new status history item and sends an email.

If a profile disables status update email notifications, the system still performs scheduled checks and records the timeline, but does not send automatic emails when the status changes. Users can still click `Test email` to send the latest existing status template manually.

Passport appointment slot monitoring uses the same-origin GTS API flow: authenticate with UID/HAL via `https://scheduling-api.gtspremium.com/authenticate`, then call `/availability7days/` to query 7-day availability. UID/HAL, raw GTS responses, and slot-change history are encrypted at rest. The system normalizes GTS responses into three states: `not_eligible` means the passport is not eligible for appointment yet, `no_slot` means the passport appears eligible but no time is available, and `has_slot` means one or more appointment times were returned. Automatic polling is controlled by `Enable automatic monitoring`; slot-change email delivery is controlled by `Send email when status changes`. Emails are sent for `not_eligible -> no_slot`, `no_slot -> has_slot`, and changed `has_slot` time lists. `no_slot` and `has_slot` emails include the full UID/HAL, the official GTS entry URL, the app entry URL, usage instructions, and a warning not to forward the email; the app does not use guessed UID/HAL deep links because the public GTS site does not expose a reliable autofill URL. Slot emails list readable dates and specific times and intentionally omit raw JSON/JWT payloads. While in `no_slot`, the scheduler uses China time for a midnight burst: 15-second checks from 23:59 to 00:02, roughly 5-second checks around 23:59:45-00:00:30, and explicit targets for 00:00:00 and 00:00:02. Once `no_slot` or `has_slot` is confirmed, the linked CEAC automatic status query is stopped and locked; only an admin can restore it. After slots are found, GTS polling slows to roughly once per hour and no longer uses the midnight burst. Users should click `I booked, stop monitor` after completing the appointment on the GTS site. GTS jobs are consumed by the Worker and appear as `passport_slot_manual` or `passport_slot_automatic`; queued jobs are claimed by `users.worker_priority ASC, query_jobs.id ASC`, where lower priority numbers run earlier.

## Production Security Baseline

- Login passwords use Argon2id. Legacy PBKDF2-SHA256 hashes are kept only for migration compatibility and are upgraded after successful login.
- CEAC profile sensitive fields, GTS UID/HAL, SMTP app passwords, and raw query snapshots are encrypted with AES-256-GCM.
- The master key is stored in a local key file outside the repository. Do not write it into code, README files, `backend.env`, or GitHub.
- Production cookies must use `HttpOnly + SameSite=Lax + Secure`.
- All sensitive API requests validate `Origin` / `Referer`. Production should only trust `https://ceac.mikezhuang.cn`.
- Application-level defenses include anonymous device cookies, SQLite-backed IP/device/account/email rate limits, login cooldowns, database-backed sessions with idle timeout, request body limits, Host allowlisting, and security-event audit logs.
- The optional `Remember password` checkbox stores the password in the browser local storage and should only be used on private devices.
- The CEAC scraper target is fixed to `https://ceac.state.gov`; the GTS slot query target is fixed to `https://scheduling-api.gtspremium.com`. User input cannot affect request hosts or URLs.
- Production entry goes through the HTTPS domain only. Port 8010 is not a public entry point.
- Nginx config sets connection timeouts, request rate limits, security headers, and only enables TLS 1.2 / TLS 1.3.

For the complete security model, see [SECURITY.md](SECURITY.md).

## Deployment And Operations

Production deployment instructions are in [DEPLOYMENT.md](DEPLOYMENT.md). Daily operations and troubleshooting are in [OPERATIONS.md](OPERATIONS.md).

Core conventions:

- Code repository: `/opt/ceacstatusbot`
- Runtime data: `/opt/ceacstatusbot-runtime`
- Frontend build output: `/var/www/ceacstatusbot/frontend/dist`
- Backend service: `ceacstatusbot-backend.service`
- Worker service: `ceacstatusbot-worker.service`
- Production domain: `https://ceac.mikezhuang.cn`
- Auto-deploy repository: `https://github.com/Mike-Zhuang/CEACStatusBot_Web`

During deployment, do not commit or overwrite `.env`, `backend.env`, the SQLite database, master key files, logs, backups, SMTP app passwords, or server private keys.

## License

This project follows the [GNU General Public License v3.0](LICENSE). If you distribute a modified version, you must continue to comply with GPLv3 requirements around source availability, license preservation, and modification notices.

## Acknowledgements

Thanks to [Andision/CEACStatusBot](https://github.com/Andision/CEACStatusBot). This project builds on its CEAC automatic query direction and parts of its implementation, then adapts them into a web-based, service-oriented, multi-user application.
