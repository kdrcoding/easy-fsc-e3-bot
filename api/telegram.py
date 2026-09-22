from __future__ import annotations

import io
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from http.server import BaseHTTPRequestHandler
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fsc_core import ALL_APPIDS, DEFAULT_APPID, build_fsc, load_template, parse_appid, validate_vin


BOT_TOKEN_ENV = "TELEGRAM_BOT_TOKEN"
WEBHOOK_SECRET_ENV = "TELEGRAM_WEBHOOK_SECRET"
OUTPUT_MODE_ENV = "FSC_BOT_MODE"
APPID_ENV = "FSC_BOT_APPID"


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


def _send_message(chat_id: int, text: str) -> None:
    _telegram_api(
        "sendMessage",
        {
            "chat_id": str(chat_id),
            "text": text,
            "disable_web_page_preview": "true",
        },
    )


def _send_document(chat_id: int, filename: str, content: bytes, caption: str) -> None:
    _telegram_api(
        "sendDocument",
        {"chat_id": str(chat_id), "caption": caption},
        {"document": (filename, content)},
    )


def _help_text() -> str:
    return (
        "Easy FSC E3 Bot\n\n"
        "Send your 7-character VIN, for example:\n"
        "TEST123\n\n"
        "The bot will generate FSC files and send them back.\n\n"
        "Created by https://t.me/imkadi\n"
        "Free use only. Not for resale.\n\n"
        "Use only with systems and files you own or have permission to service."
    )


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
    message = update.get("message") or update.get("edited_message")
    if not message:
        return

    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    text = (message.get("text") or "").strip()
    if not chat_id:
        return

    if not text or text.lower() in {"/start", "/help"}:
        _send_message(chat_id, _help_text())
        return

    try:
        vin = validate_vin(text).decode("ascii")
    except ValueError as exc:
        _send_message(chat_id, f"{exc}\n\nSend only the 7-character VIN.")
        return

    try:
        mode = os.environ.get(OUTPUT_MODE_ENV, "zip").strip().lower()
        if mode == "single":
            filename, content = _build_single(vin)
            _send_document(
                chat_id,
                filename,
                content,
                f"FSC generated for {vin}\nCreated by https://t.me/imkadi\nFree use only.",
            )
        else:
            content = _build_zip(vin)
            _send_document(
                chat_id,
                f"FSC_{vin}_all.zip",
                content,
                f"Generated {len(ALL_APPIDS)} FSC files for {vin}\nCreated by https://t.me/imkadi\nFree use only.",
            )
    except Exception:
        _send_message(chat_id, "Generation failed. Please check the VIN and try again.")
        raise


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
                "fsc_bot_mode": os.environ.get(OUTPUT_MODE_ENV, "zip"),
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
