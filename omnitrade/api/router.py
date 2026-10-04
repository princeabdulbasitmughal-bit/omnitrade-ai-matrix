"""
OmniTrade API Router & WebSocket Handlers.
Hosts /ws/stream, real-time telemetry, and health check endpoints.
"""

import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse

from omnitrade.api.websocket_manager import ws_manager, WebSocketManager
from omnitrade.api.framing import MsgType

logger = logging.getLogger("OmniTrade.APIRouter")

router = APIRouter(tags=["Stream & API"])

@router.websocket("/ws/stream")
async def websocket_stream_endpoint(websocket: WebSocket):
    """
    Primary High-Frequency WebSocket Stream Endpoint (/ws/stream).
    Serves INIT_STATE on connect, processes client heartbeats (PING/PONG),
    and streams non-blocking MARKET_TICK and AI Swarm updates with zero packet loss.
    """
    session = await ws_manager.connect(websocket)
    try:
        while session.is_active:
            raw_text = await websocket.receive_text()
            await ws_manager.handle_client_message(websocket, raw_text)
    except WebSocketDisconnect:
        await ws_manager.disconnect(websocket)
    except Exception as e:
        logger.debug(f"Client disconnected on error: {e}")
        await ws_manager.disconnect(websocket)

@router.get("/ws/metrics")
async def get_websocket_metrics():
    """Returns real-time telemetry on WebSocket throughput, serialization speed, and packet reliability."""
    return JSONResponse(content=ws_manager.get_metrics())

@router.get("/ws/health")
async def get_websocket_health():
    """Instant health check for the WebSocket broadcast subsystem."""
    metrics = ws_manager.get_metrics()
    return JSONResponse(content={
        "status": "HEALTHY",
        "active_clients": metrics["active_connections"],
        "dropped_packets": metrics["dropped_packets"],
        "avg_serialization_us": metrics["avg_serialization_time_us"],
        "packet_loss_rate_pct": metrics["packet_loss_rate_pct"]
    })
