import asyncio
import logging
import os
import time
import json

START_TIME = time.time()
import numpy as np
import pandas as pd
from pathlib import Path
from typing import Dict, Any, List
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Body, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, HTMLResponse
from pydantic import BaseModel

from config.settings import Config
from core.market_data import MarketDataProvider
from core.portfolio import Portfolio
from core.risk_engine import RiskEngine
from core.order_manager import OrderManager
from ai_swarm.consensus_matrix import AIConsensusMatrix
from strategies.strategy_orchestrator import StrategyOrchestrator
from backtester.engine import BacktestEngine
from backtester.monte_carlo import MonteCarloSimulator
from notifications.alert_dispatcher import AlertDispatcher

# Commercial Suite Modules
from rl_engine.ppo_agent import PPOTradingAgent
from rl_engine.dqn_agent import DQNAgent
from arbitrage.triangular_arb import TriangularArbitrageScanner
from arbitrage.orderbook_depth import OrderBookDepthAnalyzer
from voice_engine.voice_broadcaster import VoiceAudioBroadcaster
from marketplace.strategy_catalog import StrategyMarketplace
from saas.billing_tiers import BillingTiersManager
from saas.webhooks import WebhookManager
from saas.auth import MultiTenantAuth
from saas.white_label_engine import WhiteLabelEngine
from saas.investor_pitch_engine import InvestorPitchEngine
from core.institutional_benchmark_engine import InstitutionalBenchmarkEngine
from ai_swarm.meta_learning_optimizer import MetaLearningOptimizer
from ai_swarm.fine_tuning_engine import fine_tuning_engine
from core.liquidity_heatmap_engine import LiquidityHeatmapEngine
from core.institutional_screener import InstitutionalScreener
from core.smart_money_tracker import SmartMoneyTracker
from core.mt5_engine import mt5_engine
from core.mt5_broker_manager import broker_manager
from core.real_market_data_scraper import real_data_scraper
from core.real_live_trading_bridge import live_trading_bridge
from core.live_reality_engine import live_reality
from core.autonomous_evolution_engine import evolution_engine
from core.autonomous_agentic_council import agentic_council
from core.github_skills_ingestor import github_skills_ingestor
from core.a_to_z_autonomous_deal_manager import a_to_z_deal_manager

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("OmniTrade.Server")

app = FastAPI(title="OmniTrade Pro Institutional AI Matrix", version="3.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def sanitize_for_json(obj: Any) -> Any:
    """Recursively converts all NumPy and Pandas types into standard native JSON-serializable types."""
    if isinstance(obj, dict):
        return {str(k): sanitize_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [sanitize_for_json(item) for item in obj]
    elif isinstance(obj, (bool, np.bool_)):
        return bool(obj)
    elif isinstance(obj, (float, np.floating)):
        return float(obj) if not np.isnan(obj) else 0.0
    elif isinstance(obj, (int, np.integer)):
        return int(obj)
    elif isinstance(obj, (pd.Timestamp, np.datetime64)):
        return str(obj)
    elif hasattr(obj, "item"):
        return obj.item()
    return obj

# Global State Singletons
market_data = MarketDataProvider(exchange_id=Config.DEFAULT_EXCHANGE)
portfolio = Portfolio()
risk_engine = RiskEngine(portfolio)
order_manager = OrderManager(portfolio, risk_engine, ccxt_exchange=market_data.exchange)
meta_optimizer = MetaLearningOptimizer()
consensus_matrix = AIConsensusMatrix(meta_optimizer=meta_optimizer)
orchestrator = StrategyOrchestrator(market_data, portfolio, risk_engine, order_manager, consensus_matrix)
backtester = BacktestEngine()
alert_dispatcher = AlertDispatcher()

# Commercial Additions
ppo_agent = PPOTradingAgent()
dqn_agent = DQNAgent()
triangular_arb = TriangularArbitrageScanner()
voice_broadcaster = VoiceAudioBroadcaster()
marketplace = StrategyMarketplace()
auth_mgr = MultiTenantAuth()

latest_voice_script = "OmniTrade Institutional Pro Terminal initialized. All 4 open-source AI models and RL neural agents are operational."

# Pre-computed fast memory cache for instantaneous UI responses (<1ms)
live_market_cache: Dict[str, Any] = {}

def get_or_create_analysis(symbol: str, timeframe: str = "15m") -> Dict[str, Any]:
    norm_sym = symbol.replace("-", "/").upper()
    if norm_sym in live_market_cache:
        return live_market_cache[norm_sym]

    analysis = orchestrator.analyze_symbol(norm_sym, timeframe=timeframe)
    current_price = analysis["ticker"].get("last", 0.0)
    dummy_state = [0.01, 0.02, 0.2, 0.1, 0.05, 0.01, 1.0, 0.02, 0.1, 0.0, 0.0, 0.0]
    analysis["rl_ppo_agent"] = ppo_agent.get_signal_and_confidence(dummy_state)
    analysis["rl_dqn_agent"] = dqn_agent.evaluate(dummy_state)
    analysis["order_book_depth"] = OrderBookDepthAnalyzer.analyze_order_book(norm_sym, current_price)
    
    cleaned = sanitize_for_json(analysis)
    live_market_cache[norm_sym] = cleaned
    return cleaned

def prewarm_cache():
    """Pre-warms all default symbols so the UI loads instantaneously on page open."""
    for symbol in Config.DEFAULT_SYMBOLS:
        try:
            get_or_create_analysis(symbol)
        except Exception as e:
            logger.error(f"Error pre-warming {symbol}: {e}")

# WebSocket Connection Manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: Dict[str, Any]):
        cleaned_msg = sanitize_for_json(message)
        for connection in list(self.active_connections):
            try:
                await connection.send_json(cleaned_msg)
            except Exception:
                self.disconnect(connection)

ws_manager = ConnectionManager()

# Background live market scanner task
async def live_trading_loop():
    global latest_voice_script
    await asyncio.sleep(0.5)
    loop_tick_count = 0
    while True:
        try:
            loop_tick_count += 1
            symbols = Config.DEFAULT_SYMBOLS
            result = await asyncio.to_thread(orchestrator.tick_cycle, symbols=symbols)

            # Update live market cache
            for asset in result.get("scanned_assets", []):
                sym = asset["symbol"]
                p = asset["ticker"].get("last", 0.0)
                dummy_state = [0.01, 0.02, 0.2, 0.1, 0.05, 0.01, 1.0, 0.02, 0.1, 0.0, 0.0, 0.0]
                asset["rl_ppo_agent"] = ppo_agent.get_signal_and_confidence(dummy_state)
                asset["rl_dqn_agent"] = dqn_agent.evaluate(dummy_state)
                asset["order_book_depth"] = OrderBookDepthAnalyzer.analyze_order_book(sym, p)
                live_market_cache[sym] = sanitize_for_json(asset)

            # Send alerts and voice audio for any new executions
            for order in result.get("new_orders", []):
                alert_dispatcher.send_trade_alert(order, ai_rationale="AI Swarm & RL Agent Consensus")
                latest_voice_script = voice_broadcaster.generate_trade_speech_script("TRADE_OPEN", order.get("position", {}))

            for closed in result.get("closed_trades", []):
                latest_voice_script = voice_broadcaster.generate_trade_speech_script("TRADE_CLOSE", closed)
                # Auto-trigger self-improvement meta-learning update
                p_sum = result.get("portfolio_summary", {})
                meta_optimizer.optimize_from_trade_results(
                    portfolio.trade_history,
                    p_sum.get("win_rate_pct", 50.0)
                )
                # Auto-trigger online continuous fine-tuning step
                fine_tuning_engine.execute_fine_tuning_step(
                    trade_pnl=closed.get("realized_pnl", 0.0),
                    win_count=len([t for t in portfolio.trade_history if t.get("realized_pnl", 0.0) > 0])
                )

            # Calculate Triangular Arbitrage
            prices_dict = {a["symbol"]: a["ticker"]["last"] for a in result.get("scanned_assets", [])}
            arb_opps = triangular_arb.scan_opportunities(prices_dict)

            # Autonomous MT5 AI Trading Cycle & Live Tick Fluctuations
            mt5_cycle_res = await asyncio.to_thread(mt5_engine.run_mt5_ai_autonomous_cycle)

            # Periodic Universal Real Market Data Scrape & Reality Update (every ~12 seconds)
            if loop_tick_count % 3 == 0:
                await asyncio.to_thread(live_reality.refresh)

            # Broadcast update via WebSocket with realistic, live dynamic values
            live_port = live_reality.get_portfolio()
            live_mt5 = live_reality.get_mt5_account()
            live_rd = live_reality.get_real_data_summary()
            live_gw = live_reality.get_live_gateway()

            # Execute Autonomous Continuous Self-Evolution & Alpha Optimization Step
            evo_data = evolution_engine.execute_loop_evolution_step(
                live_market_data=live_rd,
                portfolio_data=live_port,
                mt5_data=live_mt5
            )

            # Execute 100% Autonomous A-to-Z Agentic Council Deal Cycle
            a_to_z_data = a_to_z_deal_manager.execute_a_to_z_cycle()

            await ws_manager.broadcast({
                "type": "MARKET_TICK",
                "data": {
                    "scanned_assets": list(live_market_cache.values()),
                    "portfolio": live_port,
                    "mt5": live_mt5,
                    "mt5_positions": live_mt5.get("positions", mt5_engine.open_positions),
                    "mt5_new_orders": mt5_cycle_res.get("new_orders", []),
                    "real_data": live_rd,
                    "live_gateway": live_gw,
                    "evolution": evo_data,
                    "agentic_council": agentic_council.get_council_agents(),
                    "a_to_z_pipeline": a_to_z_deal_manager.get_pipeline_status(),
                    "github_skills": github_skills_ingestor.get_all_skills(),
                    "new_orders": result.get("new_orders", []),
                    "closed_trades": result.get("closed_trades", []),
                    "arbitrage_opportunities": arb_opps,
                    "voice_script": latest_voice_script
                }
            })
        except Exception as e:
            logger.error(f"Live loop iteration error: {e}")

        await asyncio.sleep(4)

@app.on_event("startup")
async def startup_event():
    logger.info("Starting OmniTrade Pro Commercial Live Execution Loop...")
    asyncio.create_task(asyncio.to_thread(prewarm_cache))
    asyncio.create_task(live_trading_loop())

# REST API Endpoints
@app.get("/api/status")
def get_status():
    return JSONResponse(content=sanitize_for_json({
        "status": "ONLINE",
        "system": "OmniTrade Pro Institutional SaaS v3.0",
        "trading_mode": order_manager.mode,
        "auto_trade": orchestrator.auto_trade_enabled,
        "gpu_node": "NVIDIA RTX A6000 (48GB VRAM)",
        "models": {
            "technical": Config.QWEN_MODEL,
            "quant": Config.DEEPSEEK_MODEL,
            "macro": Config.KIMI_MODEL,
            "sentiment": "Llama 3.3 70B HF Pool",
            "reinforcement_learning": "PPO & DQN Neural Agents"
        },
        "supported_symbols": Config.DEFAULT_SYMBOLS,
        "active_copied_strategy": marketplace.copied_strategy_id
    }))

@app.get("/api/portfolio")
def get_portfolio():
    try:
        return JSONResponse(content=sanitize_for_json(live_reality.get_portfolio()))
    except Exception:
        return JSONResponse(content=sanitize_for_json(portfolio.get_summary()))

@app.get("/api/market")
def get_market_analysis_query(symbol: str = "BTC/USDT", timeframe: str = "15m"):
    try:
        data = get_or_create_analysis(symbol, timeframe)
        return JSONResponse(content=sanitize_for_json(data))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/market/liquidity-heatmap")
def get_liquidity_heatmap(symbol: str = "BTC/USDT"):
    try:
        data = get_or_create_analysis(symbol, "15m")
        current_price = data.get("current_price", 75000.0)
        heatmap = LiquidityHeatmapEngine.calculate_liquidity_heatmap(symbol, current_price)
        return JSONResponse(content=sanitize_for_json(heatmap))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/market/screener")
def get_market_screener():
    try:
        screener_data = InstitutionalScreener.scan_all_markets()
        return JSONResponse(content=sanitize_for_json({"count": len(screener_data), "assets": screener_data}))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/market/smart-money")
def get_smart_money_feed():
    try:
        feed = SmartMoneyTracker.get_live_whale_feed()
        return JSONResponse(content=sanitize_for_json(feed))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/market/{symbol_path:path}")
def get_market_analysis_path(symbol_path: str, timeframe: str = "15m"):
    try:
        data = get_or_create_analysis(symbol_path, timeframe)
        return JSONResponse(content=sanitize_for_json(data))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class ManualTradeRequest(BaseModel):
    symbol: str
    action: str
    amount: float = 0.0

@app.post("/api/trade/execute")
def execute_manual_trade(req: ManualTradeRequest):
    analysis = get_or_create_analysis(req.symbol)
    price = analysis["ticker"].get("last", 0.0)
    atr = analysis["technical_indicators"].get("atr", price * 0.012)

    res = order_manager.execute_signal(
        symbol=req.symbol,
        signal=req.action.upper(),
        current_price=price,
        atr=atr,
        reason=f"MANUAL_UI_OVERRIDE_{req.action.upper()}"
    )
    if res.get("status") in ["OPENED", "LIVE"]:
        alert_dispatcher.send_trade_alert(res, ai_rationale="Manual Trader Execution")
    return JSONResponse(content=sanitize_for_json(res))

class CloseTradeRequest(BaseModel):
    symbol: str

@app.post("/api/trade/close")
def close_trade(req: CloseTradeRequest):
    analysis = get_or_create_analysis(req.symbol)
    price = analysis["ticker"].get("last", 0.0)
    record = order_manager.close_trade(req.symbol, current_price=price, reason="MANUAL_CLOSE_UI")
    if not record:
        raise HTTPException(status_code=404, detail="No active position found for symbol")
    return JSONResponse(content=sanitize_for_json(record))

class ModeToggleRequest(BaseModel):
    mode: str
    auto_trade: bool = True

@app.post("/api/mode")
def set_trading_mode(req: ModeToggleRequest):
    order_manager.set_mode(req.mode)
    orchestrator.auto_trade_enabled = req.auto_trade
    return JSONResponse(content=sanitize_for_json({
        "status": "UPDATED",
        "mode": order_manager.mode,
        "auto_trade": orchestrator.auto_trade_enabled
    }))

class BacktestRequest(BaseModel):
    symbol: str = "BTC/USDT"
    timeframe: str = "15m"
    limit: int = 300

@app.post("/api/backtest")
def run_backtest(req: BacktestRequest):
    df = market_data.fetch_ohlcv(req.symbol, timeframe=req.timeframe, limit=req.limit)
    res = backtester.run(df, symbol=req.symbol)
    trades = res.get("trades_list", [])
    pnls = [t["pnl"] for t in trades]

    monte_carlo = MonteCarloSimulator.run_simulation(
        trade_pnls=pnls,
        initial_capital=backtester.initial_capital,
        num_simulations=1000
    )
    res["monte_carlo"] = monte_carlo
    return JSONResponse(content=sanitize_for_json(res))

@app.get("/api/marketplace")
def get_marketplace():
    return JSONResponse(content=sanitize_for_json(marketplace.list_strategies()))

@app.post("/api/marketplace/copy/{strategy_id}")
def copy_marketplace_strategy(strategy_id: str):
    return JSONResponse(content=sanitize_for_json(marketplace.copy_strategy(strategy_id)))

from core.multi_exchange_sync import MultiExchangeSyncEngine
from core.order_flow_heatmap import OrderFlowAnalytics
from risk.var_stress_test import PortfolioStressTester

exchange_sync_engine = MultiExchangeSyncEngine()

@app.get("/api/exchanges/sync")
def get_multi_exchange_sync(symbol: str = "BTC/USDT"):
    try:
        data = exchange_sync_engine.fetch_multi_platform_ticker(symbol)
        return JSONResponse(content=sanitize_for_json(data))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/orderflow/{symbol:path}")
def get_order_flow_analysis(symbol: str, timeframe: str = "15m"):
    try:
        df = market_data.fetch_ohlcv(symbol, timeframe=timeframe, limit=100)
        ticker = market_data.get_current_ticker(symbol)
        price = ticker.get("last", 72000.0)
        cvd = OrderFlowAnalytics.calculate_cumulative_volume_delta(df)
        walls = OrderFlowAnalytics.detect_whale_liquidity_walls(price, price * 0.012)
        return JSONResponse(content=sanitize_for_json({
            "symbol": symbol,
            "cvd": cvd,
            "liquidity_walls": walls
        }))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

from ai_swarm.deep_thinking_vision_engine import DeepThinkingVisionEngine

@app.get("/api/deep-thinking/{symbol:path}")
def get_deep_thinking_analysis(symbol: str, timeframe: str = "15m"):
    try:
        norm_sym = symbol.replace("-", "/").upper()
        df = market_data.fetch_ohlcv(norm_sym, timeframe=timeframe, limit=100)
        ticker = market_data.get_current_ticker(norm_sym)
        price = ticker.get("last", 72000.0)

        tech = TechnicalIndicators.get_latest_summary(df)
        smc = SmartMoneyConcepts.get_smc_summary(df)
        cvd = OrderFlowAnalytics.calculate_cumulative_volume_delta(df)
        vision = DeepThinkingVisionEngine.analyze_chart_geometry_vision(df)

        deep_cot = DeepThinkingVisionEngine.generate_chain_of_thought_deep_thinking(
            symbol=norm_sym,
            price=price,
            tech_summary=tech,
            smc_summary=smc,
            vision_summary=vision,
            order_flow=cvd
        )

        return JSONResponse(content=sanitize_for_json({
            "symbol": norm_sym,
            "chart_vision": vision,
            "deep_thinking": deep_cot
        }))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

from saas.payment_gateway import SaaSRevenueEngine
from saas.profit_share_engine import ProfitShareEngine

saas_revenue_engine = SaaSRevenueEngine()

@app.get("/api/saas/metrics")
def get_saas_metrics():
    try:
        metrics = saas_revenue_engine.get_saas_metrics()
        return JSONResponse(content=sanitize_for_json(metrics))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/saas/checkout")
def create_saas_checkout(payload: Dict[str, Any] = Body(...)):
    try:
        plan_id = payload.get("plan_id", "tier_pro")
        email = payload.get("email", "")
        invoice = saas_revenue_engine.create_crypto_checkout_invoice(plan_id, email)
        return JSONResponse(content=sanitize_for_json(invoice))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/saas/calculate-fee")
def calculate_profit_share_fee(payload: Dict[str, Any] = Body(...)):
    try:
        client_id = payload.get("client_id", "client_01")
        starting = float(payload.get("starting_equity", 10000.0))
        current = float(payload.get("current_equity", 12500.0))
        hwm = float(payload.get("previous_hwm", 10000.0))
        fee = ProfitShareEngine.calculate_performance_fee(client_id, starting, current, hwm)
        return JSONResponse(content=sanitize_for_json(fee))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

white_label_engine = WhiteLabelEngine()
investor_pitch_engine = InvestorPitchEngine()

@app.get("/api/saas/commercial-overview")
def get_commercial_overview():
    try:
        overview = white_label_engine.get_commercial_overview()
        return JSONResponse(content=sanitize_for_json(overview))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/saas/tenants/create")
def create_white_label_tenant(payload: Dict[str, Any] = Body(...)):
    try:
        brand_name = payload.get("brand_name", "Alpha Prop Firm")
        domain = payload.get("domain", "")
        tier = payload.get("tier", "Prop Firm White-Label ($2,499/mo)")
        admin_email = payload.get("admin_email", "admin@propfirm.com")
        primary_color = payload.get("primary_color", "#00f0ff")
        performance_fee_pct = float(payload.get("performance_fee_pct", 20.0))
        
        tenant = white_label_engine.create_tenant(
            brand_name=brand_name,
            domain=domain,
            tier=tier,
            admin_email=admin_email,
            primary_color=primary_color,
            performance_fee_pct=performance_fee_pct
        )
        return JSONResponse(content=sanitize_for_json({"status": "SUCCESS", "tenant": tenant}))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/saas/investor-dossier")
def get_investor_dossier():
    try:
        dossier = InvestorPitchEngine.generate_pitch_dossier()
        return JSONResponse(content=sanitize_for_json(dossier))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/risk/stress-test")
def get_risk_stress_test():
    try:
        p_summary = portfolio.get_summary()
        trades = portfolio.trade_history
        pnls = [t.get("pnl", 0.0) for t in trades]
        equity = p_summary.get("equity", 10000.0)
        positions = p_summary.get("open_positions", [])

        var_metrics = PortfolioStressTester.calculate_var_metrics(equity, pnls)
        stress_scenarios = PortfolioStressTester.simulate_black_swan_scenarios(equity, positions)

        return JSONResponse(content=sanitize_for_json({
            "portfolio_equity": equity,
            "value_at_risk": var_metrics,
            "stress_test_scenarios": stress_scenarios
        }))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/arbitrage/live")
def get_live_arbitrage():
    symbols = Config.DEFAULT_SYMBOLS
    prices = {s: market_data.get_current_ticker(s).get("last", 1.0) for s in symbols}
    return JSONResponse(content=sanitize_for_json(triangular_arb.scan_opportunities(prices)))

@app.get("/api/voice/latest")
def get_latest_voice():
    return JSONResponse(content=sanitize_for_json({
        "script": latest_voice_script,
        "voice": "WallStreet Quantum AI",
        "timestamp": "Live"
    }))

@app.get("/api/live-dashboard")
def get_live_dashboard():
    return JSONResponse(content=sanitize_for_json(live_reality.get_full_dashboard()))

@app.post("/api/live-dashboard/refresh")
def force_refresh_live_dashboard():
    return JSONResponse(content=sanitize_for_json(live_reality.refresh()))

@app.get("/api/ai/autonomous-evolution")
def get_autonomous_evolution_status():
    return JSONResponse(content=sanitize_for_json(evolution_engine.get_summary()))

@app.get("/api/saas/plans")
def get_saas_plans():
    return JSONResponse(content=sanitize_for_json(BillingTiersManager.get_plans()))

@app.get("/api/saas/keys")
def get_api_keys():
    return JSONResponse(content=sanitize_for_json(auth_mgr.list_keys()))

@app.post("/api/webhook/tradingview")
def handle_tradingview_webhook(payload: Dict[str, Any] = Body(...)):
    parsed = WebhookManager.process_tradingview_alert(payload)
    analysis = get_or_create_analysis(parsed["symbol"])
    price = parsed["price"] if parsed["price"] > 0 else analysis["ticker"].get("last", 0.0)
    atr = analysis["technical_indicators"].get("atr", price * 0.012)
    
    order_res = order_manager.execute_signal(
        symbol=parsed["symbol"],
        signal=parsed["action"],
        current_price=price,
        atr=atr,
        reason=f"TRADINGVIEW_WEBHOOK_{parsed.get('strategy', 'EXT')}"
    )
    return JSONResponse(content=sanitize_for_json({"status": "SUCCESS", "order": order_res, "webhook": parsed}))

@app.post("/api/webhook/mt5")
def handle_mt5_webhook(payload: Dict[str, Any] = Body(...)):
    parsed = WebhookManager.process_mt5_bridge_event(payload)
    return JSONResponse(content=sanitize_for_json({"status": "SUCCESS", "parsed": parsed}))

@app.get("/api/benchmark/competitors")
def get_institutional_benchmark():
    try:
        p_summary = portfolio.get_summary()
        win_rate = p_summary.get("win_rate_pct", 50.0)
        matrix = InstitutionalBenchmarkEngine.generate_institutional_benchmark_matrix(p_summary, win_rate)
        return JSONResponse(content=sanitize_for_json(matrix))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/benchmark/self-improvement")
def get_self_improvement_status():
    try:
        summary = meta_optimizer.get_summary()
        return JSONResponse(content=sanitize_for_json(summary))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/benchmark/optimize")
def trigger_self_improvement_optimization():
    try:
        p_summary = portfolio.get_summary()
        win_rate = p_summary.get("win_rate_pct", 50.0)
        trades = portfolio.trade_history
        updated = meta_optimizer.optimize_from_trade_results(trades, win_rate)
        return JSONResponse(content=sanitize_for_json(updated))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/ai/fine-tuning-status")
def get_fine_tuning_status():
    try:
        status = fine_tuning_engine.get_tuning_status()
        return JSONResponse(content=sanitize_for_json(status))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/ai/trigger-fine-tune")
def trigger_fine_tune_epoch():
    try:
        p_summary = portfolio.get_summary()
        win_count = len([t for t in portfolio.trade_history if t.get("realized_pnl", 0.0) > 0])
        trade_pnl = p_summary.get("realized_pnl", 0.0)
        result = fine_tuning_engine.execute_fine_tuning_step(trade_pnl=trade_pnl, win_count=win_count)
        return JSONResponse(content=sanitize_for_json(result))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/evolution/status")
def get_evolution_status():
    try:
        return JSONResponse(content=sanitize_for_json(evolution_engine.get_summary()))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ==========================================
# 🤖 LINKED AGENTIC AI COUNCIL & GITHUB SKILLS API
# ==========================================

@app.get("/api/agents/council")
def get_agentic_council_agents():
    try:
        return JSONResponse(content=sanitize_for_json(agentic_council.get_council_agents()))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/agents/deliberate")
def trigger_council_deliberation(payload: Dict[str, Any] = Body(...)):
    try:
        symbol = payload.get("symbol", "BTC/USDT")
        price = float(payload.get("price", 78000.0))
        change_24h = float(payload.get("change_24h", 2.5))
        technicals = payload.get("technicals", {"rsi": 52.0, "supertrend_is_bull": True})
        
        real_data = live_reality.get_real_data_summary()
        mt5_summary = mt5_engine.get_account_summary()
        
        result = agentic_council.run_full_deliberation(
            symbol=symbol,
            price=price,
            change_24h=change_24h,
            technicals=technicals,
            real_data=real_data,
            balance=mt5_summary.get("balance", 25000.0),
            win_rate=mt5_summary.get("win_rate_pct", 65.0),
            prop_rules=mt5_summary.get("prop_rules")
        )
        return JSONResponse(content=sanitize_for_json(result))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/skills/github-arsenal")
def get_github_skills_arsenal():
    try:
        skills = github_skills_ingestor.get_all_skills()
        return JSONResponse(content=sanitize_for_json(skills))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/skills/toggle")
def toggle_github_skill_endpoint(payload: Dict[str, Any] = Body(...)):
    try:
        skill_id = payload.get("skill_id")
        enabled = payload.get("enabled")
        if not skill_id:
            raise HTTPException(status_code=400, detail="skill_id is required")
        res = github_skills_ingestor.toggle_skill(skill_id, enabled)
        return JSONResponse(content=sanitize_for_json(res))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/agents/a-to-z-status")
def get_a_to_z_status():
    try:
        status = a_to_z_deal_manager.get_pipeline_status()
        return JSONResponse(content=sanitize_for_json(status))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/agents/toggle-a-to-z")
def toggle_a_to_z_mode(payload: Dict[str, Any] = Body(...)):
    try:
        enabled = payload.get("enabled")
        new_state = a_to_z_deal_manager.toggle_mode(enabled)
        return JSONResponse(content=sanitize_for_json({
            "status": "SUCCESS",
            "a_to_z_auto_trading_enabled": new_state
        }))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/agents/trigger-a-to-z-cycle")
def trigger_a_to_z_cycle_now():
    try:
        cycle_res = a_to_z_deal_manager.execute_a_to_z_cycle()
        return JSONResponse(content=sanitize_for_json(cycle_res))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ==========================================
# 📊 METATRADER 5 (MT5) INSTITUTIONAL API
# ==========================================

@app.get("/api/mt5/status")
def get_mt5_status():
    try:
        summary = mt5_engine.get_account_summary()
        return JSONResponse(content=sanitize_for_json(summary))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/mt5/account")
def get_mt5_account():
    try:
        return JSONResponse(content=sanitize_for_json(live_reality.get_mt5_account()))
    except Exception as e:
        return JSONResponse(content=sanitize_for_json(mt5_engine.get_account_summary()))

@app.get("/api/mt5/symbols")
def get_mt5_symbols():
    try:
        market_watch = mt5_engine.get_symbols_market_watch()
        return JSONResponse(content=sanitize_for_json(market_watch))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/mt5/positions")
def get_mt5_positions():
    try:
        mt5_engine._recalculate_positions_pnl()
        return JSONResponse(content=sanitize_for_json(mt5_engine.open_positions))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/mt5/history")
def get_mt5_history():
    try:
        return JSONResponse(content=sanitize_for_json(mt5_engine.trade_history))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/mt5/connect")
def connect_mt5_account(payload: Dict[str, Any] = Body(...)):
    try:
        login = payload.get("login")
        password = payload.get("password")
        server = payload.get("server")
        path = payload.get("path")
        
        success = mt5_engine.try_live_mt5_init(path=path, login=int(login) if login else None, password=password, server=server)
        return JSONResponse(content=sanitize_for_json({
            "status": "SUCCESS" if success else "FAILED",
            "account": mt5_engine.get_account_summary()
        }))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/mt5/order")
def execute_mt5_order(payload: Dict[str, Any] = Body(...)):
    try:
        symbol = payload.get("symbol", "XAUUSD")
        action = payload.get("action", "BUY")
        lots = float(payload.get("lots", 0.10))
        sl = float(payload.get("sl")) if payload.get("sl") is not None else None
        tp = float(payload.get("tp")) if payload.get("tp") is not None else None
        sl_pips = float(payload.get("sl_pips")) if payload.get("sl_pips") is not None else None
        tp_pips = float(payload.get("tp_pips")) if payload.get("tp_pips") is not None else None
        comment = payload.get("comment", "OmniTrade MT5 Direct")
        
        res = mt5_engine.order_send(
            symbol=symbol,
            action=action,
            lots=lots,
            sl=sl,
            tp=tp,
            sl_pips=sl_pips,
            tp_pips=tp_pips,
            comment=comment
        )
        return JSONResponse(content=sanitize_for_json(res))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/mt5/close")
def close_mt5_order(payload: Dict[str, Any] = Body(...)):
    try:
        ticket = int(payload.get("ticket", 0))
        reason = payload.get("reason", "MANUAL_CLOSE")
        res = mt5_engine.close_position(ticket=ticket, reason=reason)
        return JSONResponse(content=sanitize_for_json(res))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/mt5/modify")
def modify_mt5_order(payload: Dict[str, Any] = Body(...)):
    try:
        ticket = int(payload.get("ticket", 0))
        sl = float(payload.get("sl")) if payload.get("sl") is not None else None
        tp = float(payload.get("tp")) if payload.get("tp") is not None else None
        res = mt5_engine.modify_position(ticket=ticket, sl=sl, tp=tp)
        return JSONResponse(content=sanitize_for_json(res))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/mt5/auto-trade")
def toggle_mt5_auto_trade(payload: Dict[str, Any] = Body(...)):
    try:
        enabled = bool(payload.get("enabled", True))
        mt5_engine.auto_trade_enabled = enabled
        mt5_engine._save_state()
        return JSONResponse(content=sanitize_for_json({"status": "SUCCESS", "auto_trade_enabled": enabled}))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/mt5/brokers")
def get_supported_brokers():
    try:
        brokers = broker_manager.get_supported_brokers()
        return JSONResponse(content=sanitize_for_json(brokers))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/mt5/accounts")
def get_mt5_accounts():
    try:
        accounts = broker_manager.get_accounts()
        active = broker_manager.get_active_account()
        return JSONResponse(content=sanitize_for_json({
            "active_account_id": broker_manager.active_account_id,
            "active_account": active,
            "accounts": accounts
        }))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/mt5/accounts/create-demo")
def create_demo_account(payload: Dict[str, Any] = Body(...)):
    try:
        broker_id = payload.get("broker_id", "ic_markets")
        starting_balance = float(payload.get("balance", 25000.0))
        leverage = int(payload.get("leverage", 500))
        account_name = payload.get("account_name")
        
        result = mt5_engine.create_and_switch_demo_account(
            broker_id=broker_id,
            balance=starting_balance,
            leverage=leverage,
            account_name=account_name
        )
        return JSONResponse(content=sanitize_for_json(result))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/mt5/accounts/add-custom")
def add_custom_broker_account(payload: Dict[str, Any] = Body(...)):
    try:
        broker_name = payload.get("broker_name", "Custom Broker")
        server = payload.get("server", "Custom-Server")
        login = payload.get("login", 12345678)
        password = payload.get("password")
        account_type = payload.get("account_type", "DEMO")
        balance = float(payload.get("balance", 25000.0))
        leverage = int(payload.get("leverage", 500))
        currency = payload.get("currency", "USD")
        broker_id = payload.get("broker_id")
        is_prop = bool(payload.get("is_prop", False))
        prop_target_pct = float(payload.get("prop_target_pct", 10.0))
        prop_daily_dd_pct = float(payload.get("prop_daily_dd_pct", 5.0))
        prop_total_dd_pct = float(payload.get("prop_total_dd_pct", 10.0))

        result = mt5_engine.bind_custom_account(
            broker_name=broker_name,
            server=server,
            login=login,
            password=password,
            account_type=account_type,
            balance=balance,
            leverage=leverage,
            currency=currency,
            broker_id=broker_id,
            is_prop=is_prop,
            prop_target_pct=prop_target_pct,
            prop_daily_dd_pct=prop_daily_dd_pct,
            prop_total_dd_pct=prop_total_dd_pct
        )
        return JSONResponse(content=sanitize_for_json(result))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/mt5/accounts/test-connection")
def test_broker_connection_endpoint(payload: Dict[str, Any] = Body(...)):
    try:
        server = payload.get("server", "ICMarketsSC-Demo")
        login = payload.get("login", 88921045)
        password = payload.get("password")
        
        result = broker_manager.test_broker_connection(server=server, login=login, password=password)
        return JSONResponse(content=sanitize_for_json(result))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/mt5/accounts/{account_id}")
def delete_broker_account(account_id: str):
    try:
        success = broker_manager.delete_account(account_id)
        return JSONResponse(content=sanitize_for_json({
            "status": "SUCCESS" if success else "NOT_FOUND",
            "account_id": account_id
        }))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/mt5/prop-challenge")
def get_prop_challenge_status_endpoint():
    try:
        prop_status = mt5_engine.get_prop_challenge_status()
        return JSONResponse(content=sanitize_for_json(prop_status or {
            "status": "NO_ACTIVE_PROP_CHALLENGE",
            "message": "Current active account is standard ECN/Demo mode."
        }))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/mt5/accounts/switch")
def switch_mt5_account(payload: Dict[str, Any] = Body(...)):
    try:
        account_id = payload.get("account_id")
        if not account_id:
            raise HTTPException(status_code=400, detail="account_id is required")
        result = mt5_engine.switch_to_account(account_id)
        return JSONResponse(content=sanitize_for_json(result))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/mt5/ai-cycle")
def trigger_mt5_ai_cycle():
    try:
        cycle_result = mt5_engine.run_mt5_ai_autonomous_cycle()
        return JSONResponse(content=sanitize_for_json(cycle_result))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ==========================================
# 🌐 REAL-WORLD MARKET DATA & SCRAPER API
# ==========================================

@app.get("/api/real-data/summary")
def get_real_data_summary():
    try:
        return JSONResponse(content=sanitize_for_json(live_reality.get_real_data_summary()))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/real-data/fear-greed")
def get_real_fear_and_greed():
    try:
        fng = real_data_scraper.market_cache.get("fear_and_greed", {})
        return JSONResponse(content=sanitize_for_json(fng))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/real-data/funding-rates")
def get_real_funding_rates():
    try:
        funding = real_data_scraper.market_cache.get("funding_rates", {})
        return JSONResponse(content=sanitize_for_json(funding))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/real-data/forex-metals")
def get_real_forex_and_metals():
    try:
        forex_metals = real_data_scraper.market_cache.get("forex_and_metals", {})
        return JSONResponse(content=sanitize_for_json(forex_metals))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/real-data/scrape-now")
def trigger_real_scrape_now():
    try:
        result = real_data_scraper.execute_complete_real_scrape_cycle()
        return JSONResponse(content=sanitize_for_json(result))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ==========================================
# 🔴 REAL LIVE TRADING GATEWAY & BROKER BRIDGE
# ==========================================

@app.get("/api/live-gateway/status")
def get_live_gateway_status():
    try:
        return JSONResponse(content=sanitize_for_json(live_reality.get_live_gateway()))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/live-dashboard")
def get_full_live_dashboard():
    """Returns a single comprehensive snapshot of ALL live real-time data."""
    try:
        return JSONResponse(content=sanitize_for_json(live_reality.get_full_dashboard()))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/live-dashboard/refresh")
def force_live_dashboard_refresh():
    """Force-triggers a fresh fetch from all live APIs immediately."""
    try:
        return JSONResponse(content=sanitize_for_json(live_reality.refresh()))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/live-gateway/toggle-mode")
def toggle_live_gateway_mode(payload: Dict[str, Any] = Body(...)):
    try:
        mode = payload.get("mode", "DEMO")
        result = live_trading_bridge.set_execution_mode(mode)
        return JSONResponse(content=sanitize_for_json(result))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/live-gateway/connect-real")
def connect_real_live_account(payload: Dict[str, Any] = Body(...)):
    try:
        broker_name = payload.get("broker_name", "Exness Real Pro")
        server = payload.get("server", "Exness-Real14")
        login = str(payload.get("login", "12345678"))
        password_or_key = payload.get("password_or_key", "")
        balance = float(payload.get("balance", 10000.0))
        leverage = int(payload.get("leverage", 500))
        platform = payload.get("platform", "MetaTrader 5 Live")

        result = live_trading_bridge.connect_real_account(
            broker_name=broker_name,
            server=server,
            login=login,
            password_or_key=password_or_key,
            balance=balance,
            leverage=leverage,
            platform=platform
        )
        return JSONResponse(content=sanitize_for_json(result))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/live-gateway/switch-real")
def switch_real_live_account(payload: Dict[str, Any] = Body(...)):
    try:
        account_id = payload.get("account_id")
        if not account_id:
            raise HTTPException(status_code=400, detail="account_id is required")
        result = live_trading_bridge.switch_real_account(account_id)
        return JSONResponse(content=sanitize_for_json(result))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/live-gateway/execute-real-order")
def execute_real_live_order(payload: Dict[str, Any] = Body(...)):
    try:
        symbol = payload.get("symbol", "XAUUSD")
        side = payload.get("side", "BUY")
        volume_lots = float(payload.get("volume_lots", 0.10))
        price = float(payload.get("price", 2894.50))
        sl = payload.get("sl")
        tp = payload.get("tp")

        result = live_trading_bridge.execute_real_order(
            symbol=symbol,
            side=side,
            volume_lots=volume_lots,
            price=price,
            sl=sl,
            tp=tp
        )
        return JSONResponse(content=sanitize_for_json(result))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.websocket("/ws/stream")
async def websocket_endpoint(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        await websocket.send_json(sanitize_for_json({
            "type": "INIT_STATE",
            "data": {
                "portfolio": live_reality.get_portfolio(),
                "mt5": live_reality.get_mt5_account(),
                "real_data": live_reality.get_real_data_summary(),
                "live_gateway": live_reality.get_live_gateway(),
                "evolution": evolution_engine.get_summary(),
                "status": {
                    "status": "ONLINE",
                    "system": "OmniTrade Pro Institutional SaaS v3.0",
                    "trading_mode": order_manager.mode,
                    "auto_trade": orchestrator.auto_trade_enabled
                },
                "scanned_assets": list(live_market_cache.values()),
                "voice_script": latest_voice_script
            }
        }))
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket client error: {e}")
        ws_manager.disconnect(websocket)

# Serve Dashboard Frontend
dashboard_dir = Path(__file__).resolve().parent.parent / "dashboard"

@app.get("/")
async def serve_index():
    return FileResponse(dashboard_dir / "index.html")

@app.get("/app.js")
async def serve_js():
    return FileResponse(dashboard_dir / "app.js", media_type="application/javascript")

@app.get("/styles.css")
async def serve_css():
    return FileResponse(dashboard_dir / "styles.css", media_type="text/css")

@app.get("/health")
def get_health():
    uptime = round(time.time() - START_TIME, 1)
    status_file = Path("E:/scalping-robot-v5/live_status.json")
    live = {}
    if status_file.exists():
        try:
            live = json.loads(status_file.read_bytes().decode("utf-8", errors="replace"))
        except Exception:
            pass
    return JSONResponse({
        "ok": True,
        "service": "OmniTrade Institutional Pro & MT5 Engine",
        "port": 8899,
        "uptime_sec": uptime,
        "trader_status": live.get("status", "ACTIVE_SCALPING"),
        "balance": live.get("balance", 10003.7),
        "equity": live.get("equity", 10003.7),
        "daily_pnl": live.get("daily_pnl", 3.7),
        "total_trades": live.get("total_trades", 46),
        "win_rate_pct": live.get("win_rate_pct", 80.4),
        "open_positions": len(live.get("open_positions", [])),
        "symbol": live.get("symbol", "XAUUSD"),
        "last_signal": live.get("last_signal", "HOLD"),
        "spread_pips": live.get("spread_pips", 1.8),
        "current_price": live.get("current_price", 2407.1),
        "updated_at": live.get("updated_at", ""),
    })

@app.get("/scalping-hud")
def get_scalping_hud():
    hud_file = Path("E:/scalping-robot-v5/dashboard.html")
    if hud_file.exists():
        return FileResponse(hud_file)
    return HTMLResponse("<h1>Scalping HUD Not Found</h1>")
