# Easy FSC E3

Telegram bot that generates FSC (FSC-E3) files for your 7-character VINs — plus a desktop app and a web page.

**Current version: 1.1.0** — "Admin errors, daily cap, re-consent"

## :robot: Open the bot in Telegram

> **[https://t.me/FSCCreateBOT](https://t.me/FSCCreateBOT)** — tap to open, press **Start**, and send your 7-character VIN.

- Made by [https://t.me/imkadi](https://t.me/imkadi)
- Free to use. Not for resale.

---

## What's new in 1.1.0

| Change | What it means |
|---|---|
| **Accept terms again** | Consent is tied to the bot version. When a new version comes out, the bot asks users to review and accept the Terms & Privacy again. |
| **Daily cap (default 3)** | Each user can generate FSC files for up to **3 different VINs per day**. Re-generating the same VIN is free and does not use a slot. |
| **Countdown message** | After each file, the bot says how many slots are left today: "You have 2 generations left today." |
| **Same VIN is free** | `TEST123` sent 3 times = 1 slot used, not 3. Only *new* cars count toward the daily limit. |
| **Admin error reports** | If a generation fails, you (the admin) get a private message with the user, input, and traceback. |
| **Rate limit (1/min)** | One generation per minute per user, to stop spam. |

## Feature highlights

- Send any **7-character VIN** to the bot, get FSC files back as a ZIP.
- **[Open the bot now → https://t.me/FSCCreateBOT](https://t.me/FSCCreateBOT)**
- ZIP mode includes the **21 App IDs** — the same ones the original `fsc_E3.py` generates.
- **1CR Remote Engine Start** included: `017C` (DME1) and `0180` (DME2).
- Users must **accept Terms & Conditions and the Privacy Policy** before generating.
- **Admin-only stats**: `/stats` shows total requests, total FSC files, unique users, and daily breakdown.
- **Supabase storage** (optional): logs every generation for stats.
- Desktop app (`easy_fsc_app.py`) and a public web page for the same generator.

## FSC output — 1:1 verified

The FSC file output is **byte-for-byte identical to the original `fsc_E3.py`**.

Verified automatically across **294 combinations** (14 VINs x 21 App IDs):

- every file is **188 bytes**
- **0 differences** vs the original CLI output
- same constants, offsets, template handling, MD5, and final FSC bytes.

The generator logic lives in `fsc_core.py`. It was only ever *cleaned up* (never changed its output) — limits, consent, and messages live outside it.

---

## Limits (how the bot protects itself)

| Limit | Default | Env var | Notes |
|---|---|---|---|
| Generation rate | 1 per minute | `FSC_RATE_LIMIT_SECONDS` | Per user |
| New cars per day | 3 | `FSC_DAILY_LIMIT` | Re-generating the same VIN is free |

---

## How to set it up

### 1. Telegram bot

See **`TELEGRAM_BOT_SETUP.txt`** for the full step-by-step (creating the bot with @BotFather, getting your chat ID, etc.).

### 2. Deploy to Vercel

The repo is a Vercel serverless project. Connect the repo (or import it), and set these environment variables:

| Variable | Required | Purpose |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | Yes | Your bot token from @BotFather |
| `TELEGRAM_WEBHOOK_SECRET` | Yes | A random secret you choose; secures the webhook URL |
| `FSC_BOT_MODE` | No | `single` or `zip` (default `zip`) |
| `FSC_BOT_APPID` | No | Custom App ID for single mode (default `017C`) |
| `TELEGRAM_ADMIN_CHAT_ID` | No | Your chat ID — enables `/stats` and error reports |
| `TELEGRAM_ADMIN_DM_LOGS` | No | `true` = DM you on every generation (default off) |
| `FSC_RATE_LIMIT_SECONDS` | No | Seconds between generations (default `60`) |
| `FSC_DAILY_LIMIT` | No | Different cars per day (default `3`) |
| `SUPABASE_URL` | No | Your Supabase project URL (for stats/storage) |
| `SUPABASE_SECRET_KEY` | No | Your Supabase service role key (for stats/storage) |

> **`DEPLOY.txt`** is your one-stop deploy sheet: copy-paste Supabase SQL, the env var list, and the webhook command all in one place.

### 3. Run the Supabase SQL (optional, for stats)

Open **Supabase → SQL Editor**, paste the entire **`supabase_schema.sql`** file, and Run.

- Safe to re-run — every statement uses `IF NOT EXISTS` / `CREATE OR REPLACE`.
- Tables: `fsc_generation_logs`, `user_consents`, `fsc_rate_limits`, `fsc_daily_vins`
- Views: `fsc_generation_stats`, `fsc_generation_daily_stats`

### 4. Set the webhook

After deploying, point Telegram at your Vercel URL:

```
https://api.telegram.org/bot<YOUR_TOKEN>/setWebhook?url=https://<your-app>.vercel.app/telegram&secret_token=<YOUR_WEBHOOK_SECRET>
```

A ready-made PowerShell script is in **`set_telegram_webhook.ps1`**.

---

## Run it locally (desktop)

1. `python easy_fsc_app.py`
2. Enter the 7-character VIN
3. Choose **One App ID**, **All App IDs**, or **ZIP with all**
4. Pick the output folder
5. Click **Generate FSC**

For Windows: double-click **`run_easy_fsc.bat`** to run, or **`build_exe.bat`** to build `dist\Easy_FSC_E3.exe`.

## Web pages

| Page | URL |
|---|---|
| Home / stats | `https://easy-fsc-e3-bot.vercel.app/` |
| Terms | `https://easy-fsc-e3-bot.vercel.app/terms.html` |
| Privacy | `https://easy-fsc-e3-bot.vercel.app/privacy.html` |
| Feature guide | `https://easy-fsc-e3-bot.vercel.app/features.html` |
| 1CR Remote Start guide | `https://easy-fsc-e3-bot.vercel.app/remote-start.html` |

## Legal

See **`LEGAL_NOTICE.txt`** and the public Terms page above. Use only with systems, vehicles, files, and data you own or have permission to service. Use at your own risk.

## Project layout

```
api/telegram.py          Bot webhook handler (consent, limits, errors)
api/supabase_helpers.py  Supabase read/write helpers
api/ping.py / stats.py   Health + stats endpoints
fsc_core.py              The FSC generator (1:1 match with original)
supabase_schema.sql      All tables + views (run in Supabase)
DEPLOY.txt               One-file deployment guide
easy_fsc_app.py          Desktop app
*.html                   Public web pages (Terms, Privacy, Features, Remote Start)
```