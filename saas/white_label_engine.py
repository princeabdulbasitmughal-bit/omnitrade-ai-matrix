import os
import json
import uuid
import time
from typing import Dict, Any, List

class WhiteLabelEngine:
    """
    Commercial White-Label & Turnkey Tenant Management Engine
    Allows selling OmniTrade Pro to institutions, prop firms, and fund managers
    under custom branding with automated billing, license keys, and fee splits.
    """
    DATA_FILE = os.path.join(os.path.dirname(__file__), "tenants_store.json")

    def __init__(self):
        self._ensure_storage()

    def _ensure_storage(self):
        if not os.path.exists(self.DATA_FILE):
            default_tenants = [
                {
                    "tenant_id": "tenant_apex_alpha",
                    "brand_name": "Apex Alpha Quant Fund",
                    "domain": "portal.apexalpha.trade",
                    "tier": "Prop Firm White-Label ($2,499/mo)",
                    "admin_email": "quant@apexalpha.trade",
                    "primary_color": "#00f0ff",
                    "secondary_color": "#7000ff",
                    "performance_fee_pct": 20.0,
                    "platform_cut_pct": 5.0,
                    "active_users_count": 48,
                    "total_aum_usd": 1250000.0,
                    "monthly_revenue_usd": 38400.0,
                    "status": "ACTIVE",
                    "created_at": "2026-08-01 10:00:00"
                },
                {
                    "tenant_id": "tenant_olympus_capital",
                    "brand_name": "Olympus Digital Capital",
                    "domain": "terminal.olympuscapital.io",
                    "tier": "Institutional Enterprise ($1,499/mo)",
                    "admin_email": "desk@olympuscapital.io",
                    "primary_color": "#00ff88",
                    "secondary_color": "#0099ff",
                    "performance_fee_pct": 20.0,
                    "platform_cut_pct": 5.0,
                    "active_users_count": 124,
                    "total_aum_usd": 4800000.0,
                    "monthly_revenue_usd": 142000.0,
                    "status": "ACTIVE",
                    "created_at": "2026-08-10 14:30:00"
                }
            ]
            with open(self.DATA_FILE, "w", encoding="utf-8") as f:
                json.dump(default_tenants, f, indent=2)

    def get_tenants(self) -> List[Dict[str, Any]]:
        try:
            with open(self.DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []

    def create_tenant(self, brand_name: str, domain: str, tier: str, admin_email: str, 
                      primary_color: str = "#00f0ff", performance_fee_pct: float = 20.0) -> Dict[str, Any]:
        tenants = self.get_tenants()
        tenant_id = f"tenant_{uuid.uuid4().hex[:8]}"
        api_key = f"omp_live_{uuid.uuid4().hex}"
        
        new_tenant = {
            "tenant_id": tenant_id,
            "api_key": api_key,
            "brand_name": brand_name,
            "domain": domain or f"{tenant_id}.omnitrade.pro",
            "tier": tier,
            "admin_email": admin_email,
            "primary_color": primary_color,
            "secondary_color": "#7000ff",
            "performance_fee_pct": float(performance_fee_pct),
            "platform_cut_pct": 5.0,
            "active_users_count": 1,
            "total_aum_usd": 10000.0,
            "monthly_revenue_usd": 0.0,
            "status": "ACTIVE",
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        tenants.append(new_tenant)
        with open(self.DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(tenants, f, indent=2)
        return new_tenant

    def get_commercial_overview(self) -> Dict[str, Any]:
        tenants = self.get_tenants()
        total_aum = sum(t.get("total_aum_usd", 0) for t in tenants)
        total_mrr = sum(t.get("monthly_revenue_usd", 0) for t in tenants) + (len(tenants) * 1499.0)
        total_clients = sum(t.get("active_users_count", 0) for t in tenants)
        
        return {
            "total_active_tenants": len(tenants),
            "total_global_clients": total_clients,
            "total_aum_managed_usd": round(total_aum, 2),
            "monthly_recurring_revenue_mrr_usd": round(total_mrr, 2),
            "annual_run_rate_arr_usd": round(total_mrr * 12, 2),
            "commercial_tiers": [
                {
                    "tier_id": "tier_starter",
                    "title": "Starter Trader License",
                    "price_usd": 299,
                    "billing": "per month",
                    "target_market": "Retail Algo Traders & High-Volume Scalpers",
                    "features": [
                        "Full Multi-Model Swarm (Qwen 32B + DeepSeek 16B)",
                        "38 Quantitative Indicators & Real-time CCXT",
                        "Stepped Smart Exit (+1.0R, +1.5R, +2.5R Trailing Stop)",
                        "Telegram & Discord Audio Alerts",
                        "Single Exchange Account Connection"
                    ]
                },
                {
                    "tier_id": "tier_pro_quant",
                    "title": "Pro Quant Master",
                    "price_usd": 799,
                    "billing": "per month",
                    "popular": True,
                    "target_market": "Prop Traders & Professional Fund Managers",
                    "features": [
                        "All 6 AI Models (Qwen 32B + DeepSeek R1 + Kimi 1M + Llama 3.3 70B + PPO RL)",
                        "5-Exchange Simultaneous Level-2 Depth Arbitrage",
                        "Meta-Learning Bayesian Self-Optimizer",
                        "Multi-Account Execution & Sub-5ms Latency",
                        "High-Water Mark (HWM) Performance Fee Engine"
                    ]
                },
                {
                    "tier_id": "tier_enterprise_whitelabel",
                    "title": "Prop Firm & Hedge Fund White-Label",
                    "price_usd": 2499,
                    "billing": "per month + 20% Performance Fee",
                    "enterprise": True,
                    "target_market": "Prop Firms, Crypto Funds & Commercial Brokers",
                    "features": [
                        "100% Turnkey White-Label Platform (Your Logo, Domain & Colors)",
                        "Dedicated RTX A6000 48GB Hardware Cluster Allocation",
                        "Multi-Tenant User Management & Automated Invoicing",
                        "Institutional Investor Pitch Deck & Audit Exporter",
                        "Proprietary Alpha Lead-Generation API & 24/7 SLA"
                    ]
                }
            ],
            "tenants_list": tenants
        }
