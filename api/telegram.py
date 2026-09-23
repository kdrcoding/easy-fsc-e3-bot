from __future__ import annotations

import io
import json
import math
import os
import sys
import time
import traceback
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from http.server import BaseHTTPRequestHandler
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
API_DIR = Path(__file__).resolve().parent
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))

from fsc_core import (
    ALL_APPIDS,
    APP_VERSION,
    APP_VERSION_NAME,
    FEATURE_GUIDE,
    REMOTE_START_GUIDE,
    DEFAULT_APPID,
    build_fsc,
    load_template,
    parse_appid,
    validate_vin,
)
from supabase_helpers import (
    get_consent,
    get_daily_count,
    get_rate_limit_wait,
    get_stats,
    log_generation,
    record_daily_usage,
    record_rate_limit,
    set_consent,
    supabase_configured,
)


BOT_TOKEN_ENV = "TELEGRAM_BOT_TOKEN"
WEBHOOK_SECRET_ENV = "TELEGRAM_WEBHOOK_SECRET"
OUTPUT_MODE_ENV = "FSC_BOT_MODE"
APPID_ENV = "FSC_BOT_APPID"
ADMIN_CHAT_ID_ENV = "TELEGRAM_ADMIN_CHAT_ID"
ADMIN_DM_LOGS_ENV = "TELEGRAM_ADMIN_DM_LOGS"
RATE_LIMIT_SECONDS_ENV = "FSC_RATE_LIMIT_SECONDS"
DAILY_LIMIT_ENV = "FSC_DAILY_LIMIT"

TERMS_URL = "https://easy-fsc-e3-bot.vercel.app/terms.html"
PRIVACY_URL = "https://easy-fsc-e3-bot.vercel.app/privacy.html"
CALLBACK_ACCEPT = "consent:accept"
CALLBACK_DECLINE = "consent:decline"


def _json_response(handler: BaseHTTPRequestHandler, status: int, body: dict) -> None:
    payload = json.dumps(body).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(payload)))
    handler.end_headers()
    handler.wfile.write(payload)


def _telegram_api(method: str, fields: dict[str, str], files: dict[str, tuple[str, bytes]] | None = None) -> dict:
    token = os.environ.get(BOT_TOKEN_ENV)
    if not token:
        raise RuntimeError(f"Missing env var {BOT_TOKEN_ENV}")

    url = f"https://api.telegram.org/bot{token}/{method}"
    if not files:
        data = urllib.parse.urlencode(fields).encode("utf-8")
        request = urllib.request.Request(url, data=data, method="POST")
        with urllib.request.urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))

    boundary = "----EasyFscE3Boundary"
    parts: list[bytes] = []
    for name, value in fields.items():
        parts.extend(
            [
                f"--{boundary}\r\n".encode(),
                f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode(),
                str(value).encode("utf-8"),
                b"\r\n",
            ]
        )
    for name, (filename, content) in files.items():
        parts.extend(
            [
                f"--{boundary}\r\n".encode(),
                f'Content-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'.encode(),
                b"Content-Type: application/octet-stream\r\n\r\n",
                content,
                b"\r\n",
            ]
        )
    parts.append(f"--{boundary}--\r\n".encode())

    body = b"".join(parts)
    request = urllib.request.Request(url, data=body, method="POST")
    request.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
    request.add_header("Content-Length", str(len(body)))
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def _send_message(chat_id: int, text: str, reply_markup: dict | None = None) -> None:
    fields = {
        "chat_id": str(chat_id),
        "text": text,
        "disable_web_page_preview": "true",
    }
    if reply_markup:
        fields["reply_markup"] = json.dumps(reply_markup)
    _telegram_api("sendMessage", fields)


def _send_document(chat_id: int, filename: str, content: bytes, caption: str) -> None:
    _telegram_api(
        "sendDocument",
        {"chat_id": str(chat_id), "caption": caption},
        {"document": (filename, content)},
    )


def _edit_message_text(chat_id: int, message_id: int, text: str) -> None:
    fields = {
        "chat_id": str(chat_id),
        "message_id": str(message_id),
        "text": text,
        "disable_web_page_preview": "true",
    }
    _telegram_api("editMessageText", fields)


def _answer_callback(callback_query_id: str, text: str) -> None:
    fields = {
        "callback_query_id": callback_query_id,
        "text": text,
    }
    _telegram_api("answerCallbackQuery", fields)


def _admin_chat_id() -> int | None:
    value = os.environ.get(ADMIN_CHAT_ID_ENV, "").strip()
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _is_admin(chat_id: int) -> bool:
    return _admin_chat_id() == chat_id


def _notify_admin(user_chat_id: int, vin: str, mode: str, file_count: int, filename: str) -> None:
    if os.environ.get(ADMIN_DM_LOGS_ENV, "").strip().lower() not in {"1", "true", "yes", "on"}:
        return
    admin_chat_id = _admin_chat_id()
    if not admin_chat_id:
        return
    if admin_chat_id == user_chat_id:
        return
    _send_message(
        admin_chat_id,
        "\n".join(
            [
                "Admin Log - FSC Generated",
                f"VIN: {vin}",
                f"Mode: {mode}",
                f"Files created: {file_count}",
                f"Sent file: {filename}",
                f"User chat ID: {user_chat_id}",
                f"Saved to Supabase: {'yes' if supabase_configured() else 'not configured'}",
            ]
        ),
    )


def _notify_admin_error(user_chat_id: int, input_text: str, exc: Exception) -> None:
    admin_chat_id = _admin_chat_id()
    if not admin_chat_id:
        return
    detail = traceback.format_exc(limit=6).strip()
    if len(detail) > 3000:
        detail = detail[-3000:]
    _send_message(
        admin_chat_id,
        "\n".join(
            [
                "Admin Log - FSC Generation Error",
                f"User chat ID: {user_chat_id}",
                f"Input: {input_text}",
                f"Error: {exc!r}",
                f"Traceback:\n{detail}",
            ]
        ),
    )


def _help_text() -> str:
    return (
        "Easy FSC E3 Bot\n\n"
        f"Version {APP_VERSION} - {APP_VERSION_NAME}\n"
        "Created by https://t.me/imkadi\n"
        "Free use only. Not for resale.\n\n"
        "Send your 7-character VIN, for example:\n"
        "TEST123\n\n"
        "The bot will generate FSC files and send them back as a ZIP.\n"
        "ZIP mode includes 1CR Remote Start App IDs 017C and 0180.\n\n"
        f"Limits: 1 generation per minute, up to {_daily_limit()} per day."
    )


def _legal_text() -> str:
    return (
        "Legal Notice\n\n"
        "Free use only. Not for resale.\n\n"
        "Use only with systems, vehicles, files, and data that you own or have explicit permission to service. "
        "You are responsible for following all laws, contracts, warranties, software licenses, and local regulations.\n\n"
        "Use at your own risk. If something goes wrong, including damage, data loss, warranty issues, legal issues, "
        "incorrect use, service interruption, or account problems, the creator is not responsible.\n\n"
        "This bot is provided as-is with no warranty and no official affiliation with any vehicle manufacturer, dealer, "
        "software vendor, platform provider, or third party.\n\n"
        f"Terms: {TERMS_URL}\n"
        f"Privacy Policy: {PRIVACY_URL}"
    )


_CONSENT_MEM: set[int] = set()


def _terms_summary_text() -> str:
    return (
        "Welcome to Easy FSC E3 Bot!\n\n"
        f"v{APP_VERSION} - {APP_VERSION_NAME}\n"
        "Created by https://t.me/imkadi\n"
        "Free use only. Not for resale.\n\n"
        "Before generating any FSC files you must review and accept the\n"
        "Terms & Conditions and the Privacy Policy.\n\n"
        "By accepting you confirm:\n"
        "- You use the bot only with systems, vehicles, files, and data that you own or have permission to service.\n"
        "- You are responsible for following all laws, contracts, warranties, and local regulations.\n"
        "- You use any generated files at your own risk.\n\n"
        "Data note:\n"
        "- The bot stores your Telegram user ID, your consent time, and (if stats are enabled) the VINs you generate.\n"
        "Read the links below, then tap Accept to continue."
    )


def _consent_keyboard() -> dict:
    return {
        "inline_keyboard": [
            [{"text": "Terms & Conditions", "url": TERMS_URL}],
            [{"text": "Privacy Policy", "url": PRIVACY_URL}],
            [
                {"text": "Accept", "callback_data": CALLBACK_ACCEPT},
                {"text": "Decline", "callback_data": CALLBACK_DECLINE},
            ],
        ]
    }


def _send_consent_prompt(chat_id: int) -> None:
    _send_message(chat_id, _terms_summary_text(), _consent_keyboard())


def _is_consented(chat_id: int) -> bool:
    if chat_id in _CONSENT_MEM:
        return True
    try:
        accepted_version = get_consent(chat_id)
    except Exception:
        accepted_version = None
    if accepted_version == APP_VERSION:
        _CONSENT_MEM.add(chat_id)
        if len(_CONSENT_MEM) > 5000:
            _CONSENT_MEM.clear()
        return True
    return False


def _record_consent(chat_id: int) -> None:
    _CONSENT_MEM.add(chat_id)
    if not supabase_configured():
        return
    try:
        set_consent(chat_id, APP_VERSION)
    except Exception as exc:
        print(f"Supabase consent write failed: {exc}", file=sys.stderr)


_RATE_MEM: dict[int, float] = {}


def _rate_limit_seconds() -> int:
    try:
        value = int(os.environ.get(RATE_LIMIT_SECONDS_ENV, "60"))
    except ValueError:
        value = 60
    return max(1, value)


def _rate_wait_seconds(subject_id: int) -> int:
    limit = _rate_limit_seconds()
    now = time.time()
    last = _RATE_MEM.get(subject_id)
    if last is not None:
        return max(0, int(math.ceil(limit - (now - last))))
    if supabase_configured():
        try:
            return get_rate_limit_wait(subject_id, limit)
        except Exception:
            pass
    return 0


def _record_rate(subject_id: int) -> None:
    if len(_RATE_MEM) > 5000:
        _RATE_MEM.clear()
    _RATE_MEM[subject_id] = time.time()
    if not supabase_configured():
        return
    try:
        record_rate_limit(subject_id)
    except Exception as exc:
        print(f"Supabase rate write failed: {exc}", file=sys.stderr)


_DAILY_MEM: dict[int, tuple[str, int]] = {}


def _daily_limit() -> int:
    try:
        value = int(os.environ.get(DAILY_LIMIT_ENV, "3"))
    except ValueError:
        value = 3
    return max(1, value)


def _utc_date() -> str:
    return time.strftime("%Y-%m-%d", time.gmtime())


def _daily_used(subject_id: int) -> int:
    today = _utc_date()
    mem = _DAILY_MEM.get(subject_id)
    if mem and mem[0] == today:
        return mem[1]
    if not supabase_configured():
        return 0
    try:
        return get_daily_count(subject_id)
    except Exception:
        return 0


def _daily_remaining(subject_id: int) -> int:
    return max(0, _daily_limit() - _daily_used(subject_id))


def _record_daily(subject_id: int) -> None:
    today = _utc_date()
    used = _daily_used(subject_id) + 1
    if len(_DAILY_MEM) > 5000:
        _DAILY_MEM.clear()
    _DAILY_MEM[subject_id] = (today, used)
    if not supabase_configured():
        return
    try:
        record_daily_usage(subject_id, today, used)
    except Exception as exc:
        print(f"Supabase daily write failed: {exc}", file=sys.stderr)


def _handle_callback(callback: dict) -> None:
    data = callback.get("data") or ""
    callback_id = callback.get("id")
    message = callback.get("message") or {}
    chat_id = (message.get("chat") or {}).get("id")
    user_id = (callback.get("from") or {}).get("id")
    subject_id = user_id or chat_id
    if not callback_id or not chat_id or not subject_id:
        return

    if data == CALLBACK_ACCEPT:
        _record_consent(subject_id)
        _answer_callback(callback_id, "Accepted. Thank you!")
        _edit_message_text(
            chat_id,
            message.get("message_id"),
            f"Accepted - Terms & Privacy confirmed (v{APP_VERSION}).\n\n",
        )
        _send_message(chat_id, _short_start_text(), _main_keyboard())
        return

    if data == CALLBACK_DECLINE:
        _answer_callback(callback_id, "You declined.")
        _edit_message_text(
            chat_id,
            message.get("message_id"),
            "You declined the Terms & Privacy.\n\n"
            "The bot needs your acceptance before it can generate FSC files.\n\n"
            "Send /start to review them again whenever you are ready.",
        )
        return


def _main_keyboard() -> dict:
    return {
        "keyboard": [
            [{"text": "Generate FSC ZIP"}],
            [{"text": "Feature Guide"}, {"text": "1CR Remote Start Guide"}],
            [{"text": "Legal Notice"}, {"text": "Help"}],
        ],
        "resize_keyboard": True,
        "one_time_keyboard": False,
        "input_field_placeholder": "Send 7-character VIN, example TEST123",
    }


def _short_start_text() -> str:
    return (
        "Easy FSC E3 Bot\n"
        f"v{APP_VERSION} - {APP_VERSION_NAME}\n"
        "Free use only. Created by https://t.me/imkadi\n\n"
        "Tap Generate FSC ZIP, then send your 7-character VIN."
    )


def _bot_mode() -> str:
    mode = os.environ.get(OUTPUT_MODE_ENV, "zip").strip().lower()
    return mode if mode in {"zip", "single"} else "zip"


def _build_zip(vin_text: str) -> bytes:
    template = load_template()
    vin = validate_vin(vin_text)
    archive_buffer = io.BytesIO()
    with zipfile.ZipFile(archive_buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for appid in ALL_APPIDS:
            result = build_fsc(template, vin, appid)
            archive.writestr(f"FSC_{vin_text}_{appid:04x}.fsc", result.data)
    return archive_buffer.getvalue()


def _build_single(vin_text: str) -> tuple[str, bytes]:
    appid = parse_appid(os.environ.get(APPID_ENV, f"{DEFAULT_APPID:04X}"))
    result = build_fsc(load_template(), validate_vin(vin_text), appid)
    return f"FSC_{vin_text}_{appid:04x}.fsc", result.data


def _handle_update(update: dict) -> None:
    callback = update.get("callback_query")
    if callback:
        _handle_callback(callback)
        return

    message = update.get("message") or update.get("edited_message")
    if not message:
        return

    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    text = (message.get("text") or "").strip()
    if not chat_id:
        return

    user_id = (message.get("from") or {}).get("id")
    subject_id = user_id or chat_id

    normalized_text = text.lower()

    if not text or normalized_text == "/start":
        if _is_consented(subject_id):
            _send_message(chat_id, _short_start_text(), _main_keyboard())
        else:
            _send_consent_prompt(chat_id)
        return

    if normalized_text in {"/admin", "admin", "/stats", "stats"}:
        if not _is_admin(chat_id):
            _send_message(chat_id, "Admin commands are not available for this chat.", _main_keyboard())
            return
        try:
            stats = get_stats()
        except Exception as exc:
            _send_message(chat_id, f"Admin Reader\n\nStats error: {exc}", _main_keyboard())
            return
        _send_message(
            chat_id,
            "\n".join(
                [
                    "Admin Reader",
                    "",
                    f"Supabase: {'enabled' if stats.get('supabase_configured') else 'not configured'}",
                    f"Total requests: {stats.get('total_requests', 0)}",
                    f"Total FSC files: {stats.get('total_fsc_files', 0)}",
                    f"Unique users: {stats.get('unique_users', 0)}",
                    f"ZIP requests: {stats.get('zip_requests', 0)}",
                    f"Single requests: {stats.get('single_requests', 0)}",
                    f"Last generated: {stats.get('last_generated_at') or 'none'}",
                    "",
                    "Generation DMs are off by default. Set TELEGRAM_ADMIN_DM_LOGS=true to enable them.",
                ]
            ),
            _main_keyboard(),
        )
        return

    if not _is_consented(subject_id):
        _send_consent_prompt(chat_id)
        return

    if normalized_text in {"/help", "help"}:
        _send_message(chat_id, _help_text(), _main_keyboard())
        return

    if normalized_text in {"/features", "features", "feature guide", "app ids", "appids"}:
        _send_message(chat_id, FEATURE_GUIDE, _main_keyboard())
        return

    if normalized_text in {
        "/1cr",
        "/remote_start",
        "1cr",
        "remote start",
        "remote start guide",
        "1cr remote start guide",
    }:
        _send_message(chat_id, REMOTE_START_GUIDE, _main_keyboard())
        return

    if normalized_text in {"/legal", "/terms", "legal", "terms", "legal notice"}:
        _send_message(chat_id, _legal_text(), _main_keyboard())
        return

    if normalized_text in {"generate fsc zip", "generate", "fsc", "zip"}:
        _send_message(
            chat_id,
            "Send the 7-character VIN now, for example TEST123.",
            _main_keyboard(),
        )
        return

    try:
        vin = validate_vin(text).decode("ascii")
    except ValueError as exc:
        _send_message(
            chat_id,
            f"{exc}\n\nSend only the 7-character VIN, for example TEST123.\n\n"
            "Created by https://t.me/imkadi. Free use only, not for resale.",
            _main_keyboard(),
        )
        return

    wait = _rate_wait_seconds(subject_id)
    if wait > 0:
        _send_message(
            chat_id,
            f"Please wait {wait}s before generating another FSC file.\n"
            "Rate limit: 1 generation per minute.\n\n"
            "Created by https://t.me/imkadi. Free use only, not for resale.",
            _main_keyboard(),
        )
        return
    if _daily_remaining(subject_id) <= 0:
        _send_message(
            chat_id,
            f"Daily limit reached: {_daily_limit()} generations per day.\n"
            "Try again tomorrow.\n\n"
            "Created by https://t.me/imkadi. Free use only, not for resale.",
            _main_keyboard(),
        )
        return
    _record_rate(subject_id)
    _record_daily(subject_id)

    try:
        mode = _bot_mode()
        if mode == "single":
            filename, content = _build_single(vin)
            _send_document(
                chat_id,
                filename,
                content,
                f"FSC generated for {vin}\nCreated by https://t.me/imkadi\nFree use only. Not for resale.\nUse only where authorized.",
            )
            try:
                log_generation(vin=vin, mode="single", file_count=1, sent_filename=filename, user_chat_id=chat_id)
            except Exception as exc:
                print(f"Supabase log failed: {exc}", file=sys.stderr)
            try:
                _notify_admin(chat_id, vin, "single", 1, filename)
            except Exception as exc:
                print(f"Admin DM log failed: {exc}", file=sys.stderr)
        else:
            content = _build_zip(vin)
            filename = f"FSC_{vin}_all.zip"
            _send_document(
                chat_id,
                filename,
                content,
                f"Generated {len(ALL_APPIDS)} FSC files for {vin}\nIncludes 1CR Remote Start App IDs 017C and 0180.\nCreated by https://t.me/imkadi\nFree use only. Not for resale.\nUse only where authorized and at your own risk.",
            )
            try:
                log_generation(
                    vin=vin,
                    mode="zip",
                    file_count=len(ALL_APPIDS),
                    sent_filename=filename,
                    user_chat_id=chat_id,
                )
            except Exception as exc:
                print(f"Supabase log failed: {exc}", file=sys.stderr)
            try:
                _notify_admin(chat_id, vin, "zip", len(ALL_APPIDS), filename)
            except Exception as exc:
                print(f"Admin DM log failed: {exc}", file=sys.stderr)
    except Exception as exc:
        _send_message(chat_id, "Generation failed. Please check the VIN and try again.")
        try:
            _notify_admin_error(subject_id, text, exc)
        except Exception as admin_exc:
            print(f"Admin error DM failed: {admin_exc}", file=sys.stderr)


class handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        _json_response(
            self,
            200,
            {
                "ok": True,
                "service": "Easy FSC E3 Telegram bot",
                "telegram_bot_token_configured": bool(os.environ.get(BOT_TOKEN_ENV)),
                "telegram_webhook_secret_configured": bool(os.environ.get(WEBHOOK_SECRET_ENV)),
                "fsc_bot_mode_configured": os.environ.get(OUTPUT_MODE_ENV, "zip"),
                "fsc_bot_mode_effective": _bot_mode(),
                "fsc_rate_limit_seconds": _rate_limit_seconds(),
                "fsc_daily_limit": _daily_limit(),
                "version": APP_VERSION,
                "version_name": APP_VERSION_NAME,
                "admin_reader_configured": bool(_admin_chat_id()),
                "supabase_configured": supabase_configured(),
            },
        )

    def do_POST(self) -> None:
        expected_secret = os.environ.get(WEBHOOK_SECRET_ENV)
        if expected_secret:
            got_secret = self.headers.get("X-Telegram-Bot-Api-Secret-Token")
            if got_secret != expected_secret:
                _json_response(self, 403, {"ok": False, "error": "bad webhook secret"})
                return

        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = self.rfile.read(length)
            update = json.loads(payload.decode("utf-8"))
            _handle_update(update)
            _json_response(self, 200, {"ok": True})
        except (json.JSONDecodeError, urllib.error.URLError, RuntimeError) as exc:
            _json_response(self, 500, {"ok": False, "error": str(exc)})
