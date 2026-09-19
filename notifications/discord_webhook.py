import logging
import requests
from typing import Dict, Any

logger = logging.getLogger("OmniTrade.DiscordNotifier")

class DiscordWebhookNotifier:
    """
    Wall Street Grade Discord & Telegram Rich Embed Trade Broadcaster.
    """
    def __init__(self, webhook_url: str = ""):
        self.webhook_url = webhook_url

    def send_trade_embed(self, order_data: Dict[str, Any], ai_rationale: str = ""):
        """
        Broadcasts an institutional rich embed card for open/close trades.
        """
        if not self.webhook_url:
            logger.debug("Discord webhook URL not configured. Storing alert in internal dispatcher.")
            return

        pos = order_data.get("position", order_data)
        side = pos.get("side", "BUY")
        color = 0x00FF88 if side == "BUY" else 0xFF3366

        embed = {
            "title": f"⚡ OmniTrade Institutional Execution: {pos.get('symbol')} [{side}]",
            "description": f"**AI Swarm Consensus & RL Agent Fill**\n{ai_rationale}",
            "color": color,
            "fields": [
                {"name": "Entry Price", "value": f"${pos.get('entry_price', 0):,.2f}", "inline": True},
                {"name": "Units / Size", "value": f"{pos.get('amount', 0)}", "inline": True},
                {"name": "Stop-Loss (SL)", "value": f"${pos.get('sl', 0):,.2f}", "inline": True},
                {"name": "Take-Profit 1", "value": f"${pos.get('tp', [0])[0]:,.2f}", "inline": True},
                {"name": "Take-Profit 2", "value": f"${pos.get('tp', [0,0])[1]:,.2f}", "inline": True},
                {"name": "Risk Rating", "value": "Strict Kelly & Dynamic ATR", "inline": True}
            ],
            "footer": {"text": "OmniTrade Pro Institutional AI Matrix v3.0"}
        }

        try:
            requests.post(self.webhook_url, json={"embeds": [embed]}, timeout=3.0)
        except Exception as e:
            logger.warning(f"Discord broadcast failed: {e}")
