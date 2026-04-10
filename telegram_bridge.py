"""
Jarvis Telegram Bridge — remote control via Telegram bot.

Setup (.env):
  TELEGRAM_BOT_TOKEN=<token from @BotFather>
  TELEGRAM_ALLOWED_ID=<your numeric ID from @userinfobot>
"""

import logging
import os
import queue
import threading
import time

import httpx

logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)

TELEGRAM_TOKEN      = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_ALLOWED_ID = os.getenv("TELEGRAM_ALLOWED_ID", "")
BASE_URL            = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"


def _allowed_ids() -> set[int]:
    if not TELEGRAM_ALLOWED_ID:
        return set()
    try:
        return {int(x.strip()) for x in TELEGRAM_ALLOWED_ID.split(",") if x.strip()}
    except ValueError:
        return set()


class TelegramBridge:
    def __init__(self):
        self.enabled  = bool(TELEGRAM_TOKEN)
        self._queue   = None
        self._allowed = _allowed_ids()
        self._client  = httpx.Client(timeout=35)

    def start(self, msg_queue: queue.Queue, reply_callback=None):
        if not self.enabled:
            return
        self._queue = msg_queue
        threading.Thread(target=self._poll_loop, daemon=True, name="TelegramBridge").start()

    def send(self, chat_id: int, text: str):
        """Send a reply back to Telegram (blocking, called from main thread)."""
        try:
            self._client.post(f"{BASE_URL}/sendMessage", json={
                "chat_id": chat_id,
                "text": text[:4096],
            })
        except Exception as e:
            print(f"\n  [Telegram] Send error: {e}")

    def _poll_loop(self):
        offset = 0
        _error_shown = False
        while True:
            try:
                r = self._client.get(f"{BASE_URL}/getUpdates", params={
                    "offset": offset,
                    "timeout": 25,
                    "allowed_updates": ["message"],
                })
                data = r.json()
                _error_shown = False   # connected — reset error flag
                if not data.get("ok"):
                    time.sleep(3)
                    continue

                for update in data.get("result", []):
                    offset = update["update_id"] + 1
                    msg = update.get("message", {})
                    text = (msg.get("text") or "").strip()
                    if not text:
                        continue
                    user_id = msg.get("from", {}).get("id")
                    chat_id = msg.get("chat", {}).get("id")

                    if self._allowed and user_id not in self._allowed:
                        self.send(chat_id, "Unauthorized.")
                        continue

                    self.send(chat_id, "⏳ On it, sir...")
                    self._queue.put((text, chat_id))

            except httpx.ReadTimeout:
                continue   # normal — no messages in 25s window
            except Exception:
                time.sleep(30)   # retry silently every 30s
