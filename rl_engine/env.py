import numpy as np
import pandas as pd
from typing import Dict, Any, Tuple
from strategies.indicators import TechnicalIndicators

class TradingEnvironment:
    """
    OpenAI Gym-style reinforcement learning trading environment.
    State space: 12 normalized features (Returns, RSI, MACD, BB %B, ATR %, SuperTrend, VWAP distance, Volume Delta, Position State).
    Action space: 0 = HOLD, 1 = BUY / LONG, 2 = SELL / SHORT
    """
    def __init__(self, df: pd.DataFrame, initial_balance: float = 10000.0, fee_pct: float = 0.00075):
        self.df = TechnicalIndicators.compute_all(df)
        self.initial_balance = initial_balance
        self.fee_pct = fee_pct
        self.reset()

    def reset(self) -> np.ndarray:
        self.current_step = 20
        self.balance = self.initial_balance
        self.position = 0 # -1 = Short, 0 = Flat, 1 = Long
        self.entry_price = 0.0
        self.position_size = 0.0
        self.peak_balance = self.initial_balance
        self.trades = []
        return self._get_state()

    def _get_state(self) -> np.ndarray:
        row = self.df.iloc[self.current_step]
        close = float(row["close"])
        
        # 12 Normalized state features
        ret_1 = float((close - self.df["close"].iloc[self.current_step - 1]) / self.df["close"].iloc[self.current_step - 1])
        ret_5 = float((close - self.df["close"].iloc[self.current_step - 5]) / self.df["close"].iloc[self.current_step - 5])
        rsi_norm = (float(row.get("rsi", 50)) - 50.0) / 50.0
        macd_norm = float(row.get("macd_hist", 0)) / (close * 0.01) if close > 0 else 0
        bb_pct = float(row.get("bb_pct", 0.5)) - 0.5
        atr_norm = float(row.get("atr", 0)) / close if close > 0 else 0
        st_dir = 1.0 if row.get("supertrend_dir", True) else -1.0
        vwap_dist = (close - float(row.get("vwap", close))) / close if close > 0 else 0
        vol_norm = float(row.get("volume", 1)) / float(self.df["volume"].iloc[self.current_step-10:self.current_step].mean() + 1e-5)
        
        # Position states
        pos_state = float(self.position)
        unrealized_pnl = ((close - self.entry_price) / self.entry_price) if self.position == 1 and self.entry_price > 0 else (
            ((self.entry_price - close) / self.entry_price) if self.position == -1 and self.entry_price > 0 else 0.0
        )
        drawdown = (self.peak_balance - self.balance) / self.peak_balance if self.peak_balance > 0 else 0.0

        state = np.array([
            ret_1 * 10,
            ret_5 * 5,
            rsi_norm,
            np.clip(macd_norm, -3, 3),
            bb_pct,
            atr_norm * 100,
            st_dir,
            vwap_dist * 50,
            np.clip(vol_norm, 0, 5) / 2.5 - 1.0,
            pos_state,
            unrealized_pnl * 10,
            drawdown * 10
        ], dtype=np.float32)
        return np.nan_to_num(state)

    def step(self, action: int) -> Tuple[np.ndarray, float, bool, Dict[str, Any]]:
        """
        Executes action: 0 = HOLD, 1 = BUY, 2 = SELL
        Returns (next_state, reward, done, info)
        """
        current_bar = self.df.iloc[self.current_step]
        close = float(current_bar["close"])
        reward = 0.0

        # Action logic
        if action == 1: # BUY
            if self.position == 0:
                self.position = 1
                self.entry_price = close
                self.position_size = (self.balance * 0.95) / close
                fee = self.position_size * close * self.fee_pct
                self.balance -= fee
                reward -= 0.001 # Small transaction fee penalty
            elif self.position == -1: # Close Short, Open Long
                pnl = (self.entry_price - close) * self.position_size - (close * self.position_size * self.fee_pct)
                self.balance += pnl
                reward += (pnl / self.initial_balance) * 10.0
                self.position = 1
                self.entry_price = close
                self.position_size = (self.balance * 0.95) / close

        elif action == 2: # SELL
            if self.position == 0:
                self.position = -1
                self.entry_price = close
                self.position_size = (self.balance * 0.95) / close
                fee = self.position_size * close * self.fee_pct
                self.balance -= fee
                reward -= 0.001
            elif self.position == 1: # Close Long, Open Short
                pnl = (close - self.entry_price) * self.position_size - (close * self.position_size * self.fee_pct)
                self.balance += pnl
                reward += (pnl / self.initial_balance) * 10.0
                self.position = -1
                self.entry_price = close
                self.position_size = (self.balance * 0.95) / close

        # Step forward
        self.current_step += 1
        done = self.current_step >= len(self.df) - 1

        # Calculate step unrealized equity
        next_bar = self.df.iloc[self.current_step]
        next_close = float(next_bar["close"])
        
        step_return = 0.0
        if self.position == 1:
            step_return = (next_close - close) / close
        elif self.position == -1:
            step_return = (close - next_close) / close

        # Reward = Step Return - Drawdown Penalty (Sortino Ratio optimization)
        reward += step_return * 10.0
        if step_return < 0:
            reward += (step_return * 5.0) # Penalty for downside volatility

        current_equity = self.balance
        if self.position != 0:
            unrealized = (next_close - self.entry_price) * self.position_size if self.position == 1 else (self.entry_price - next_close) * self.position_size
            current_equity += unrealized

        if current_equity > self.peak_balance:
            self.peak_balance = current_equity

        # Bankruptcy condition
        if current_equity <= self.initial_balance * 0.5:
            done = True
            reward -= 5.0

        next_state = self._get_state()
        info = {
            "balance": self.balance,
            "equity": current_equity,
            "position": self.position,
            "step": self.current_step
        }
        return next_state, reward, done, info
