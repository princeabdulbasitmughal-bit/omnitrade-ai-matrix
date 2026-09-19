import argparse
import sys
import os
import uvicorn
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

# Add root directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config.settings import Config
from core.market_data import MarketDataProvider
from core.portfolio import Portfolio
from core.risk_engine import RiskEngine
from core.order_manager import OrderManager
from ai_swarm.consensus_matrix import AIConsensusMatrix
from strategies.strategy_orchestrator import StrategyOrchestrator
from backtester.engine import BacktestEngine
from backtester.monte_carlo import MonteCarloSimulator

console = Console()

def run_scan():
    console.print(Panel.fit(
        "[bold cyan]⚡ OMNITRADE AI MATRIX — MULTI-MODEL SWARM SCAN[/bold cyan]\n"
        "[dim]NVIDIA RTX A6000 (48GB) • Qwen 32B • DeepSeek 16B • Kimi K3 • HF Llama 3.3 70B[/dim]",
        border_style="cyan"
    ))

    market_data = MarketDataProvider()
    portfolio = Portfolio()
    risk_engine = RiskEngine(portfolio)
    order_manager = OrderManager(portfolio, risk_engine)
    consensus_matrix = AIConsensusMatrix()
    orchestrator = StrategyOrchestrator(market_data, portfolio, risk_engine, order_manager, consensus_matrix)

    table = Table(title="Live Multi-Asset AI Consensus Matrix", border_style="blue")
    table.add_column("Asset", style="bold white")
    table.add_column("Price", justify="right", style="cyan")
    table.add_column("24h Change", justify="right")
    table.add_column("SuperTrend", justify="center")
    table.add_column("RSI", justify="right")
    table.add_column("ML Prediction", justify="center")
    table.add_column("AI Consensus", justify="center", style="bold")
    table.add_column("Confidence", justify="right")

    for symbol in Config.DEFAULT_SYMBOLS:
        res = orchestrator.analyze_symbol(symbol)
        ticker = res["ticker"]
        tech = res["technical_indicators"]
        ml = res["ml_prediction"]
        ai = res["ai_consensus"]

        chg = ticker.get("change_24h", 0.0)
        chg_str = f"[green]+{chg:.2f}%[/green]" if chg >= 0 else f"[red]{chg:.2f}%[/red]"

        sig = ai.get("final_signal", "HOLD")
        if "BUY" in sig:
            sig_str = f"[bold green]{sig}[/bold green]"
        elif "SELL" in sig:
            sig_str = f"[bold red]{sig}[/bold red]"
        else:
            sig_str = f"[yellow]{sig}[/yellow]"

        st_str = "[green]BULL[/green]" if tech.get("supertrend_is_bull") else "[red]BEAR[/red]"

        table.add_row(
            symbol,
            f"${ticker.get('last', 0.0):,.2f}" if ticker.get('last', 0) > 10 else f"${ticker.get('last', 0.0):.4f}",
            chg_str,
            st_str,
            f"{tech.get('rsi', 50):.1f}",
            f"{ml.get('prediction', 'NEUTRAL')} ({ml.get('confidence', 0.5)*100:.0f}%)",
            sig_str,
            f"{ai.get('aggregate_confidence', 0.5)*100:.1f}%"
        )

    console.print(table)

def run_backtest_cli(symbol: str, candles: int):
    console.print(f"[bold cyan]Running Quantitative & Monte Carlo Backtest on {symbol} ({candles} candles)...[/bold cyan]")
    market_data = MarketDataProvider()
    df = market_data.fetch_ohlcv(symbol, timeframe="15m", limit=candles)
    
    engine = BacktestEngine()
    res = engine.run(df, symbol=symbol)
    
    trades = res.get("trades_list", [])
    pnls = [t["pnl"] for t in trades]
    mc = MonteCarloSimulator.run_simulation(pnls, initial_capital=10000.0, num_simulations=1000)

    t = Table(title=f"Backtest Results: {symbol}", border_style="green")
    t.add_column("Metric", style="bold")
    t.add_column("Value", style="cyan")

    t.add_row("Initial Capital", f"${res['initial_capital']:,.2f}")
    t.add_row("Ending Capital", f"${res['ending_capital']:,.2f}")
    t.add_row("Total Return", f"{res['return_pct']:+.2f}%")
    t.add_row("Win Rate", f"{res['win_rate_pct']:.1f}% ({res['win_count']}W / {res['loss_count']}L)")
    t.add_row("Profit Factor", f"{res['profit_factor']:.2f}")
    t.add_row("Sharpe Ratio", f"{res['sharpe_ratio']:.2f}")
    t.add_row("Sortino Ratio", f"{res['sortino_ratio']:.2f}")
    t.add_row("Max Drawdown", f"{res['max_drawdown_pct']:.2f}%")
    t.add_row("Monte Carlo Prob of Profit", f"[bold green]{mc['probability_of_profit_pct']:.1f}%[/bold green]")
    t.add_row("Worst 5th Percentile Equity", f"${mc['worst_5th_percentile_equity']:,.2f}")

    console.print(t)

def start_server():
    console.print(Panel.fit(
        f"[bold green]🚀 STARTING OMNITRADE AI MATRIX LIVE TERMINAL[/bold green]\n"
        f"[cyan]Dashboard URL: [bold white]http://localhost:{Config.SERVER_PORT}[/bold white][/cyan]\n"
        f"[dim]WebSocket Stream: ws://localhost:{Config.SERVER_PORT}/ws/stream[/dim]",
        border_style="green"
    ))
    uvicorn.run("server.app:app", host=Config.SERVER_HOST, port=Config.SERVER_PORT, reload=False, log_level="info")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="OmniTrade AI Matrix Master Runner")
    parser.add_argument("--scan", action="store_true", help="Perform live AI Swarm scan on terminal")
    parser.add_argument("--backtest", type=str, help="Run backtest on symbol (e.g. BTC/USDT)")
    parser.add_argument("--candles", type=int, default=250, help="Number of candles for backtest")
    parser.add_argument("--dashboard", action="store_true", help="Launch FastAPI Web Dashboard & Live Execution Server")

    args = parser.parse_args()

    if args.scan:
        run_scan()
    elif args.backtest:
        run_backtest_cli(args.backtest, args.candles)
    else:
        # Default: launch dashboard server
        start_server()
