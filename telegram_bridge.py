"""
Jarvis Telegram Bridge
─────────────────────
Runs a Telegram bot in a background thread. Messages from your Telegram chat
are injected into the same msg_queue that the terminal uses, so Jarvis handles
them identically. Replies are sent back to Telegram.

Setup:
  1. Message @BotFather on Telegram → /newbot → copy the token
  2. Add TELEGRAM_BOT_TOKEN=<token> to your .env
  3. Add TELEGRAM_ALLOWED_ID=<your numeric user ID> to your .env
     (get your ID by messaging @userinfobot on Telegram)

Usage once running:
  Send any message to your bot → Jarvis processes it → replies back.
  Slash commands (/help, /skill, etc.) work the same as in terminal.
"""

import asyncio
import logging
import os
import queue
import threading

logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telegram").setLevel(logging.WARNING)

TELEGRAM_TOKEN      = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_ALLOWED_ID = os.getenv("TELEGRAM_ALLOWED_ID", "")   # comma-separated IDs


def _parse_allowed_ids() -> set[int]:
    if not TELEGRAM_ALLOWED_ID:
        return set()
    try:
        return {int(x.strip()) for x in TELEGRAM_ALLOWED_ID.split(",") if x.strip()}
    except ValueError:
        return set()


class TelegramBridge:
    """
    Spawns a background thread that runs the Telegram bot event loop.
    Call start(msg_queue, reply_callback) to begin.

      msg_queue      — same queue the terminal uses; bridge puts text in it
      reply_callback — callable(chat_id, text) to send a reply back
    """

    def __init__(self):
        self._app       = None
        self._thread    = None
        self._loop      = None
        self._queue     = None
        self._reply_cb  = None
        self._allowed   = _parse_allowed_ids()
        self.enabled    = bool(TELEGRAM_TOKEN)

    def start(self, msg_queue: queue.Queue, reply_callback):
        if not self.enabled:
            return
        self._queue    = msg_queue
        self._reply_cb = reply_callback
        self._thread   = threading.Thread(
            target=self._run_loop, daemon=True, name="TelegramBridge"
        )
        self._thread.start()

    def send(self, chat_id: int, text: str):
        """Push a reply to a Telegram chat (thread-safe via asyncio.run_coroutine_threadsafe)."""
        if self._app and self._loop:
            asyncio.run_coroutine_threadsafe(
                self._app.bot.send_message(chat_id=chat_id, text=text),
                self._loop,
            )

    # ── Internal ─────────────────────────────────────────────────────────────
    def _run_loop(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._loop.run_until_complete(self._start_bot())

    async def _start_bot(self):
        from telegram import Update
        from telegram.ext import Application, MessageHandler, filters, ContextTypes

        self._app = Application.builder().token(TELEGRAM_TOKEN).build()

        async def on_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
            user_id = update.effective_user.id
            chat_id = update.effective_chat.id
            text    = (update.message.text or "").strip()

            if not text:
                return

            # Access control
            if self._allowed and user_id not in self._allowed:
                await update.message.reply_text("Unauthorized.")
                return

            # Acknowledge receipt
            await update.message.reply_text("⏳ On it, sir...")

            # Inject into Jarvis queue — reply_callback sends the response back
            self._queue.put((text, chat_id))

        self._app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_message))

        await self._app.initialize()
        await self._app.start()
        await self._app.updater.start_polling(drop_pending_updates=True)

        # Keep running until the thread is killed (daemon)
        import asyncio as _a
        while True:
            await _a.sleep(1)
