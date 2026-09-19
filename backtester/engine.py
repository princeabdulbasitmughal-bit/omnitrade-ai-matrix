import logging
import pandas as pd
import numpy as np
from typing import Dict, Any, List
from strategies.indicators import TechnicalIndicators
from strategies.smart_money_concepts import SmartMoneyConcepts
from backtester.metrics import PerformanceMetrics
from config.settings import Config

logger = logging.getLogger("OmniTrade.Backtester")

class BacktestEngine:
    def __init__(self, initial_capital: float = 10000.0, fee_pct: float = 0.00075, slippage_pct: float = 0.0005):
        self.initial_capital = initial_capital
        self.fee_pct = fee_pct
        self.slippage_pct = slippage_pct

    def run(self, df: pd.DataFrame, symbol: str = "BTC/USDT") -> Dict[str, Any]:
        """
        Executes backtest on historical OHLCV data.
        Combines EMA trend alignment, RSI momentum, SuperTrend, and Smart Money Concepts.
        """
        if df.empty or len(df) < 30:
            return {"error": "Insufficient historical data for backtesting"}

        df_calc = TechnicalIndicators.compute_all(df)
        trades: List[Dict[str, Any]] = []

        capital = self.initial_capital
        position = None  # None or dict

        for i in range(20, len(df_calc)):
            current_bar = df_calc.iloc[i]
            prev_bar = df_calc.iloc[i - 1]
            close = float(current_bar["close"])
            high = float(current_bar["high"])
            low = float(current_bar["low"])
            atr = float(current_bar["atr"])
            timestamp = str(current_bar["timestamp"])

            # 1. If in position, check SL, TP, or Trailing Stop
            if position:
                side = position["side"]
                entry_price = position["entry_price"]
                sl = position["sl"]
                tp = position["tp"]
                amount = position["amount"]

                if side == "BUY":
                    # Check Stop Loss
                    if low <= sl:
                        exit_p = sl * (1 - self.slippage_pct)
                        pnl = (exit_p - entry_price) * amount - (exit_p * amount * self.fee_pct)
                        pnl_pct = ((exit_p - entry_price) / entry_price) * 100
                        capital += (entry_price * amount) + pnl
                        trades.append({
                            "symbol": symbol,
                            "side": "BUY",
                            "entry_price": entry_price,
                            "exit_price": exit_p,
                            "pnl": round(pnl, 2),
                            "pnl_pct": round(pnl_pct, 2),
                            "exit_reason": "STOP_LOSS",
                            "timestamp": timestamp
                        })
                        position = None
                        continue

                    # Check Take Profit
                    elif high >= tp:
                        exit_p = tp * (1 - self.slippage_pct)
                        pnl = (exit_p - entry_price) * amount - (exit_p * amount * self.fee_pct)
                        pnl_pct = ((exit_p - entry_price) / entry_price) * 100
                        capital += (entry_price * amount) + pnl
                        trades.append({
                            "symbol": symbol,
                            "side": "BUY",
                            "entry_price": entry_price,
                            "exit_price": exit_p,
                            "pnl": round(pnl, 2),
                            "pnl_pct": round(pnl_pct, 2),
                            "exit_reason": "TAKE_PROFIT",
                            "timestamp": timestamp
                        })
                        position = None
                        continue

                    # Trailing Stop adjust
                    if high > position.get("highest_price", entry_price):
                        position["highest_price"] = high
                        if high >= entry_price + (1.5 * atr):
                            new_sl = high - (1.5 * atr)
                            if new_sl > sl:
                                position["sl"] = new_sl

                elif side == "SELL":
                    # Check Stop Loss
                    if high >= sl:
                        exit_p = sl * (1 + self.slippage_pct)
                        pnl = (entry_price - exit_p) * amount - (exit_p * amount * self.fee_pct)
                        pnl_pct = ((entry_price - exit_p) / entry_price) * 100
                        capital += (entry_price * amount) + pnl
                        trades.append({
                            "symbol": symbol,
                            "side": "SELL",
                            "entry_price": entry_price,
                            "exit_price": exit_p,
                            "pnl": round(pnl, 2),
                            "pnl_pct": round(pnl_pct, 2),
                            "exit_reason": "STOP_LOSS",
                            "timestamp": timestamp
                        })
                        position = None
                        continue

                    # Check Take Profit
                    elif low <= tp:
                        exit_p = tp * (1 + self.slippage_pct)
                        pnl = (entry_price - exit_p) * amount - (exit_p * amount * self.fee_pct)
                        pnl_pct = ((entry_price - exit_p) / entry_price) * 100
                        capital += (entry_price * amount) + pnl
                        trades.append({
                            "symbol": symbol,
                            "side": "SELL",
                            "entry_price": entry_price,
                            "exit_price": exit_p,
                            "pnl": round(pnl, 2),
                            "pnl_pct": round(pnl_pct, 2),
                            "exit_reason": "TAKE_PROFIT",
                            "timestamp": timestamp
                        })
                        position = None
                        continue

            # 2. If no position, evaluate entry conditions
            if not position and capital > 500:
                rsi = current_bar["rsi"]
                super_bull = current_bar["supertrend_dir"]
                macd_hist = current_bar["macd_hist"]
                ema_20 = current_bar["ema_20"]
                ema_50 = current_bar["ema_50"]

                # Buy Condition: SuperTrend Bullish + MACD Hist > 0 + EMA20 > EMA50 + RSI between 45 and 68
                if super_bull and macd_hist > 0 and ema_20 > ema_50 and 42 < rsi < 70:
                    entry_p = close * (1 + self.slippage_pct)
                    sl_dist = 1.5 * atr
                    sl_p = entry_p - sl_dist
                    tp_p = entry_p + (2.5 * sl_dist) # 1:2.5 Risk-to-Reward

                    risk_amount = capital * 0.015 # Risk 1.5% of capital
                    amount = risk_amount / sl_dist
                    max_alloc = (capital * 0.3) / entry_p
                    amount = min(amount, max_alloc)

                    cost = amount * entry_p
                    fee = cost * self.fee_pct
                    if capital >= cost + fee:
                        capital -= (cost + fee)
                        position = {
                            "side": "BUY",
                            "entry_price": entry_p,
                            "sl": sl_p,
                            "tp": tp_p,
                            "amount": amount,
                            "highest_price": entry_p,
                            "timestamp": timestamp
                        }

                # Sell/Short Condition: SuperTrend Bearish + MACD Hist < 0 + EMA20 < EMA50 + RSI between 30 and 58
                elif not super_bull and macd_hist < 0 and ema_20 < ema_50 and 30 < rsi < 58:
                    entry_p = close * (1 - self.slippage_pct)
                    sl_dist = 1.5 * atr
                    sl_p = entry_p + sl_dist
                    tp_p = entry_p - (2.5 * sl_dist)

                    risk_amount = capital * 0.015
                    amount = risk_amount / sl_dist
                    max_alloc = (capital * 0.3) / entry_p
                    amount = min(amount, max_alloc)

                    cost = amount * entry_p
                    fee = cost * self.fee_pct
                    if capital >= cost + fee:
                        capital -= (cost + fee)
                        position = {
                            "side": "SELL",
                            "entry_price": entry_p,
                            "sl": sl_p,
                            "tp": tp_p,
                            "amount": amount,
                            "lowest_price": entry_p,
                            "timestamp": timestamp
                        }

        # Close any lingering position at final bar
        if position:
            last_bar = df_calc.iloc[-1]
            last_close = float(last_bar["close"])
            side = position["side"]
            entry_price = position["entry_price"]
            amount = position["amount"]
            pnl = (last_close - entry_price) * amount if side == "BUY" else (entry_price - last_close) * amount
            trades.append({
                "symbol": symbol,
                "side": side,
                "entry_price": entry_price,
                "exit_price": last_close,
                "pnl": round(pnl, 2),
                "pnl_pct": round(((last_close - entry_price) / entry_price * 100), 2) if side == "BUY" else round(((entry_price - last_close) / entry_price * 100), 2),
                "exit_reason": "BACKTEST_END",
                "timestamp": str(last_bar["timestamp"])
            })

        metrics = PerformanceMetrics.calculate(trades, initial_capital=self.initial_capital)
        metrics["symbol"] = symbol
        metrics["bars_analyzed"] = len(df_calc)
        metrics["trades_list"] = trades
        return metrics
