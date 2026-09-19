import logging
import requests
import subprocess
from typing import Dict, Any
from config.settings import Config

logger = logging.getLogger("OmniTrade.AlertDispatcher")

class AlertDispatcher:
    def __init__(self):
        self.telegram_token = Config.TELEGRAM_BOT_TOKEN
        self.telegram_chat_id = Config.TELEGRAM_CHAT_ID
        self.whatsapp_enabled = Config.WHATSAPP_ENABLED
        self.alert_phone = Config.ALERT_PHONE

    def send_trade_alert(self, order_event: Dict[str, Any], ai_rationale: str = ""):
        """Dispatches real-time alert via Telegram and WhatsApp."""
        pos = order_event.get("position", {})
        symbol = pos.get("symbol", "N/A")
        side = pos.get("side", "BUY")
        price = pos.get("entry_price", 0.0)
        sl = pos.get("sl", 0.0)
        tps = pos.get("tp", [])
        amount = pos.get("amount", 0.0)

        tp_str = ", ".join([f"${t:.2f}" for t in tps]) if tps else "N/A"

        msg = (
            f"⚡ *OmniTrade AI Matrix — New Trade Execution*\n\n"
            f"🔹 *Asset*: `{symbol}`\n"
            f"🎯 *Action*: *{side}* ({amount} units)\n"
            f"💵 *Entry Price*: `${price:.2f}`\n"
            f"🛡️ *Stop-Loss*: `${sl:.2f}`\n"
            f"🚀 *Take-Profit Targets*: `{tp_str}`\n"
            f"🤖 *AI Swarm Thesis*: _{ai_rationale}_\n"
            f"⚙️ *Mode*: `{order_event.get('execution_mode', 'PAPER')}`"
        )

        self._send_telegram(msg)
        if self.whatsapp_enabled and self.alert_phone:
            self._send_whatsapp(msg)

    def _send_telegram(self, text: str):
        if not self.telegram_token or not self.telegram_chat_id:
            logger.debug("Telegram credentials not configured.")
            return

        try:
            url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
            payload = {
                "chat_id": self.telegram_chat_id,
                "text": text,
                "parse_mode": "Markdown"
            }
            requests.post(url, json=payload, timeout=5)
            logger.info("Telegram trade alert dispatched.")
        except Exception as e:
            logger.error(f"Failed to send Telegram alert: {e}")

    def _send_whatsapp(self, text: str):
        try:
            # Invokes local WhatsApp shortcut if available
            subprocess.run(
                ["wa", "--phone", self.alert_phone, "--message", text],
                capture_output=True,
                timeout=10,
                shell=True
            )
            logger.info("WhatsApp trade alert dispatched.")
        except Exception as e:
            logger.debug(f"WhatsApp alert error: {e}")
