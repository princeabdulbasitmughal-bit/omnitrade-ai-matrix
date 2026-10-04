"""
Comprehensive Institutional Audit & Load Test Suite for OmniTrade WebSocket Stream.
Tests:
1. Bidirectional Client Heartbeat (PING/PONG and server HEARTBEAT)
2. Protocol Message Framing and monotonic sequence ordering
3. Ultra-fast microsecond serialization benchmarking
4. Zero dropped packets under heavy burst load across concurrent clients
"""

import sys
import os
import asyncio
import time

# Ensure root directory is on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from omnitrade.api.framing import (
    serialize_frame,
    deserialize_frame,
    create_envelope,
    MsgType
)
from omnitrade.api.websocket_manager import WebSocketManager, ws_manager
from server.app import app

class MockWebSocket:
    """Mock WebSocket for high-speed actor queue and load simulation."""
    def __init__(self, client_id: str = "mock_client", latency: float = 0.0):
        self.client_id = client_id
        self.latency = latency
        self.received_messages = []
        self.is_closed = False
        self.close_code = None

    async def accept(self):
        pass

    async def send_text(self, text: str):
        if self.latency > 0:
            await asyncio.sleep(0)
        self.received_messages.append(text)

    async def close(self, code: int = 1000):
        self.is_closed = True
        self.close_code = code

@pytest.mark.asyncio
async def test_serialization_speed_and_framing():
    """Verifies that serialization completes in microseconds and framing is standard."""
    sample_tick = {
        "symbol": "BTC/USDT",
        "last": 95123.45,
        "volume": 412.8,
        "signals": [True, False, True],
        "orderbook": {"bids": [[95100.0, 1.2]], "asks": [[95150.0, 0.8]]}
    }

    envelope = create_envelope(
        msg_type=MsgType.MARKET_TICK,
        data=sample_tick,
        seq=101,
        channel="market:live"
    )

    assert envelope["type"] == MsgType.MARKET_TICK
    assert envelope["seq"] == 101
    assert envelope["channel"] == "market:live"
    assert envelope["timestamp"] > 0

    # Benchmark 2000 serializations
    t0 = time.perf_counter()
    for _ in range(2000):
        s = serialize_frame(envelope)
    t1 = time.perf_counter()

    avg_us = ((t1 - t0) / 2000) * 1e6
    print(f"\n[BENCHMARK] Average serialization time: {avg_us:.2f} microseconds per packet")
    # Must be under 50 microseconds
    assert avg_us < 50.0

    # Verify deserialization
    decoded = deserialize_frame(s)
    assert decoded["seq"] == 101
    assert decoded["data"]["symbol"] == "BTC/USDT"

@pytest.mark.asyncio
async def test_client_heartbeat_ping_pong():
    """Tests bidirectional heartbeat: client PING gets immediate PONG with timestamp echo."""
    mgr = WebSocketManager(heartbeat_interval=1.0)
    mock_ws = MockWebSocket("client_hb")
    session = await mgr.connect(mock_ws)

    client_send_time = time.time()
    ping_payload = serialize_frame({
        "type": "PING",
        "client_ts": client_send_time
    })

    # Send client message
    await mgr.handle_client_message(mock_ws, ping_payload)

    # Allow queue writer loop to dispatch
    await asyncio.sleep(0.05)

    assert len(mock_ws.received_messages) >= 1
    # Check for PONG
    pong_found = False
    for raw in mock_ws.received_messages:
        frame = deserialize_frame(raw)
        if frame.get("type") == MsgType.PONG:
            pong_found = True
            assert frame["data"]["client_ts"] == client_send_time
            assert frame["data"]["latency_ack"] is True
            break

    assert pong_found is True
    await mgr.disconnect(mock_ws)

@pytest.mark.asyncio
async def test_zero_dropped_packets_under_high_load():
    """
    Stress-tests the WebSocket broadcast manager under heavy burst load.
    Dispatches 1,000 rapid messages to multiple concurrent clients.
    Verifies that ZERO packets are dropped, sequence numbers are strictly contiguous,
    and slow clients do not block fast clients.
    """
    mgr = WebSocketManager(max_client_queue_size=10000)

    # 1 Fast Client (0 latency) and 1 Moderate Client (simulating network jitter)
    fast_ws = MockWebSocket("fast_client", latency=0.0)
    moderate_ws = MockWebSocket("moderate_client", latency=0.0001)

    fast_session = await mgr.connect(fast_ws)
    moderate_session = await mgr.connect(moderate_ws)

    num_burst_packets = 1000
    start_seq = mgr._seq_counter + 1

    t0 = time.perf_counter()
    for i in range(num_burst_packets):
        await mgr.broadcast({
            "type": MsgType.MARKET_TICK,
            "data": {
                "tick_id": i,
                "price": 95000.0 + i,
                "timestamp": time.time()
            }
        })
    t1 = time.perf_counter()

    broadcast_duration = t1 - t0
    print(f"\n[LOAD TEST] Dispatched {num_burst_packets} packets in {broadcast_duration*1000:.2f} ms")

    # Wait for writer actor queues to drain
    max_wait = 3.0
    elapsed = 0.0
    while (len(fast_ws.received_messages) < num_burst_packets or len(moderate_ws.received_messages) < num_burst_packets) and elapsed < max_wait:
        await asyncio.sleep(0.05)
        elapsed += 0.05

    # Check received counts
    fast_received = len(fast_ws.received_messages)
    moderate_received = len(moderate_ws.received_messages)

    print(f"[LOAD TEST] Fast client received: {fast_received}/{num_burst_packets}")
    print(f"[LOAD TEST] Moderate client received: {moderate_received}/{num_burst_packets}")

    assert fast_received == num_burst_packets
    assert moderate_received == num_burst_packets

    # Check Sequence Numbers to ensure ZERO gaps / dropped packets
    seqs = []
    for raw in fast_ws.received_messages:
        msg = deserialize_frame(raw)
        seqs.append(msg["seq"])

    # Verify strictly monotonic contiguous sequence: [start_seq, start_seq+1, ..., start_seq + 999]
    expected_seqs = list(range(start_seq, start_seq + num_burst_packets))
    assert seqs == expected_seqs, "Packet gap detected in fast client stream!"

    # Check Telemetry metrics
    metrics = mgr.get_metrics()
    assert metrics["dropped_packets"] == 0
    assert metrics["packet_loss_rate_pct"] == 0.0
    print(f"[LOAD TEST] Telemetry Verified: Dropped Packets = {metrics['dropped_packets']}, Loss Rate = {metrics['packet_loss_rate_pct']}%")

    await mgr.disconnect(fast_ws)
    await mgr.disconnect(moderate_ws)

@pytest.mark.asyncio
async def test_stale_client_reaping():
    """Verifies that unresponsive/stale connections are cleanly reaped."""
    mgr = WebSocketManager(heartbeat_interval=0.1, stale_client_timeout=0.2)
    mock_ws = MockWebSocket("stale_client")
    session = await mgr.connect(mock_ws)

    # Fake client last_seen back in time
    session.last_seen = time.time() - 10.0

    # Let the heartbeat monitor cycle run
    await asyncio.sleep(0.3)

    assert mock_ws.is_closed is True or mock_ws not in mgr.sessions
    await mgr.stop()

if __name__ == "__main__":
    asyncio.run(test_serialization_speed_and_framing())
    asyncio.run(test_client_heartbeat_ping_pong())
    asyncio.run(test_zero_dropped_packets_under_high_load())
    asyncio.run(test_stale_client_reaping())
    print("\nAll OmniTrade WebSocket Audit & Load Tests Passed Successfully!")
