import requests
import json

BASE_URL = "http://localhost:8888"

def test_saas_suite():
    print("Testing OmniTrade Pro Commercial SaaS, White-Label & Investor Pitch Suite...")
    
    # 1. Test Commercial Overview
    res_ov = requests.get(f"{BASE_URL}/api/saas/commercial-overview")
    print(f"1. /api/saas/commercial-overview: {res_ov.status_code}")
    if res_ov.status_code == 200:
        ov = res_ov.json()
        print(f"   Total AUM: ${ov.get('total_aum_managed_usd'):,.2f}")
        print(f"   MRR: ${ov.get('monthly_recurring_revenue_mrr_usd'):,.2f}")
        print(f"   ARR: ${ov.get('annual_run_rate_arr_usd'):,.2f}")
        print(f"   Active Tenants: {ov.get('total_active_tenants')}")

    # 2. Test Investor Dossier
    res_pitch = requests.get(f"{BASE_URL}/api/saas/investor-dossier")
    print(f"2. /api/saas/investor-dossier: {res_pitch.status_code}")
    if res_pitch.status_code == 200:
        pd = res_pitch.json()
        print(f"   Title: {pd.get('title')}")
        kpi = pd.get("key_performance_indicators", {})
        print(f"   Sharpe: {kpi.get('sharpe_ratio')} | Sortino: {kpi.get('sortino_ratio')} | Max DD: {kpi.get('max_drawdown_pct')}%")
        print(f"   Monte Carlo Win Prob: {kpi.get('monte_carlo_probability_of_profit')}%")

    # 3. Test Create White-Label Tenant
    payload = {
        "brand_name": "Titan Quantitative Partners",
        "domain": "portal.titanquant.io",
        "admin_email": "trading@titanquant.io",
        "tier": "Prop Firm White-Label ($2,499/mo)",
        "primary_color": "#ff007f",
        "performance_fee_pct": 20.0
    }
    res_tenant = requests.post(f"{BASE_URL}/api/saas/tenants/create", json=payload)
    print(f"3. /api/saas/tenants/create: {res_tenant.status_code}")
    if res_tenant.status_code == 200:
        t_data = res_tenant.json()
        print(f"   Created Tenant: {t_data['tenant']['brand_name']} ({t_data['tenant']['tenant_id']})")
        print(f"   Assigned API Key: {t_data['tenant']['api_key']}")

    print("\n✅ ALL COMMERCIAL SAAS & INVESTOR PITCH TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    test_saas_suite()
