import os
import json
import pandas as pd
from typing import Dict, Any, List

class PerformanceReportExporter:
    """
    Exports institutional backtest ledgers, Monte Carlo statistics,
    and live trade histories to CSV and JSON formats.
    """
    @staticmethod
    def export_trade_history_csv(trades: List[Dict[str, Any]], filepath: str = "trade_history.csv") -> str:
        if not trades:
            return ""
        df = pd.DataFrame(trades)
        df.to_csv(filepath, index=False)
        return filepath

    @staticmethod
    def export_quant_audit_json(portfolio_summary: Dict[str, Any], backtest_results: Dict[str, Any], filepath: str = "quant_audit.json") -> str:
        audit_data = {
            "system": "OmniTrade Pro Institutional AI",
            "portfolio": portfolio_summary,
            "backtest_metrics": backtest_results,
            "version": "3.0.0"
        }
        with open(filepath, "w") as f:
            json.dump(audit_data, f, indent=2)
        return filepath
