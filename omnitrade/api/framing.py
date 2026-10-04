"""
High-Performance Message Framing and Serialization Engine for OmniTrade.
Optimized with orjson C-extensions for microsecond serialization and zero allocation overhead.
"""

import time
import logging
from typing import Any, Dict, Optional, Union
from datetime import datetime, date

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False

try:
    import orjson
    HAS_ORJSON = True
except ImportError:
    HAS_ORJSON = False
    import json

logger = logging.getLogger("OmniTrade.Framing")

# Standardized Protocol Message Types
class MsgType:
    INIT_STATE = "INIT_STATE"
    MARKET_TICK = "MARKET_TICK"
    ORDER_UPDATE = "ORDER_UPDATE"
    TRADE_ALERT = "TRADE_ALERT"
    EVOLUTION_UPDATE = "EVOLUTION_UPDATE"
    HEARTBEAT = "HEARTBEAT"
    PING = "PING"
    PONG = "PONG"
    SUBSCRIBE = "SUBSCRIBE"
    SUBSCRIPTION_ACK = "SUBSCRIPTION_ACK"
    UNSUBSCRIBE = "UNSUBSCRIBE"
    REQUEST_SNAPSHOT = "REQUEST_SNAPSHOT"
    ERROR = "ERROR"

def _default_serializer(obj: Any) -> Any:
    """Fast fallback serializer for non-primitive types."""
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if HAS_PANDAS and isinstance(obj, pd.Timestamp):
        return obj.isoformat()
    if HAS_NUMPY:
        if isinstance(obj, (np.floating, np.float32, np.float64)):
            return float(obj) if not np.isnan(obj) else 0.0
        if isinstance(obj, (np.integer, np.int64, np.int32)):
            return int(obj)
        if isinstance(obj, (np.bool_, bool)):
            return bool(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
    if hasattr(obj, "to_dict") and callable(obj.to_dict):
        return obj.to_dict()
    if hasattr(obj, "__dict__"):
        return obj.__dict__
    if isinstance(obj, (set, frozenset)):
        return list(obj)
    if hasattr(obj, "item") and callable(obj.item):
        return obj.item()
    return str(obj)

def serialize_frame(data: Any) -> str:
    """
    Serializes a message payload to a UTF-8 JSON string at microsecond latency.
    Employs orjson with C-native NumPy vectorization when available.
    """
    if HAS_ORJSON:
        try:
            return orjson.dumps(
                data,
                default=_default_serializer,
                option=orjson.OPT_SERIALIZE_NUMPY | orjson.OPT_NON_STR_KEYS
            ).decode("utf-8")
        except Exception as e:
            logger.debug(f"orjson serialization fallback triggered: {e}")
            import json
            return json.dumps(data, default=_default_serializer)
    else:
        import json
        return json.dumps(data, default=_default_serializer)

def deserialize_frame(raw: Union[str, bytes]) -> Dict[str, Any]:
    """
    Deserializes raw incoming WebSocket text or bytes to a Python dictionary.
    Handles malformed JSON and plain text commands.
    """
    if isinstance(raw, str):
        trimmed = raw.strip()
        if trimmed.lower() == "ping":
            return {"type": MsgType.PING, "raw": "ping"}
        if trimmed.lower() == "pong":
            return {"type": MsgType.PONG, "raw": "pong"}

    try:
        if HAS_ORJSON:
            return orjson.loads(raw)
        else:
            import json
            return json.loads(raw)
    except Exception:
        return {"type": "RAW_TEXT", "payload": str(raw)}

def create_envelope(
    msg_type: str,
    data: Optional[Any] = None,
    seq: int = 0,
    channel: str = "all",
    **extra
) -> Dict[str, Any]:
    """
    Constructs a standardized, backwards-compatible protocol envelope.
    Includes monotonic sequence number, high-resolution timestamp, and routing channel.
    """
    envelope = {
        "type": msg_type,
        "seq": seq,
        "timestamp": time.time(),
        "channel": channel,
        "data": data if data is not None else {}
    }
    if extra:
        envelope.update(extra)
    return envelope
