"""
OmniTrade Execution Bridge - Order Manager Module
Re-exports OrderManager from core.order_manager with full backwards and forwards compatibility.
"""
import sys
import os

# Ensure project root is in sys.path
_current_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(os.path.dirname(_current_dir))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from core.order_manager import OrderManager, logger

__all__ = ["OrderManager", "logger"]
