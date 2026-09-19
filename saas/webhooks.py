import logging
from typing import Dict, Any

logger = logging.getLogger("OmniTrade.Webhooks")

class WebhookManager:
    @staticmethod
    def process_tradingview_alert(payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parses incoming TradingView Pine Script webhook alert JSON:
        Example payload:
        {
          "ticker": "BTCUSDT",
          "action": "BUY" | "SELL",
          "price": 96500,
          "strategy": "SuperTrend_Scalp",
          "secret": "my_secret_token"
        }
        """
        raw_ticker = payload.get("ticker", "BTC/USDT")
        action = payload.get("action", "BUY").upper()
        price = float(payload.get("price", 0.0))
        strategy = payload.get("strategy", "TradingView_External_Alert")

        # Normalize ticker
        if "/" not in raw_ticker:
            if raw_ticker.endswith("USDT"):
                symbol = raw_ticker.replace("USDT", "/USDT")
            elif raw_ticker.endswith("USD"):
                symbol = raw_ticker.replace("USD", "/USD")
            else:
                symbol = raw_ticker
        else:
            symbol = raw_ticker

        logger.info(f"Processed TradingView Webhook: {action} {symbol} @ ${price:.2f} [{strategy}]")
        return {
            "symbol": symbol,
            "action": action,
            "price": price,
            "strategy": strategy,
            "source": "TRADINGVIEW_WEBHOOK"
        }

    @staticmethod
    def process_mt5_bridge_event(payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parses incoming MetaTrader 5 (MT5) EA Bridge alert JSON.
        """
        symbol = payload.get("symbol", "XAU/USD")
        action = payload.get("cmd", "BUY").upper()
        price = float(payload.get("price", 0.0))
        volume = float(payload.get("volume", 0.1))

        logger.info(f"Processed MT5 Bridge Alert: {action} {symbol} ({volume} lots) @ ${price:.2f}")
        return {
            "symbol": symbol,
            "action": action,
            "price": price,
            "volume": volume,
            "source": "MT5_EA_BRIDGE"
        }
