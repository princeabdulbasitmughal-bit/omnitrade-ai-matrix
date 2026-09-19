import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional
from config.settings import Config

logger = logging.getLogger("OmniTrade.Portfolio")

class Portfolio:
    def __init__(self, initial_balance: float = None, storage_path: Path = None):
        self.storage_path = storage_path or (Config.DATA_DIR / "portfolio.json")
        self.initial_balance = initial_balance or Config.INITIAL_PAPER_BALANCE
        self.cash = self.initial_balance
        self.equity = self.initial_balance
        self.peak_equity = self.initial_balance
        self.daily_start_equity = self.initial_balance
        self.daily_date = datetime.utcnow().strftime("%Y-%m-%d")

        self.positions: Dict[str, Dict[str, Any]] = {} # symbol -> position dict
        self.trade_history: List[Dict[str, Any]] = []
        self.orders: List[Dict[str, Any]] = []

        self._load()

    def _load(self):
        if self.storage_path.exists():
            try:
                with open(self.storage_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.cash = data.get("cash", self.initial_balance)
                    self.equity = data.get("equity", self.cash)
                    self.peak_equity = data.get("peak_equity", self.equity)
                    self.daily_start_equity = data.get("daily_start_equity", self.equity)
                    self.daily_date = data.get("daily_date", datetime.utcnow().strftime("%Y-%m-%d"))
                    self.positions = data.get("positions", {})
                    self.trade_history = data.get("trade_history", [])
                    self.orders = data.get("orders", [])
                logger.info(f"Loaded portfolio state. Equity: ${self.equity:.2f}, Cash: ${self.cash:.2f}")
            except Exception as e:
                logger.error(f"Error loading portfolio: {e}")

    def save(self):
        try:
            today = datetime.utcnow().strftime("%Y-%m-%d")
            if today != self.daily_date:
                self.daily_date = today
                self.daily_start_equity = self.equity

            data = {
                "cash": self.cash,
                "equity": self.equity,
                "peak_equity": self.peak_equity,
                "daily_start_equity": self.daily_start_equity,
                "daily_date": self.daily_date,
                "positions": self.positions,
                "trade_history": self.trade_history[-200:], # keep latest 200
                "orders": self.orders[-100:],
                "updated_at": datetime.utcnow().isoformat(),
            }
            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving portfolio: {e}")

    def update_market_prices(self, current_prices: Dict[str, float]):
        """Updates unrealized PnL and total account equity based on current market prices."""
        unrealized_pnl = 0.0
        for symbol, pos in list(self.positions.items()):
            price = current_prices.get(symbol, pos.get("entry_price", 0.0))
            pos["current_price"] = price
            side = pos.get("side", "BUY")
            amount = pos.get("amount", 0.0)
            entry_price = pos.get("entry_price", price)

            if side == "BUY":
                pnl = (price - entry_price) * amount
                pnl_pct = ((price - entry_price) / entry_price) * 100 if entry_price > 0 else 0
            else: # SELL / SHORT
                pnl = (entry_price - price) * amount
                pnl_pct = ((entry_price - price) / entry_price) * 100 if entry_price > 0 else 0

            pos["unrealized_pnl"] = round(pnl, 2)
            pos["unrealized_pnl_pct"] = round(pnl_pct, 2)
            unrealized_pnl += pnl

        self.equity = round(self.cash + sum(pos.get("margin", pos.get("amount", 0) * pos.get("entry_price", 0)) for pos in self.positions.values()) + unrealized_pnl, 2)
        if self.equity > self.peak_equity:
            self.peak_equity = self.equity

    def open_position(self, symbol: str, side: str, amount: float, entry_price: float, sl: float, tp: list, reason: str = "") -> Dict[str, Any]:
        cost = amount * entry_price
        fee = cost * Config.TAKER_FEE_PCT
        total_required = cost + fee

        if total_required > self.cash:
            logger.warning(f"Insufficient cash ${self.cash:.2f} for required ${total_required:.2f}")
            return {"status": "REJECTED", "reason": "Insufficient cash"}

        self.cash -= total_required
        pos_id = f"pos_{int(datetime.utcnow().timestamp() * 1000)}"
        position = {
            "id": pos_id,
            "symbol": symbol,
            "side": side,
            "amount": amount,
            "entry_price": entry_price,
            "current_price": entry_price,
            "margin": cost,
            "sl": sl,
            "tp": tp if isinstance(tp, list) else [tp],
            "highest_price": entry_price if side == "BUY" else entry_price,
            "lowest_price": entry_price if side == "SELL" else entry_price,
            "unrealized_pnl": 0.0,
            "unrealized_pnl_pct": 0.0,
            "opened_at": datetime.utcnow().isoformat(),
            "reason": reason,
        }
        self.positions[symbol] = position
        self.save()
        logger.info(f"Opened {side} position for {symbol}: {amount} units @ ${entry_price:.2f} (SL: ${sl:.2f})")
        return {"status": "OPENED", "position": position}

    def close_position(self, symbol: str, exit_price: float, exit_reason: str = "MANUAL") -> Optional[Dict[str, Any]]:
        if symbol not in self.positions:
            return None

        pos = self.positions.pop(symbol)
        side = pos["side"]
        amount = pos["amount"]
        entry_price = pos["entry_price"]
        gross_return = amount * exit_price
        fee = gross_return * Config.TAKER_FEE_PCT

        if side == "BUY":
            pnl = (exit_price - entry_price) * amount - fee
            pnl_pct = ((exit_price - entry_price) / entry_price) * 100
        else:
            pnl = (entry_price - exit_price) * amount - fee
            pnl_pct = ((entry_price - exit_price) / entry_price) * 100

        returned_cash = pos["margin"] + pnl
        self.cash += max(0, returned_cash)
        self.equity = self.cash + sum(p.get("margin", 0) for p in self.positions.values())

        trade_record = {
            "id": pos["id"],
            "symbol": symbol,
            "side": side,
            "amount": amount,
            "entry_price": entry_price,
            "exit_price": exit_price,
            "pnl": round(pnl, 2),
            "pnl_pct": round(pnl_pct, 2),
            "opened_at": pos["opened_at"],
            "closed_at": datetime.utcnow().isoformat(),
            "exit_reason": exit_reason,
            "open_reason": pos.get("reason", ""),
        }
        self.trade_history.append(trade_record)
        self.save()
        logger.info(f"Closed {side} position for {symbol} @ ${exit_price:.2f}. PnL: ${pnl:.2f} ({pnl_pct:+.2f}%) [{exit_reason}]")
        return trade_record

    def partial_close_position(self, symbol: str, exit_price: float, close_pct: float = 0.33, exit_reason: str = "PARTIAL_TP") -> Optional[Dict[str, Any]]:
        if symbol not in self.positions:
            return None

        pos = self.positions[symbol]
        side = pos["side"]
        close_amount = round(pos["amount"] * close_pct, 4)
        if close_amount <= 0 or close_amount >= pos["amount"]:
            return self.close_position(symbol, exit_price, exit_reason)

        entry_price = pos["entry_price"]
        gross_return = close_amount * exit_price
        fee = gross_return * Config.TAKER_FEE_PCT

        if side == "BUY":
            pnl = (exit_price - entry_price) * close_amount - fee
            pnl_pct = ((exit_price - entry_price) / entry_price) * 100
        else:
            pnl = (entry_price - exit_price) * close_amount - fee
            pnl_pct = ((entry_price - exit_price) / entry_price) * 100

        pos["amount"] = round(pos["amount"] - close_amount, 4)
        pos["margin"] = round(pos["amount"] * entry_price, 2)

        released_margin = close_amount * entry_price
        self.cash += round(released_margin + pnl, 2)
        self.equity = round(self.cash + sum(p.get("margin", 0) for p in self.positions.values()), 2)

        trade_record = {
            "id": f"part_{pos['id']}_{int(datetime.utcnow().timestamp())}",
            "symbol": symbol,
            "side": side,
            "amount": close_amount,
            "entry_price": entry_price,
            "exit_price": exit_price,
            "pnl": round(pnl, 2),
            "pnl_pct": round(pnl_pct, 2),
            "opened_at": pos["opened_at"],
            "closed_at": datetime.utcnow().isoformat(),
            "exit_reason": exit_reason,
            "open_reason": pos.get("reason", ""),
        }
        self.trade_history.append(trade_record)
        self.save()
        logger.info(f"Partial Close {side} for {symbol}: {close_amount} units @ ${exit_price:.2f}. PnL: ${pnl:.2f} ({pnl_pct:+.2f}%) [{exit_reason}]")
        return trade_record

    def get_summary(self) -> Dict[str, Any]:
        """Calculates performance metrics including win rate, profit factor, max drawdown."""
        trades = self.trade_history
        wins = [t for t in trades if t["pnl"] > 0]
        losses = [t for t in trades if t["pnl"] < 0]

        total_trades = len(trades)
        win_rate = (len(wins) / total_trades * 100) if total_trades > 0 else 0.0
        total_pnl = sum(t["pnl"] for t in trades)
        total_pnl_pct = ((self.equity - self.initial_balance) / self.initial_balance) * 100

        gross_profit = sum(t["pnl"] for t in wins)
        gross_loss = abs(sum(t["pnl"] for t in losses))
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (99.9 if gross_profit > 0 else 1.0)

        # Max drawdown from peak
        drawdown_pct = ((self.peak_equity - self.equity) / self.peak_equity * 100) if self.peak_equity > 0 else 0.0

        # Daily drawdown
        daily_dd_pct = ((self.daily_start_equity - self.equity) / self.daily_start_equity * 100) if self.daily_start_equity > 0 else 0.0

        return {
            "cash": round(self.cash, 2),
            "equity": round(self.equity, 2),
            "initial_balance": round(self.initial_balance, 2),
            "total_pnl": round(total_pnl, 2),
            "total_pnl_pct": round(total_pnl_pct, 2),
            "total_trades": total_trades,
            "wins": len(wins),
            "losses": len(losses),
            "win_rate": round(win_rate, 2),
            "profit_factor": round(profit_factor, 2),
            "max_drawdown_pct": round(drawdown_pct, 2),
            "daily_drawdown_pct": round(daily_dd_pct, 2),
            "open_positions_count": len(self.positions),
            "open_positions": list(self.positions.values()),
            "recent_trades": self.trade_history[-15:],
        }
