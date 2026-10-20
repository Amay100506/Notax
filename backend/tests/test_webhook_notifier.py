"""
Unit tests for NotifyIQ External Webhook Notifier (Telegram & Discord).
"""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from backend.database.connection import init_db
from backend.database.repository import Repository
from backend.utils.configuration import settings
from backend.utils.webhook_notifier import WebhookNotifier


@pytest.fixture
def notifier(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        test_db = Path(tmpdir) / "test_webhook.db"
        monkeypatch.setattr(settings, "db_path", str(test_db))
        init_db()
        repo = Repository()
        yield WebhookNotifier(repository=repo)


def test_save_and_get_webhook_config(notifier):
    notifier.save_config(
        telegram_bot_token="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
        telegram_chat_id="987654321",
        discord_webhook_url="https://discord.com/api/webhooks/123/xyz",
        webhooks_enabled=True,
    )

    cfg = notifier.get_config()
    assert cfg["telegram_bot_token"] == "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
    assert cfg["telegram_chat_id"] == "987654321"
    assert cfg["discord_webhook_url"] == "https://discord.com/api/webhooks/123/xyz"
    assert cfg["webhooks_enabled"] is True


def test_send_telegram_alert_disabled_returns_false(notifier):
    # Disabled by default
    res = notifier.notify_urgent_alert("Title", "Body", 90.0)
    assert res is False


def test_send_telegram_alert_success(notifier):
    notifier.save_config(
        telegram_bot_token="test_token",
        telegram_chat_id="test_chat_id",
        webhooks_enabled=True,
    )

    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.__enter__.return_value = mock_resp

    with patch("urllib.request.urlopen", return_value=mock_resp):
        res = notifier.send_telegram_alert("Test message")
        assert res is True


def test_send_discord_alert_success(notifier):
    notifier.save_config(
        discord_webhook_url="https://discord.com/api/webhooks/test",
        webhooks_enabled=True,
    )

    mock_resp = MagicMock()
    mock_resp.status = 204
    mock_resp.__enter__.return_value = mock_resp

    with patch("urllib.request.urlopen", return_value=mock_resp):
        res = notifier.send_discord_alert("Test message")
        assert res is True
