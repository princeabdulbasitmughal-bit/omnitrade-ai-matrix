import numpy as np
import pandas as pd
from typing import Dict, Any, List

class PerformanceMetrics:
    @staticmethod
    def calculate(trade_history: List[Dict[str, Any]], initial_capital: float = 10000.0) -> Dict[str, Any]:
        """
        Calculates institutional performance metrics from trade logs.
        """
        if not trade_history:
            return {
                "initial_capital": initial_capital,
                "ending_capital": initial_capital,
                "total_net_profit": 0.0,
                "return_pct": 0.0,
                "total_trades": 0,
                "win_rate_pct": 0.0,
                "profit_factor": 0.0,
                "sharpe_ratio": 0.0,
                "sortino_ratio": 0.0,
                "max_drawdown_pct": 0.0,
                "expectancy_per_trade": 0.0,
                "equity_curve": [initial_capital],
            }

        pnls = [t["pnl"] for t in trade_history]
        pnl_pcts = [t.get("pnl_pct", 0.0) for t in trade_history]
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p < 0]

        total_trades = len(pnls)
        win_count = len(wins)
        loss_count = len(losses)
        win_rate = (win_count / total_trades) * 100 if total_trades > 0 else 0.0

        gross_profit = sum(wins)
        gross_loss = abs(sum(losses))
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (99.9 if gross_profit > 0 else 1.0)

        # Equity Curve calculation
        equity_curve = [initial_capital]
        current_eq = initial_capital
        for p in pnls:
            current_eq += p
            equity_curve.append(round(current_eq, 2))

        ending_capital = equity_curve[-1]
        total_net_profit = ending_capital - initial_capital
        return_pct = (total_net_profit / initial_capital) * 100

        # Drawdown calculation
        peaks = pd.Series(equity_curve).cummax()
        drawdowns = (pd.Series(equity_curve) - peaks) / peaks * 100
        max_drawdown_pct = abs(float(drawdowns.min())) if not drawdowns.empty else 0.0

        # Sharpe & Sortino (per trade annualized approx)
        if len(pnl_pcts) > 1:
            mean_ret = np.mean(pnl_pcts)
            std_ret = np.std(pnl_pcts)
            sharpe = (mean_ret / std_ret * np.sqrt(252)) if std_ret > 0 else 0.0

            downside_pnls = [r for r in pnl_pcts if r < 0]
            downside_std = np.std(downside_pnls) if len(downside_pnls) > 1 else std_ret
            sortino = (mean_ret / downside_std * np.sqrt(252)) if downside_std > 0 else 0.0
        else:
            sharpe = 0.0
            sortino = 0.0

        avg_win = np.mean(wins) if wins else 0.0
        avg_loss = abs(np.mean(losses)) if losses else 0.0
        win_prob = win_rate / 100.0
        loss_prob = 1.0 - win_prob
        expectancy = (win_prob * avg_win) - (loss_prob * avg_loss)

        return {
            "initial_capital": round(initial_capital, 2),
            "ending_capital": round(ending_capital, 2),
            "total_net_profit": round(total_net_profit, 2),
            "return_pct": round(return_pct, 2),
            "total_trades": total_trades,
            "win_count": win_count,
            "loss_count": loss_count,
            "win_rate_pct": round(win_rate, 2),
            "profit_factor": round(profit_factor, 2),
            "avg_win": round(avg_win, 2),
            "avg_loss": round(avg_loss, 2),
            "expectancy_per_trade": round(expectancy, 2),
            "sharpe_ratio": round(sharpe, 2),
            "sortino_ratio": round(sortino, 2),
            "max_drawdown_pct": round(max_drawdown_pct, 2),
            "equity_curve": equity_curve,
        }
