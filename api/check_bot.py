from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler


def _send(handler: BaseHTTPRequestHandler, status: int, body: dict) -> None:
    payload = json.dumps(body).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(payload)))
    handler.end_headers()
    handler.wfile.write(payload)


class handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        token = os.environ.get("TELEGRAM_BOT_TOKEN")
        if not token:
            _send(self, 200, {"ok": False, "error": "TELEGRAM_BOT_TOKEN is missing"})
            return

        url = f"https://api.telegram.org/bot{token}/getMe"
        try:
            with urllib.request.urlopen(url, timeout=15) as response:
                data = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            try:
                error_body = exc.read().decode("utf-8")
            except Exception:
                error_body = str(exc)
            _send(
                self,
                200,
                {
                    "ok": False,
                    "telegram_http_status": exc.code,
                    "telegram_error": error_body,
                },
            )
            return
        except Exception as exc:
            _send(self, 200, {"ok": False, "error": str(exc)})
            return

        result = data.get("result") or {}
        _send(
            self,
            200,
            {
                "ok": bool(data.get("ok")),
                "bot_id": result.get("id"),
                "username": result.get("username"),
                "first_name": result.get("first_name"),
            },
        )
