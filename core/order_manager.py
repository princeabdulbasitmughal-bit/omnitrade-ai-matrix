import logging
from typing import Dict, Any, Optional
from config.settings import Config
from core.portfolio import Portfolio
from core.risk_engine import RiskEngine

logger = logging.getLogger("OmniTrade.OrderManager")

class OrderManager:
    def __init__(self, portfolio: Portfolio, risk_engine: RiskEngine, ccxt_exchange=None):
        self.portfolio = portfolio
        self.risk_engine = risk_engine
        self.exchange = ccxt_exchange
        self.mode = Config.TRADING_MODE  # 'paper' or 'live'

    def set_mode(self, mode: str):
        if mode in ["paper", "live"]:
            self.mode = mode
            logger.info(f"OrderManager mode switched to: {self.mode.upper()}")

    def execute_signal(self, symbol: str, signal: str, current_price: float, atr: float, reason: str = "") -> Dict[str, Any]:
        """
        Executes BUY or SELL order based on AI consensus signal.
        Handles risk verification, position sizing, SL/TP calculation, and execution in Paper or Live mode.
        """
        if self.risk_engine.check_circuit_breaker()[0]:
            return {"status": "BLOCKED", "reason": "Circuit breaker active"}

        if signal not in ["BUY", "STRONG_BUY", "SELL", "STRONG_SELL"]:
            return {"status": "IGNORED", "reason": f"Signal is {signal}"}

        side = "BUY" if "BUY" in signal else "SELL"

        # If already holding a position in opposite direction, close it first
        if symbol in self.portfolio.positions:
            existing_side = self.portfolio.positions[symbol]["side"]
            if existing_side != side:
                logger.info(f"Reversing position for {symbol}: Closing {existing_side} before opening {side}")
                self.portfolio.close_position(symbol, current_price, exit_reason="SIGNAL_REVERSAL")
            else:
                logger.debug(f"Position already open in direction {side} for {symbol}. Skipping redundant entry.")
                return {"status": "ALREADY_OPEN", "reason": f"Already holding {side} for {symbol}"}

        # Calculate SL and TP
        sl_price, tp_levels = self.risk_engine.calculate_sl_tp(side, current_price, atr)

        # Calculate Position Size
        amount = self.risk_engine.calculate_position_size(symbol, current_price, sl_price, atr)
        if amount <= 0:
            return {"status": "REJECTED", "reason": "Calculated position size is 0 (insufficient capital or extreme risk)"}

        # Apply realistic execution slippage
        executed_price = current_price * (1 + Config.SLIPPAGE_PCT) if side == "BUY" else current_price * (1 - Config.SLIPPAGE_PCT)
        executed_price = round(executed_price, 4 if executed_price > 10 else 6)

        if self.mode == "paper":
            res = self.portfolio.open_position(
                symbol=symbol,
                side=side,
                amount=amount,
                entry_price=executed_price,
                sl=sl_price,
                tp=tp_levels,
                reason=reason
            )
            res["execution_mode"] = "PAPER"
            return res
        else:
            # Live Execution via CCXT
            logger.info(f"LIVE EXECUTION: Sending {side} order to exchange for {symbol} ({amount} units)")
            try:
                if self.exchange:
                    order = self.exchange.create_order(
                        symbol=symbol,
                        type="market",
                        side=side.lower(),
                        amount=amount
                    )
                    logger.info(f"Live exchange order placed successfully: {order.get('id')}")
                    res = self.portfolio.open_position(
                        symbol=symbol,
                        side=side,
                        amount=amount,
                        entry_price=executed_price,
                        sl=sl_price,
                        tp=tp_levels,
                        reason=f"LIVE_EXCHANGE_ID_{order.get('id')} | {reason}"
                    )
                    res["execution_mode"] = "LIVE"
                    res["exchange_order_id"] = order.get("id")
                    return res
                else:
                    logger.error("Live exchange instance not configured. Falling back to paper.")
                    return {"status": "ERROR", "reason": "Exchange client not initialized"}
            except Exception as e:
                logger.error(f"Live exchange execution failed: {e}")
                return {"status": "FAILED", "reason": str(e)}

    def close_trade(self, symbol: str, current_price: float, reason: str = "MANUAL_CLOSE") -> Optional[Dict[str, Any]]:
        return self.portfolio.close_position(symbol, current_price, exit_reason=reason)
