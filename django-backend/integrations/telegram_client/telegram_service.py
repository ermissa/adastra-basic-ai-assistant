"""
Telegram Bot Service for Adastra Telecenter

This service provides functionality to send notifications about ongoing calls
and finalized orders to customers via Telegram during the MVP phase.
"""

import logging
from typing import Optional, List, Union

from django.conf import settings
from telegram import Bot

logger = logging.getLogger(__name__)


class TelegramService:
    def __init__(self):
        self.bot_token = settings.TELEGRAM_BOT_TOKEN
        self.default_chat_ids = self._parse_chat_ids(settings.TELEGRAM_CHAT_IDS)
        self.bot = Bot(token=self.bot_token)

        if not self.bot_token:
            logger.debug("Telegram bot token not configured")
        if not self.default_chat_ids:
            logger.debug("Telegram chat ID not configured")

    def _parse_chat_ids(self, chat_id_setting: str) -> List[str]:
        """Parse chat ID setting which can be a single ID or comma-separated list"""
        if not chat_id_setting:
            return []

        # Split by comma and strip whitespace
        chat_ids = [chat_id.strip() for chat_id in chat_id_setting.split(",")]
        return [chat_id for chat_id in chat_ids if chat_id]

    async def send_message(self, text: str) -> bool:
        success_count = 0
        for chat_id in self.default_chat_ids:
            try:
                await self.bot.send_message(chat_id=chat_id, text=text)
                success_count += 1
            except Exception as e:
                logger.debug(f"Error sending Telegram message to {chat_id}: {e}")

        return success_count > 0
