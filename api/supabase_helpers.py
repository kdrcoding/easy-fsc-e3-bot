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
SUPABASE_DAILY_STATS_VIEW = "fsc_generation_daily_stats"
SUPABASE_CONSENT_TABLE = "user_consents"
SUPABASE_RATE_TABLE = "fsc_rate_limits"
SUPABASE_DAILY_VINS_TABLE = "fsc_daily_vins"


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


def _request(
    path: str,
    method: str = "GET",
    body: dict | None = None,
    prefer: str | None = None,
) -> tuple[int, bytes]:
    config = _config()
    if not config:
        raise RuntimeError("Supabase is not configured")
    url, key = config
    data = json.dumps(body).encode("utf-8") if body is not None else None
    request = urllib.request.Request(f"{url}/rest/v1/{path}", data=data, method=method)
    request.add_header("apikey", key)
    request.add_header("Authorization", f"Bearer {key}")
    request.add_header("Content-Type", "application/json")
    if prefer:
        request.add_header("Prefer", prefer)
    elif method == "POST":
        request.add_header("Prefer", "return=minimal")
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Supabase HTTP {exc.code}: {error_body or exc.reason}") from exc


def _get_json(path: str):
    _status, body = _request(path)
    if not body:
        return []
    decoded_body = body.decode("utf-8", errors="replace")
    try:
        return json.loads(decoded_body)
    except json.JSONDecodeError as exc:
        preview = decoded_body[:500]
        raise RuntimeError(
            "Supabase returned non-JSON. "
            f"Response preview: {preview!r}. "
            "Use SUPABASE_SERVICE_ROLE_KEY from Supabase Project Settings > API/API Keys."
        ) from exc


def get_consent(user_chat_id: int) -> str | None:
    if not supabase_configured():
        return None
    query = urllib.parse.urlencode(
        {
            "select": "accepted_version",
            "user_chat_id": f"eq.{user_chat_id}",
            "limit": "1",
        }
    )
    rows = _get_json(f"{SUPABASE_CONSENT_TABLE}?{query}")
    if not rows:
        return None
    return rows[0].get("accepted_version")


def set_consent(user_chat_id: int, accepted_version: str) -> bool:
    if not supabase_configured():
        return False
    payload = {
        "user_chat_id": str(user_chat_id),
        "accepted_version": accepted_version,
    }
    _request(
        SUPABASE_CONSENT_TABLE,
        method="POST",
        body=payload,
        prefer="resolution=merge-duplicates,return=minimal",
    )
    return True


def get_rate_limit_wait(user_chat_id: int, limit_seconds: int) -> int:
    query = urllib.parse.urlencode(
        {
            "select": "last_generated_at",
            "user_chat_id": f"eq.{user_chat_id}",
            "limit": "1",
        }
    )
    rows = _get_json(f"{SUPABASE_RATE_TABLE}?{query}")
    if not rows:
        return 0
    raw = rows[0].get("last_generated_at")
    if not raw:
        return 0
    from datetime import datetime, timezone

    last = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    elapsed = (datetime.now(timezone.utc) - last).total_seconds()
    remaining = limit_seconds - elapsed
    if remaining <= 0:
        return 0
    return int(remaining) + 1


def record_rate_limit(user_chat_id: int) -> bool:
    if not supabase_configured():
        return False
    from datetime import datetime, timezone

    payload = {
        "user_chat_id": str(user_chat_id),
        "last_generated_at": datetime.now(timezone.utc).isoformat(),
    }
    _request(
        SUPABASE_RATE_TABLE,
        method="POST",
        body=payload,
        prefer="resolution=merge-duplicates,return=minimal",
    )
    return True


def get_daily_vins(user_chat_id: int) -> list[str]:
    from datetime import datetime, timezone

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    query = urllib.parse.urlencode(
        {
            "select": "vin",
            "user_chat_id": f"eq.{user_chat_id}",
            "used_on": f"eq.{today}",
            "limit": "10000",
        }
    )
    rows = _get_json(f"{SUPABASE_DAILY_VINS_TABLE}?{query}")
    return [str(row.get("vin")) for row in rows if row.get("vin")]


def record_daily_vin(user_chat_id: int, used_on: str, vin: str) -> bool:
    if not supabase_configured():
        return False
    payload = {
        "user_chat_id": str(user_chat_id),
        "used_on": used_on,
        "vin": vin,
    }
    _request(
        SUPABASE_DAILY_VINS_TABLE,
        method="POST",
        body=payload,
        prefer="resolution=merge-duplicates,return=minimal",
    )
    return True


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
            "recent_generations": [],
            "daily": [],
        }

    query = urllib.parse.urlencode({"select": "*", "limit": "1"})
    rows = _get_json(f"{SUPABASE_STATS_VIEW}?{query}")
    stats = rows[0] if rows else {}
    recent_query = urllib.parse.urlencode(
        {
            "select": "created_at,vin,mode,file_count,sent_filename,user_chat_id",
            "order": "created_at.desc",
            "limit": "10",
        }
    )
    daily_query = urllib.parse.urlencode({"select": "*", "order": "day.desc", "limit": "14"})
    recent = _get_json(f"{SUPABASE_LOG_TABLE}?{recent_query}")
    try:
        daily = _get_json(f"{SUPABASE_DAILY_STATS_VIEW}?{daily_query}")
    except RuntimeError:
        daily = []
    return {
        "ok": True,
        "supabase_configured": True,
        "total_requests": int(stats.get("total_requests") or 0),
        "total_fsc_files": int(stats.get("total_fsc_files") or 0),
        "unique_users": int(stats.get("unique_users") or 0),
        "zip_requests": int(stats.get("zip_requests") or 0),
        "single_requests": int(stats.get("single_requests") or 0),
        "last_generated_at": stats.get("last_generated_at"),
        "recent_generations": recent,
        "daily": daily,
    }
