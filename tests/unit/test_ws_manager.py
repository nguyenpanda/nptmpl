import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi import WebSocket
from nptmpl.server.ws import ConnectionManager

@pytest.mark.asyncio
async def test_manager_connect_disconnect():
    manager = ConnectionManager()
    websocket = AsyncMock(spec=WebSocket)
    websocket.scope = {"headers": []}
    
    # Test connect
    await manager.connect(websocket)
    assert websocket in manager.active_connections
    websocket.accept.assert_called_once()
    
    # Test disconnect
    manager.disconnect(websocket)
    assert websocket not in manager.active_connections

@pytest.mark.asyncio
async def test_manager_broadcast():
    manager = ConnectionManager()
    ws1 = AsyncMock(spec=WebSocket)
    ws1.scope = {"headers": []}
    ws2 = AsyncMock(spec=WebSocket)
    ws2.scope = {"headers": []}
    
    await manager.connect(ws1)
    await manager.connect(ws2)
    
    message = {"type": "test", "data": "hello"}
    await manager.broadcast(message)
    
    ws1.send_json.assert_called_with(message)
    ws2.send_json.assert_called_with(message)

@pytest.mark.asyncio
async def test_manager_broadcast_failure_cleanup():
    manager = ConnectionManager()
    ws_good = AsyncMock(spec=WebSocket)
    ws_good.scope = {"headers": []}
    ws_bad = AsyncMock(spec=WebSocket)
    ws_bad.scope = {"headers": []}
    
    # Simulate failure for ws_bad
    ws_bad.send_json.side_effect = Exception("Connection lost")
    
    await manager.connect(ws_good)
    await manager.connect(ws_bad)
    
    await manager.broadcast({"type": "update"})
    
    # ws_bad should have been disconnected after failure
    assert ws_bad not in manager.active_connections
    assert ws_good in manager.active_connections
    ws_good.send_json.assert_called()
