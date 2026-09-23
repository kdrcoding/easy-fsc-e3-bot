Easy FSC E3
============

Version:
  1.1.0 - Re-consent on new terms; admin error reports; daily cap
  FSC output remains original-match verified.

Created by:
  https://t.me/imkadi

Free use only. Not for resale.

Rate limit:
  Each user can generate at most 1 FSC per minute (configurable via
  the FSC_RATE_LIMIT_SECONDS environment variable, default 60).
  Rate limit events are stored in the fsc_rate_limits table when
  Supabase is configured; otherwise enforced per bot instance.

Daily limit:
  Each user can generate at most FSC_DAILY_LIMIT files per day
  (default 10). Daily usage is stored in the fsc_daily_usage table
  (one row per user per day, in UTC).

Bot consent:
  When a user starts the bot, they must review and accept the Terms &
  Conditions and the Privacy Policy before generating FSC files.
    Terms:   https://easy-fsc-e3-bot.vercel.app/terms.html
    Privacy: https://easy-fsc-e3-bot.vercel.app/privacy.html
  Acceptance is stored in the user_consents table when Supabase is
  configured; otherwise it is kept for the current bot session only.

Run:
  Double-click run_easy_fsc.bat

Build Windows EXE:
  Double-click build_exe.bat
  The finished file will be:
    dist\Easy_FSC_E3.exe

Use:
  1. Enter the 7-character VIN.
  2. Choose One App ID, All App IDs, or ZIP with all App IDs.
  3. Optional: choose a custom template file.
  4. Choose the output folder.
  5. Click Generate FSC.

The generator logic is kept in fsc_core.py and matches the original fsc_E3.py
constants, offsets, template handling, and FSC output format.

All App IDs:
  Batch/ZIP mode generates the same 21 FSC files as the original fsc_E3.py.
  1CR Remote Engine Start is included:
    017C - DME1
    0180 - DME2

Legal:
  See LEGAL_NOTICE.txt.
  Public bot terms page:
    https://easy-fsc-e3-bot.vercel.app/terms.html

Feature guide:
  See features.html or:
    https://easy-fsc-e3-bot.vercel.app/features.html
  1CR Remote Start guide:
    https://easy-fsc-e3-bot.vercel.app/remote-start.html

Telegram bot:
  See TELEGRAM_BOT_SETUP.txt.

Admin reader:
  Set TELEGRAM_ADMIN_CHAT_ID in Vercel for admin-only /stats.
  Set TELEGRAM_ADMIN_DM_LOGS=true only if you want a private message for every
  generation.

Supabase stats:
  Run supabase_schema.sql in Supabase, then set SUPABASE_URL and
  SUPABASE_SECRET_KEY in Vercel. The homepage will show total requests, total
  FSC files generated, and unique users.
