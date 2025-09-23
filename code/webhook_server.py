import os
import hmac
import hashlib
import sys
import subprocess
import threading
import time
from fastapi import FastAPI, Request, Header, HTTPException
from fastapi.responses import JSONResponse

app = FastAPI(title="Interview Chatbot Webhook Server")

# Simple health check
@app.get("/healthz")
async def healthz():
    return {"ok": True}


def verify_daily_signature(secret: str, body: bytes, signature_header: str | None) -> bool:
    if not secret:
        return True  # signature disabled if no secret
    if not signature_header:
        return False
    try:
        # Daily sends hex digest HMAC SHA256 of raw body using the shared secret
        digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
        # Constant-time compare
        return hmac.compare_digest(digest, signature_header)
    except Exception:
        return False


# Track active launches per room to avoid duplicate concurrent runs
_active_rooms: dict[str, float] = {}
_lock = threading.Lock()


def _extract_room_info(payload: dict) -> tuple[str | None, str | None]:
    """Try to extract (room_url, room_name) from multiple Daily payload shapes."""
    if not isinstance(payload, dict):
        return None, None
    # Common top-level keys
    room_url = payload.get("room_url") or payload.get("roomUrl") or payload.get("url")
    room_name = payload.get("room_name") or payload.get("roomName") or payload.get("room")

    # Daily sometimes nests under 'payload' or 'data'
    nested = payload.get("payload") or payload.get("data") or {}
    if not room_url:
        room_url = nested.get("room_url") or nested.get("roomUrl") or nested.get("url")
    if not room_name:
        room_name = nested.get("room_name") or nested.get("roomName") or nested.get("room")

    # Derive room_name from URL path if missing
    try:
        if not room_name and room_url:
            from urllib.parse import urlparse
            path = urlparse(room_url).path or ""
            room_name = path.strip("/") or None
    except Exception:
        pass

    return room_url, room_name


def _launch_bot(room_url: str, room_name: str) -> None:
    """Spawn main.py in background and stream output to stdout prefix."""
    python_exec = sys.executable or "python"
    main_path = os.path.join(os.path.dirname(__file__), "main.py")
    print(f"[webhook] launching bot: {python_exec} -u {main_path} {room_url} {room_name}")
    proc = subprocess.Popen(
        [python_exec, "-u", main_path, room_url, room_name],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        cwd=os.path.dirname(__file__),
    )

    def _stream():
        try:
            if proc.stdout is not None:
                for line in iter(proc.stdout.readline, ''):
                    if not line:
                        break
                    print(f"[BOT-{room_name}] {line.rstrip()}")
            proc.wait()
            print(f"[BOT-{room_name}] exited with code {proc.returncode}")
        except Exception as e:
            print(f"[BOT-{room_name}] stream error: {e}")
        finally:
            with _lock:
                _active_rooms.pop(room_name, None)

    t = threading.Thread(target=_stream, daemon=True)
    t.start()


@app.post("/webhooks/daily")
async def daily_webhook(request: Request, x_daily_signature: str | None = Header(default=None, alias="X-Daily-Signature")):
    # Read raw body first so we can verify signature
    raw = await request.body()

    secret = os.getenv("DAILY_WEBHOOK_SECRET", "").strip()
    if secret:
        ok = verify_daily_signature(secret, raw, x_daily_signature)
        if not ok:
            raise HTTPException(status_code=400, detail="invalid signature")

    # Parse JSON body safely (Daily may send a test payload on webhook creation)
    try:
        payload = await request.json()
    except Exception:
        payload = {}

    # Log minimal info (stdout)
    event = payload.get("event") or payload.get("type") or "unknown"
    room_url, room_name = _extract_room_info(payload)
    print(f"[webhook] event={event} room_url={room_url} room_name={room_name}")

    # If we have room details, attempt to launch the bot once per room concurrently
    launched = False
    if room_url and room_name:
        with _lock:
            # Clear stale entries after 6 hours
            now = time.time()
            for r, ts in list(_active_rooms.items()):
                if now - ts > 6 * 3600:
                    _active_rooms.pop(r, None)
            if room_name not in _active_rooms:
                _active_rooms[room_name] = now
                launched = True
        if launched:
            threading.Thread(target=_launch_bot, args=(room_url, room_name), daemon=True).start()
        else:
            print(f"[webhook] bot already active for room={room_name}, skipping re-launch")

    # Always return 200 quickly so Daily accepts the webhook
    return JSONResponse(status_code=200, content={"ok": True, "launched": launched, "room": room_name, "event": event})
