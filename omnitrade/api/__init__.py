"""
OmniTrade API Subsystem.
Provides enterprise WebSocket broadcast managers, protocol framing, and streaming routers.
"""

from omnitrade.api.framing import (
    serialize_frame,
    deserialize_frame,
    create_envelope,
    MsgType
)
from omnitrade.api.websocket_manager import (
    WebSocketManager,
    ClientSession,
    ws_manager
)
from omnitrade.api.router import router

__all__ = [
    "serialize_frame",
    "deserialize_frame",
    "create_envelope",
    "MsgType",
    "WebSocketManager",
    "ClientSession",
    "ws_manager",
    "router"
]
