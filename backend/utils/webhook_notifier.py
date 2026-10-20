"""
External Webhook Notification Dispatcher for NotifyIQ.
Dispatches high-priority security alerts, critical deadline reminders,
and shopping price-drop notifications to Telegram Bots or Discord Webhooks.
"""

import json
import urllib.request
import urllib.parse
from typing import Optional
from backend.utils.logging_config import logger
from backend.database.repository import Repository


class WebhookNotifier:
    def __init__(self, repository: Optional[Repository] = None):
        self.repo = repository or Repository()

    def get_config(self) -> dict:
        """Retrieves active webhook configuration from SQLite settings."""
        return {
            "telegram_bot_token": self.repo.get_setting("telegram_bot_token") or "",
            "telegram_chat_id": self.repo.get_setting("telegram_chat_id") or "",
            "discord_webhook_url": self.repo.get_setting("discord_webhook_url") or "",
            "webhooks_enabled": (self.repo.get_setting("webhooks_enabled") or "false").lower() == "true",
        }

    def save_config(
        self,
        telegram_bot_token: Optional[str] = None,
        telegram_chat_id: Optional[str] = None,
        discord_webhook_url: Optional[str] = None,
        webhooks_enabled: Optional[bool] = None,
    ):
        """Persists webhook parameters in SQLite settings table."""
        if telegram_bot_token is not None:
            self.repo.set_setting("telegram_bot_token", telegram_bot_token.strip())
        if telegram_chat_id is not None:
            self.repo.set_setting("telegram_chat_id", telegram_chat_id.strip())
        if discord_webhook_url is not None:
            self.repo.set_setting("discord_webhook_url", discord_webhook_url.strip())
        if webhooks_enabled is not None:
            self.repo.set_setting("webhooks_enabled", "true" if webhooks_enabled else "false")

    def send_telegram_alert(self, text: str) -> bool:
        """Sends a message to configured Telegram chat via Bot API."""
        cfg = self.get_config()
        token = cfg["telegram_bot_token"]
        chat_id = cfg["telegram_chat_id"]

        if not token or not chat_id:
            return False

        try:
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            payload = json.dumps({"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}).encode("utf-8")
            req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                return resp.status == 200
        except Exception as e:
            logger.warning("Telegram webhook dispatch failed: %s", str(e))
            return False

    def send_discord_alert(self, content: str) -> bool:
        """Posts a message to configured Discord webhook channel."""
        cfg = self.get_config()
        webhook_url = cfg["discord_webhook_url"]

        if not webhook_url:
            return False

        try:
            payload = json.dumps({"content": content}).encode("utf-8")
            req = urllib.request.Request(
                webhook_url,
                data=payload,
                headers={"Content-Type": "application/json", "User-Agent": "NotifyIQ-Notifier/1.0"}
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                return resp.status in (200, 204)
        except Exception as e:
            logger.warning("Discord webhook dispatch failed: %s", str(e))
            return False

    def notify_urgent_alert(self, title: str, text: str, priority_score: float) -> bool:
        """Dispatches an urgent alert notification across all active channels."""
        cfg = self.get_config()
        if not cfg["webhooks_enabled"]:
            return False

        msg = (
            f"🚨 *NotifyIQ Urgent Alert!* (Priority: `{priority_score:.1f}`/100)\n\n"
            f"*Title:* {title}\n"
            f"*Details:* {text}\n\n"
            f"_[View in NotifyIQ Smart Inbox]_"
        )
        sent_tg = self.send_telegram_alert(msg)
        sent_dc = self.send_discord_alert(msg)
        return sent_tg or sent_dc

    def notify_price_drop(
        self,
        product_title: str,
        current_price: float,
        drop_percent: float,
        target_price: Optional[float] = None,
    ) -> bool:
        """Dispatches a price drop alert across all active channels."""
        cfg = self.get_config()
        if not cfg["webhooks_enabled"]:
            return False

        target_note = f" (Target: ₹{target_price:.0f})" if target_price else ""
        msg = (
            f"🎉 *NotifyIQ Price Drop Detected!*\n\n"
            f"📦 *Product:* {product_title}\n"
            f"💰 *New Price:* ₹{current_price:,.0f} (-{drop_percent:.0f}% OFF){target_note}\n\n"
            f"_[Open NotifyIQ or Amazon to grab the deal]_"
        )
        sent_tg = self.send_telegram_alert(msg)
        sent_dc = self.send_discord_alert(msg)
        return sent_tg or sent_dc
