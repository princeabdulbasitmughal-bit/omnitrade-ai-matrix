import logging
from typing import Dict, Any, Optional, Tuple, List
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

    def calculate_dynamic_slippage(self, symbol: str, current_price: float, side: str, amount: float, atr: float = 0.0) -> Tuple[float, float]:
        """
        Institutional Dynamic Slippage Model:
        1. Base slippage: Config.SLIPPAGE_PCT (e.g. 0.05% / 5 bps)
        2. Volatility factor: Scales with (ATR / current_price) relative to baseline 1.0% volatility
        3. Market impact / size factor: Non-linear impact scaling with order notional value
        Returns:
            Tuple of (effective_slippage_pct, executed_price)
        """
        base_slippage = Config.SLIPPAGE_PCT

        # 1. Volatility adjustment via ATR
        if atr > 0 and current_price > 0:
            vol_ratio = (atr / current_price) / 0.01  # normalized to 1% baseline
            vol_factor = max(0.5, min(4.0, vol_ratio))
        else:
            vol_factor = 1.0

        # 2. Market impact based on order notional value
        notional_value = amount * current_price
        if notional_value > 25000:
            # High notional size experiences greater order book walk-through
            impact_factor = 1.0 + min(3.0, ((notional_value - 25000) / 75000) ** 0.5 * 0.8)
        elif notional_value > 5000:
            impact_factor = 1.0 + ((notional_value - 5000) / 20000) * 0.25
        else:
            impact_factor = 1.0

        effective_slippage_pct = base_slippage * vol_factor * impact_factor
        effective_slippage_pct = max(0.0001, min(0.01, effective_slippage_pct)) # bounded between 1 bps and 100 bps

        if side.upper() == "BUY":
            executed_price = current_price * (1.0 + effective_slippage_pct)
        else:
            executed_price = current_price * (1.0 - effective_slippage_pct)

        executed_price = round(executed_price, 4 if executed_price > 10 else 6)
        return effective_slippage_pct, executed_price

    def handle_partial_fill(
        self,
        symbol: str,
        order_id: str,
        side: str,
        filled_amount: float,
        fill_price: float,
        remaining_amount: float,
        sl_price: float,
        tp_levels: list,
        reason: str = ""
    ) -> Dict[str, Any]:
        """
        Handles partial fill events from exchange or broker bridge.
        Synchronizes portfolio positions incrementally and records execution receipts.
        """
        if filled_amount <= 0:
            return {"status": "NOOP", "reason": "Filled amount is zero"}

        side = side.upper()
        if symbol in self.portfolio.positions:
            pos = self.portfolio.positions[symbol]
            if pos["side"] == side:
                # Add to existing position with volume-weighted average price (VWAP)
                old_amt = pos["amount"]
                old_entry = pos["entry_price"]
                new_amt = round(old_amt + filled_amount, 6)
                new_entry = round(((old_entry * old_amt) + (fill_price * filled_amount)) / new_amt, 4 if fill_price > 10 else 6)
                
                pos["amount"] = new_amt
                pos["entry_price"] = new_entry
                pos["margin"] = round(new_amt * new_entry, 2)
                pos["sl"] = sl_price
                pos["tp"] = tp_levels
                self.portfolio.save()

                logger.info(f"Partial fill aggregated for {symbol}: added {filled_amount} @ {fill_price}, total: {new_amt} @ {new_entry} (remaining: {remaining_amount})")
                return {
                    "status": "PARTIALLY_FILLED",
                    "symbol": symbol,
                    "order_id": order_id,
                    "filled_amount": filled_amount,
                    "total_position_amount": new_amt,
                    "vwap_entry_price": new_entry,
                    "remaining_amount": remaining_amount
                }
            else:
                logger.warning(f"Partial fill received in opposite direction for {symbol} while holding {pos['side']}.")

        # If no prior position, open with partial filled amount
        res = self.portfolio.open_position(
            symbol=symbol,
            side=side,
            amount=filled_amount,
            entry_price=fill_price,
            sl=sl_price,
            tp=tp_levels,
            reason=f"PARTIAL_FILL_{order_id} | {reason}"
        )
        res["execution_mode"] = "PARTIAL_FILL"
        res["order_id"] = order_id
        res["remaining_amount"] = remaining_amount
        return res

    def emergency_cancel_all(
        self,
        symbol: Optional[str] = None,
        flatten_positions: bool = False,
        current_prices: Optional[Dict[str, float]] = None
    ) -> Dict[str, Any]:
        """
        Institutional Emergency Kill Switch:
        1. Immediately cancels all pending/working orders on live exchange (CCXT)
        2. Optionally flattens all open positions at market prices
        3. Engages the RiskEngine circuit breaker to freeze further trade attempts
        """
        logger.warning(f"EMERGENCY CANCEL-ALL TRIGGERED! (Symbol filter: {symbol or 'ALL'}, Flatten: {flatten_positions})")
        cancelled_exchange_orders = []
        exchange_errors = []

        # 1. Cancel exchange live open orders
        if self.exchange:
            try:
                if hasattr(self.exchange, "cancel_all_orders"):
                    try:
                        res = self.exchange.cancel_all_orders(symbol=symbol)
                        cancelled_exchange_orders.append({"action": "cancel_all_orders", "result": res})
                    except Exception as e:
                        logger.warning(f"cancel_all_orders failed, falling back to cancel_order loop: {e}")
                
                # Fallback: query open orders and cancel one-by-one
                if hasattr(self.exchange, "fetch_open_orders"):
                    open_orders = self.exchange.fetch_open_orders(symbol=symbol)
                    for ord_item in open_orders:
                        ord_id = ord_item.get("id")
                        ord_sym = ord_item.get("symbol", symbol)
                        if ord_id:
                            try:
                                c_res = self.exchange.cancel_order(ord_id, ord_sym)
                                cancelled_exchange_orders.append({"order_id": ord_id, "symbol": ord_sym, "result": c_res})
                            except Exception as c_err:
                                exchange_errors.append(f"Failed to cancel order {ord_id}: {c_err}")
            except Exception as e:
                exchange_errors.append(f"Exchange order cancellation exception: {e}")

        # 2. Optionally flatten active portfolio positions
        flattened_trades = []
        if flatten_positions:
            prices = current_prices or {}
            target_symbols = [symbol] if symbol and symbol in self.portfolio.positions else list(self.portfolio.positions.keys())
            for sym in target_symbols:
                exit_price = prices.get(sym, self.portfolio.positions[sym].get("current_price", self.portfolio.positions[sym].get("entry_price", 0.0)))
                closed = self.portfolio.close_position(sym, exit_price=exit_price, exit_reason="EMERGENCY_KILL_SWITCH_FLATTEN")
                if closed:
                    flattened_trades.append(closed)

        # 3. Trip Risk Engine Circuit Breaker
        self.risk_engine.is_circuit_broken = True

        report = {
            "status": "EMERGENCY_CANCEL_ALL_COMPLETED",
            "circuit_breaker_active": True,
            "cancelled_exchange_orders": cancelled_exchange_orders,
            "flattened_positions": flattened_trades,
            "exchange_errors": exchange_errors,
            "timestamp": Config.DATA_DIR.name
        }
        logger.info(f"Emergency cancel-all completed. {len(cancelled_exchange_orders)} orders cancelled, {len(flattened_trades)} positions flattened.")
        return report

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

        # Apply institutional dynamic execution slippage
        effective_slippage_pct, executed_price = self.calculate_dynamic_slippage(
            symbol=symbol,
            current_price=current_price,
            side=side,
            amount=amount,
            atr=atr
        )

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
            res["slippage_applied_pct"] = round(effective_slippage_pct * 100, 4)
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

                    # Extract real fill price and filled quantity from exchange response
                    actual_fill_price = float(order.get("average") or order.get("price") or executed_price)
                    filled_qty = float(order.get("filled") if order.get("filled") is not None else amount)
                    remaining_qty = float(order.get("remaining", 0.0) or 0.0)
                    order_status = order.get("status", "closed")

                    # Handle partial fills gracefully
                    if filled_qty < amount and filled_qty > 0:
                        logger.warning(f"Live exchange order {order.get('id')} partially filled: {filled_qty}/{amount}")
                        return self.handle_partial_fill(
                            symbol=symbol,
                            order_id=str(order.get("id")),
                            side=side,
                            filled_amount=filled_qty,
                            fill_price=actual_fill_price,
                            remaining_amount=remaining_qty,
                            sl_price=sl_price,
                            tp_levels=tp_levels,
                            reason=f"LIVE_EXCHANGE_PARTIAL_{order.get('id')} | {reason}"
                        )

                    res = self.portfolio.open_position(
                        symbol=symbol,
                        side=side,
                        amount=filled_qty if filled_qty > 0 else amount,
                        entry_price=actual_fill_price,
                        sl=sl_price,
                        tp=tp_levels,
                        reason=f"LIVE_EXCHANGE_ID_{order.get('id')} | {reason}"
                    )
                    res["execution_mode"] = "LIVE"
                    res["exchange_order_id"] = order.get("id")
                    res["actual_fill_price"] = actual_fill_price
                    res["order_status"] = order_status
                    return res
                else:
                    logger.error("Live exchange instance not configured. Falling back to paper.")
                    return {"status": "ERROR", "reason": "Exchange client not initialized"}
            except Exception as e:
                logger.error(f"Live exchange execution failed: {e}")
                return {"status": "FAILED", "reason": str(e)}

    def close_trade(self, symbol: str, current_price: float, reason: str = "MANUAL_CLOSE") -> Optional[Dict[str, Any]]:
        return self.portfolio.close_position(symbol, current_price, exit_reason=reason)
