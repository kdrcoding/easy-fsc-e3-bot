import json
import os
import sys
import traceback
from http.server import BaseHTTPRequestHandler
from pathlib import Path


API_DIR = Path(__file__).resolve().parent
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))

class handler(BaseHTTPRequestHandler):
    def _send(self, status: int, body: dict) -> None:
        payload = json.dumps(body, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self) -> None:
        try:
            from supabase_helpers import get_stats

            body = get_stats()
        except Exception as exc:
            self._send(
                200,
                {
                    "ok": False,
                    "error": str(exc),
                    "error_type": type(exc).__name__,
                    "trace": traceback.format_exc(limit=3),
                    "env": {
                        "SUPABASE_URL_set": bool(os.environ.get("SUPABASE_URL")),
                        "SUPABASE_SECRET_KEY_set": bool(os.environ.get("SUPABASE_SECRET_KEY")),
                        "SUPABASE_SERVICE_ROLE_KEY_set": bool(os.environ.get("SUPABASE_SERVICE_ROLE_KEY")),
                    },
                    "hint": "Check SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY/SUPABASE_SECRET_KEY, and run supabase_schema.sql.",
                },
            )
            return

        self._send(200, body)
