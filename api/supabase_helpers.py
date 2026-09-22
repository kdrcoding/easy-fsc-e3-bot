from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request


SUPABASE_URL_ENV = "SUPABASE_URL"
SUPABASE_SECRET_KEY_ENV = "SUPABASE_SECRET_KEY"
SUPABASE_SERVICE_ROLE_KEY_ENV = "SUPABASE_SERVICE_ROLE_KEY"
SUPABASE_LOG_TABLE = "fsc_generation_logs"
SUPABASE_STATS_VIEW = "fsc_generation_stats"


def _config() -> tuple[str, str] | None:
    url = os.environ.get(SUPABASE_URL_ENV, "").strip().rstrip("/")
    key = (
        os.environ.get(SUPABASE_SERVICE_ROLE_KEY_ENV, "").strip()
        or os.environ.get(SUPABASE_SECRET_KEY_ENV, "").strip()
    )
    if not url or not key:
        return None
    return url, key


def supabase_configured() -> bool:
    return _config() is not None


def _request(path: str, method: str = "GET", body: dict | None = None) -> tuple[int, bytes]:
    config = _config()
    if not config:
        raise RuntimeError("Supabase is not configured")
    url, key = config
    data = json.dumps(body).encode("utf-8") if body is not None else None
    request = urllib.request.Request(f"{url}/rest/v1/{path}", data=data, method=method)
    request.add_header("apikey", key)
    request.add_header("Authorization", f"Bearer {key}")
    request.add_header("Content-Type", "application/json")
    if method == "POST":
        request.add_header("Prefer", "return=minimal")
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Supabase HTTP {exc.code}: {error_body or exc.reason}") from exc


def log_generation(
    *,
    vin: str,
    mode: str,
    file_count: int,
    sent_filename: str,
    user_chat_id: int,
) -> bool:
    if not supabase_configured():
        return False
    payload = {
        "vin": vin,
        "mode": mode,
        "file_count": file_count,
        "sent_filename": sent_filename,
        "user_chat_id": str(user_chat_id),
    }
    _request(SUPABASE_LOG_TABLE, method="POST", body=payload)
    return True


def get_stats() -> dict:
    if not supabase_configured():
        return {
            "ok": True,
            "supabase_configured": False,
            "total_requests": 0,
            "total_fsc_files": 0,
            "unique_users": 0,
            "zip_requests": 0,
            "single_requests": 0,
            "last_generated_at": None,
        }

    query = urllib.parse.urlencode({"select": "*", "limit": "1"})
    _status, body = _request(f"{SUPABASE_STATS_VIEW}?{query}")
    if not body:
        raise RuntimeError(
            "Supabase returned an empty response. Check SUPABASE_URL and use a service_role key, not the database password."
        )
    decoded_body = body.decode("utf-8", errors="replace")
    try:
        rows = json.loads(decoded_body)
    except json.JSONDecodeError as exc:
        preview = decoded_body[:500]
        raise RuntimeError(
            "Supabase returned non-JSON for stats. "
            f"Response preview: {preview!r}. "
            "Use SUPABASE_SERVICE_ROLE_KEY from Supabase Project Settings > API/API Keys."
        ) from exc
    stats = rows[0] if rows else {}
    return {
        "ok": True,
        "supabase_configured": True,
        "total_requests": int(stats.get("total_requests") or 0),
        "total_fsc_files": int(stats.get("total_fsc_files") or 0),
        "unique_users": int(stats.get("unique_users") or 0),
        "zip_requests": int(stats.get("zip_requests") or 0),
        "single_requests": int(stats.get("single_requests") or 0),
        "last_generated_at": stats.get("last_generated_at"),
    }
