Easy FSC E3
============

Version:
  1.0.3 - Separated option buttons
  FSC output remains original-match verified.

Created by:
  https://t.me/imkadi

Free use only. Not for resale.

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
  Set TELEGRAM_ADMIN_CHAT_ID in Vercel to receive a private admin log whenever
  the bot generates files.
