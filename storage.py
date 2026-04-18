"""
Dual-mode persistence: local files (dev) or Supabase (cloud).
Local: history.json, content_plan.json, generated_images/
Cloud: Supabase PostgreSQL + Storage bucket 'post-images'
"""
import os
import json
from pathlib import Path
from datetime import datetime
from typing import Optional

HISTORY_FILE = Path(__file__).parent / "history.json"
PLAN_FILE    = Path(__file__).parent / "content_plan.json"
OUTPUT_DIR   = Path(__file__).parent / "generated_images"
OUTPUT_DIR.mkdir(exist_ok=True)

_supabase_client = None
_supabase_checked = False


def _get_supabase():
    global _supabase_client, _supabase_checked
    if _supabase_checked:
        return _supabase_client
    _supabase_checked = True
    url = os.getenv("SUPABASE_URL", "")
    key = os.getenv("SUPABASE_KEY", "")
    if url and key:
        try:
            from supabase import create_client
            _supabase_client = create_client(url, key)
        except Exception:
            _supabase_client = None
    return _supabase_client


def _is_cloud() -> bool:
    return _get_supabase() is not None


# ─────────────────────────── HISTORY ───────────────────────────

def load_history() -> list:
    sb = _get_supabase()
    if sb:
        try:
            result = sb.table("post_history").select("*").order("created_at", desc=True).limit(100).execute()
            rows = result.data or []
            # Normalize: Supabase uses post_text/image_url, app uses text/image_path
            for row in rows:
                row.setdefault("text", row.get("post_text", ""))
                row.setdefault("image_path", row.get("image_url", ""))
            return rows
        except Exception:
            pass
    if HISTORY_FILE.exists():
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def save_to_history(topic: str, platform: str, platform_label: str,
                    platform_icon: str, notebook_name: str, post_text: str) -> str:
    entry_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    sb = _get_supabase()
    if sb:
        try:
            sb.table("post_history").insert({
                "id": entry_id,
                "date": datetime.now().strftime("%d.%m.%Y %H:%M"),
                "topic": topic,
                "platform": platform,
                "platform_label": platform_label,
                "platform_icon": platform_icon,
                "notebook": notebook_name,
                "post_text": post_text,
                "image_url": "",
            }).execute()
            return entry_id
        except Exception:
            pass
    # Local fallback
    history = load_history()
    history.insert(0, {
        "id": entry_id,
        "date": datetime.now().strftime("%d.%m.%Y %H:%M"),
        "topic": topic,
        "platform": platform_label,
        "platform_icon": platform_icon,
        "notebook": notebook_name,
        "text": post_text,
        "image_path": "",
    })
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history[:100], f, ensure_ascii=False, indent=2)
    return entry_id


def update_history_image(image_url: str, entry_id: Optional[str] = None):
    sb = _get_supabase()
    if sb:
        try:
            if entry_id:
                sb.table("post_history").update({"image_url": image_url}).eq("id", entry_id).execute()
            return
        except Exception:
            pass
    # Local fallback
    history = load_history()
    if not history:
        return
    if entry_id:
        for entry in history:
            if entry.get("id") == entry_id:
                entry["image_path"] = image_url
                break
    else:
        history[0]["image_path"] = image_url
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history[:100], f, ensure_ascii=False, indent=2)


def clear_history():
    sb = _get_supabase()
    if sb:
        try:
            sb.table("post_history").delete().neq("id", "").execute()
            return
        except Exception:
            pass
    HISTORY_FILE.unlink(missing_ok=True)


# ─────────────────────────── CONTENT PLAN ───────────────────────────

def load_plan_data() -> list:
    sb = _get_supabase()
    if sb:
        try:
            result = sb.table("content_plans").select("plan_data").eq("id", "current").execute()
            if result.data:
                return result.data[0].get("plan_data") or []
        except Exception:
            pass
    if PLAN_FILE.exists():
        with open(PLAN_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def save_plan_data(plan: list):
    sb = _get_supabase()
    if sb:
        try:
            sb.table("content_plans").upsert({"id": "current", "plan_data": plan}).execute()
            return
        except Exception:
            pass
    with open(PLAN_FILE, "w", encoding="utf-8") as f:
        json.dump(plan, f, ensure_ascii=False, indent=2)


# ─────────────────────────── IMAGES ───────────────────────────

def save_and_upload_image(image, topic: str) -> str:
    """Save image locally, upload to Supabase Storage if available. Returns URL or local path."""
    from image_generator import save_image
    local_path = save_image(image, topic)

    sb = _get_supabase()
    if sb:
        try:
            filename = local_path.name
            with open(local_path, "rb") as f:
                sb.storage.from_("post-images").upload(
                    filename, f, {"content-type": "image/jpeg"}
                )
            url = sb.storage.from_("post-images").get_public_url(filename)
            return url
        except Exception:
            pass
    return str(local_path)


def load_image_bytes(path_or_url: str) -> bytes:
    """Load image bytes from local path or URL."""
    if path_or_url.startswith("http"):
        import requests
        return requests.get(path_or_url, timeout=15).content
    with open(path_or_url, "rb") as f:
        return f.read()


def image_exists(path_or_url: str) -> bool:
    """Check if image is accessible (local file or URL)."""
    if not path_or_url:
        return False
    if path_or_url.startswith("http"):
        return True
    return Path(path_or_url).exists()
