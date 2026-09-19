from typing import Dict, Any, List

class BillingTiersManager:
    @staticmethod
    def get_plans() -> List[Dict[str, Any]]:
        return [
            {
                "id": "tier_starter",
                "name": "Starter Trader",
                "price_usd": 0,
                "billing_period": "Forever Free",
                "features": [
                    "Full $10,000 Paper Trading Sandbox",
                    "All 4 Open-Source AI Swarm Models",
                    "Basic Quant Indicators (EMA, RSI, MACD)",
                    "Single Chart View & Manual Execution",
                    "Community Discord Support"
                ],
                "is_current": True
            },
            {
                "id": "tier_pro",
                "name": "Pro Algo Master",
                "price_usd": 49,
                "billing_period": "per month",
                "features": [
                    "Everything in Starter +",
                    "Live CCXT Exchange Execution (Binance / Bybit / OKX)",
                    "Reinforcement Learning (PPO & DQN Neural Agents)",
                    "Smart Money Concepts (SMC) & FVG Hunter",
                    "Telegram & WhatsApp Instant Audio Trade Alerts",
                    "1-Click Copy Trading & Strategy Marketplace"
                ],
                "is_popular": True,
                "is_current": False
            },
            {
                "id": "tier_institutional",
                "name": "Institutional Hedge Fund",
                "price_usd": 199,
                "billing_period": "per month",
                "features": [
                    "Everything in Pro +",
                    "Triangular & Cross-Exchange HFT Arbitrage Engine",
                    "TradingView Pine Script & MetaTrader 5 Webhook Ingestion",
                    "Dedicated Local GPU Swarm Allocation (RTX A6000)",
                    "Multi-Tenant White-Label API Access & Custom Endpoints",
                    "24/7 Dedicated Quant Risk Desk Support"
                ],
                "is_current": False
            }
        ]
