import logging
from typing import Dict, Any, List

logger = logging.getLogger("OmniTrade.Marketplace")

class StrategyMarketplace:
    def __init__(self):
        self.strategies = [
            {
                "id": "strat_rl_momentum",
                "name": "Alpha-RL Momentum Scalper",
                "author": "OmniTrade Quant Lab",
                "category": "Reinforcement Learning (PPO)",
                "description": "Deep Reinforcement Learning neural network agent optimizing for high-frequency 5m/15m momentum continuation and Sortino ratio.",
                "historical_win_rate": 68.4,
                "profit_factor": 3.45,
                "sharpe_ratio": 3.82,
                "max_drawdown": 4.2,
                "timeframes": ["5m", "15m"],
                "active_copiers": 1420,
                "risk_rating": "MODERATE",
                "is_active": True
            },
            {
                "id": "strat_smc_fvg",
                "name": "SMC Institutional Liquidity Hunter",
                "author": "Smart Money Matrix",
                "category": "Smart Money Concepts",
                "description": "Exploits Fair Value Gaps (FVG), Order Blocks, and Liquidity Sweeps targeting 1:3+ Risk-to-Reward institutional setups.",
                "historical_win_rate": 64.2,
                "profit_factor": 4.10,
                "sharpe_ratio": 3.15,
                "max_drawdown": 3.8,
                "timeframes": ["15m", "1h"],
                "active_copiers": 2890,
                "risk_rating": "LOW",
                "is_active": True
            },
            {
                "id": "strat_triangular_arb",
                "name": "Triangular Arbitrage Matrix",
                "author": "HFT Delta Neutral",
                "category": "Delta Neutral Arbitrage",
                "description": "Cross-currency 3-leg triangular arbitrage capturing microsecond price imbalances with zero directional market risk.",
                "historical_win_rate": 99.1,
                "profit_factor": 12.8,
                "sharpe_ratio": 6.40,
                "max_drawdown": 0.4,
                "timeframes": ["1s", "1m"],
                "active_copiers": 940,
                "risk_rating": "ULTRA_LOW",
                "is_active": True
            },
            {
                "id": "strat_deepseek_macro",
                "name": "DeepSeek Macro Trend Surfer",
                "author": "DeepSeek Quant Core",
                "category": "Macro & Trend Following",
                "description": "Multi-timeframe swing trading engine leveraging 4h/1d trend alignment, VWAP bands, and ATR trailing stop management.",
                "historical_win_rate": 59.8,
                "profit_factor": 2.95,
                "sharpe_ratio": 2.65,
                "max_drawdown": 5.5,
                "timeframes": ["1h", "4h", "1d"],
                "active_copiers": 1830,
                "risk_rating": "MODERATE",
                "is_active": True
            },
            {
                "id": "strat_volatility_squeeze",
                "name": "Volatility Breakout Squeeze",
                "author": "Institutional Vol Desk",
                "category": "Volatility Explosion",
                "description": "Detects Bollinger Band contraction inside Keltner Channels to capture massive directional volatility expansion explosions.",
                "historical_win_rate": 66.5,
                "profit_factor": 3.70,
                "sharpe_ratio": 3.40,
                "max_drawdown": 4.9,
                "timeframes": ["15m", "1h"],
                "active_copiers": 2150,
                "risk_rating": "HIGH_GROWTH",
                "is_active": True
            }
        ]
        self.copied_strategy_id = "strat_rl_momentum"

    def list_strategies(self) -> List[Dict[str, Any]]:
        for s in self.strategies:
            s["is_being_copied"] = (s["id"] == self.copied_strategy_id)
        return self.strategies

    def copy_strategy(self, strategy_id: str) -> Dict[str, Any]:
        found = next((s for s in self.strategies if s["id"] == strategy_id), None)
        if not found:
            return {"status": "ERROR", "message": "Strategy not found"}
        
        self.copied_strategy_id = strategy_id
        logger.info(f"User activated copy-trading for: {found['name']}")
        return {
            "status": "ACTIVATED",
            "message": f"Successfully activated Copy-Trading for {found['name']}!",
            "active_strategy": found
        }
