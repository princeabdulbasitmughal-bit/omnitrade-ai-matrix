import os
import json
import numpy as np
import pandas as pd
from typing import Dict, Any, List, Optional


class PerformanceReportExporter:
    """
    Exports institutional backtest ledgers, Monte Carlo statistics,
    and live trade histories to CSV and JSON formats.
    """
    @staticmethod
    def export_trade_history_csv(trades: Optional[List[Dict[str, Any]]] = None, filepath: str = "trade_history.csv") -> str:
        if not trades:
            return ""
        df = pd.DataFrame(trades)
        df.to_csv(filepath, index=False)
        return filepath

    @staticmethod
    def export_quant_audit_json(
        portfolio_summary: Optional[Dict[str, Any]] = None,
        backtest_results: Optional[Dict[str, Any]] = None,
        filepath: str = "quant_audit.json"
    ) -> str:
        audit_data = {
            "system": "OmniTrade Pro Institutional AI",
            "portfolio": portfolio_summary or {},
            "backtest_metrics": backtest_results or {},
            "version": "3.0.0"
        }
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(audit_data, f, indent=2, default=lambda x: x.item() if isinstance(x, np.generic) else str(x))
        return filepath

    @classmethod
    def evaluate(cls, portfolio_summary: Optional[Dict[str, Any]] = None, backtest_results: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return {
            "system": "OmniTrade Pro Institutional AI",
            "portfolio": portfolio_summary or {},
            "backtest_metrics": backtest_results or {},
            "version": "3.0.0"
        }

    @classmethod
    def run(cls, portfolio_summary: Optional[Dict[str, Any]] = None, backtest_results: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return cls.evaluate(portfolio_summary=portfolio_summary, backtest_results=backtest_results)

