import numpy as np
import pandas as pd
from typing import Dict, Any, Tuple, Optional
from strategies.indicators import TechnicalIndicators

class TradingEnvironment:
    """
    OpenAI Gym-style reinforcement learning trading environment.
    State space: 12 normalized features (Returns, RSI, MACD, BB %B, ATR %, SuperTrend, VWAP distance, Volume Delta, Position State).
    Action space: 0 = HOLD, 1 = BUY / LONG, 2 = SELL / SHORT
    """
    def __init__(self, df: Optional[pd.DataFrame] = None, initial_balance: float = 10000.0, fee_pct: float = 0.00075):
        if df is None:
            # Generate default synthetic OHLCV frame if constructed without arguments
            closes = 100.0 + np.cumsum(np.random.normal(0.05, 0.5, 60))
            df = pd.DataFrame({
                "open": closes - 0.1,
                "high": closes + 0.4,
                "low": closes - 0.4,
                "close": closes,
                "volume": np.linspace(1000, 1500, 60),
            })
        self.df = TechnicalIndicators.compute_all(df)
        self.initial_balance = max(1.0, float(initial_balance))
        self.fee_pct = float(fee_pct)
        self.reset()

    def reset(self) -> np.ndarray:
        if self.df is None or self.df.empty:
            self.current_step = 0
        else:
            self.current_step = min(20, max(0, len(self.df) - 1))
        self.balance = self.initial_balance
        self.position = 0  # -1 = Short, 0 = Flat, 1 = Long
        self.entry_price = 0.0
        self.position_size = 0.0
        self.peak_balance = self.initial_balance
        self.trades = []
        return self._get_state()

    def _get_state(self) -> np.ndarray:
        if self.df is None or self.df.empty:
            return np.zeros(12, dtype=np.float32)

        n = len(self.df)
        step_idx = min(max(0, self.current_step), n - 1)
        row = self.df.iloc[step_idx]
        close = float(row.get("close", 0.0))
        if np.isnan(close) or close <= 0:
            close = 100.0

        prev_1_idx = max(0, step_idx - 1)
        prev_5_idx = max(0, step_idx - 5)
        prev_1_close = max(float(self.df["close"].iloc[prev_1_idx]), 1e-8)
        prev_5_close = max(float(self.df["close"].iloc[prev_5_idx]), 1e-8)

        # 12 Normalized state features
        ret_1 = (close - prev_1_close) / prev_1_close
        ret_5 = (close - prev_5_close) / prev_5_close
        rsi_norm = (float(row.get("rsi", 50.0)) - 50.0) / 50.0
        macd_norm = float(row.get("macd_hist", 0.0)) / (close * 0.01) if close > 0 else 0.0
        bb_pct = float(row.get("bb_pct", 0.5)) - 0.5
        atr_norm = float(row.get("atr", 0.0)) / close if close > 0 else 0.0
        st_dir = 1.0 if row.get("supertrend_dir", True) else -1.0
        vwap_dist = (close - float(row.get("vwap", close))) / close if close > 0 else 0.0

        vol_start = max(0, step_idx - 10)
        vol_slice = self.df["volume"].iloc[vol_start:step_idx + 1]
        vol_mean = float(vol_slice.mean()) if not vol_slice.empty else 1.0
        if np.isnan(vol_mean) or vol_mean <= 0:
            vol_mean = 1.0
        vol_norm = float(row.get("volume", 1.0)) / (vol_mean + 1e-5)
        
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
        return np.nan_to_num(state, nan=0.0, posinf=0.0, neginf=0.0)

    def step(self, action: int = 0) -> Tuple[np.ndarray, float, bool, Dict[str, Any]]:
        """
        Executes action: 0 = HOLD, 1 = BUY, 2 = SELL
        Returns (next_state, reward, done, info)
        """
        if self.df is None or self.df.empty:
            return (
                np.zeros(12, dtype=np.float32),
                0.0,
                True,
                {"balance": self.balance, "equity": self.balance, "position": 0, "step": 0}
            )

        n = len(self.df)
        self.current_step = min(max(0, self.current_step), n - 1)
        current_bar = self.df.iloc[self.current_step]
        close = float(current_bar.get("close", 100.0))
        if np.isnan(close) or close <= 0:
            close = 100.0
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

        # Step forward safely
        if self.current_step < n - 1:
            self.current_step += 1
        done = self.current_step >= n - 1

        # Calculate step unrealized equity
        next_bar = self.df.iloc[self.current_step]
        next_close = float(next_bar.get("close", close))
        if np.isnan(next_close) or next_close <= 0:
            next_close = close
        
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
            "balance": round(float(self.balance), 2),
            "equity": round(float(current_equity), 2),
            "position": self.position,
            "step": self.current_step
        }
        return next_state, float(reward), done, info

    def evaluate(self, state: Any = None) -> Dict[str, Any]:
        st = self._get_state()
        return {
            "environment": "TradingEnvironment",
            "state": st.tolist(),
            "state_dim": len(st),
            "balance": round(float(self.balance), 2),
            "position": self.position,
            "step": self.current_step,
            "status": "READY",
        }

    run = evaluate

