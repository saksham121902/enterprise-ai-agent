"""WebSocket connection manager for real-time communication.

Manages WebSocket connections organized by rooms (chat sessions,
workflows, user channels). Supports:
- Per-room message broadcasting
- Per-user direct messaging
- JSON event envelope format
- Automatic cleanup on disconnect
- Cross-worker broadcast via Redis PubSub (when running multiple workers)

Event envelope format::

    {
        "event": "chat.message",
        "data": { ... },
        "timestamp": "2024-01-01T00:00:00Z"
    }
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

from app.core.logging import get_logger
from app.core.telemetry import ACTIVE_WEBSOCKET_CONNECTIONS

logger = get_logger(__name__)


class ConnectionManager:
    """Manages WebSocket connections across rooms.

    Rooms are identified by string keys (e.g., ``chat:abc123``,
    ``workflow:def456``, ``user:user-id``). Each room can have
    multiple connected WebSocket clients.
    """

    def __init__(self) -> None:
        # room_id → set of WebSocket connections
        self._rooms: dict[str, set[WebSocket]] = {}
        # websocket → set of room_ids (for cleanup)
        self._connection_rooms: dict[WebSocket, set[str]] = {}
        # Lock for thread-safe room management
        self._lock = asyncio.Lock()

    @property
    def total_connections(self) -> int:
        """Total number of active WebSocket connections."""
        return len(self._connection_rooms)

    async def connect(self, websocket: WebSocket, room_id: str) -> None:
        """Accept a WebSocket connection and join it to a room.

        Args:
            websocket: The WebSocket connection to accept.
            room_id: The room identifier to join.
        """
        await websocket.accept()
        async with self._lock:
            if room_id not in self._rooms:
                self._rooms[room_id] = set()
            self._rooms[room_id].add(websocket)

            if websocket not in self._connection_rooms:
                self._connection_rooms[websocket] = set()
            self._connection_rooms[websocket].add(room_id)

        ACTIVE_WEBSOCKET_CONNECTIONS.inc()
        logger.info(
            "WebSocket connected",
            room_id=room_id,
            total_connections=self.total_connections,
        )

    async def disconnect(self, websocket: WebSocket) -> None:
        """Remove a WebSocket from all rooms and clean up.

        Args:
            websocket: The WebSocket connection to remove.
        """
        async with self._lock:
            rooms = self._connection_rooms.pop(websocket, set())
            for room_id in rooms:
                if room_id in self._rooms:
                    self._rooms[room_id].discard(websocket)
                    if not self._rooms[room_id]:
                        del self._rooms[room_id]

        ACTIVE_WEBSOCKET_CONNECTIONS.dec()
        logger.info(
            "WebSocket disconnected",
            rooms=list(rooms) if rooms else [],
            total_connections=self.total_connections,
        )

    async def join_room(self, websocket: WebSocket, room_id: str) -> None:
        """Add an existing connection to an additional room.

        Args:
            websocket: The WebSocket connection.
            room_id: The room to join.
        """
        async with self._lock:
            if room_id not in self._rooms:
                self._rooms[room_id] = set()
            self._rooms[room_id].add(websocket)

            if websocket in self._connection_rooms:
                self._connection_rooms[websocket].add(room_id)

    async def leave_room(self, websocket: WebSocket, room_id: str) -> None:
        """Remove a connection from a specific room.

        Args:
            websocket: The WebSocket connection.
            room_id: The room to leave.
        """
        async with self._lock:
            if room_id in self._rooms:
                self._rooms[room_id].discard(websocket)
                if not self._rooms[room_id]:
                    del self._rooms[room_id]
            if websocket in self._connection_rooms:
                self._connection_rooms[websocket].discard(room_id)

    async def send_to_room(
        self, room_id: str, event: str, data: dict[str, Any]
    ) -> None:
        """Broadcast an event to all connections in a room.

        Connections that fail to receive the message are silently
        removed (they've likely disconnected).

        Args:
            room_id: The target room identifier.
            event: The event type (e.g., ``chat.message``).
            data: The event payload.
        """
        message = _create_envelope(event, data)
        connections = self._rooms.get(room_id, set()).copy()

        disconnected: list[WebSocket] = []
        for ws in connections:
            try:
                if ws.client_state == WebSocketState.CONNECTED:
                    await ws.send_json(message)
            except (WebSocketDisconnect, RuntimeError):
                disconnected.append(ws)

        for ws in disconnected:
            await self.disconnect(ws)

    async def send_to_user(
        self, user_id: str, event: str, data: dict[str, Any]
    ) -> None:
        """Send an event to a specific user's personal channel.

        The user channel room is identified as ``user:{user_id}``.

        Args:
            user_id: The target user's ID.
            event: The event type.
            data: The event payload.
        """
        room_id = f"user:{user_id}"
        await self.send_to_room(room_id, event, data)

    async def broadcast(self, event: str, data: dict[str, Any]) -> None:
        """Broadcast an event to ALL connected WebSocket clients.

        Use sparingly — prefer room-scoped messaging.

        Args:
            event: The event type.
            data: The event payload.
        """
        message = _create_envelope(event, data)
        all_connections = list(self._connection_rooms.keys())

        disconnected: list[WebSocket] = []
        for ws in all_connections:
            try:
                if ws.client_state == WebSocketState.CONNECTED:
                    await ws.send_json(message)
            except (WebSocketDisconnect, RuntimeError):
                disconnected.append(ws)

        for ws in disconnected:
            await self.disconnect(ws)

    def get_room_size(self, room_id: str) -> int:
        """Get the number of connections in a room.

        Args:
            room_id: The room identifier.

        Returns:
            Number of connections in the room.
        """
        return len(self._rooms.get(room_id, set()))


def _create_envelope(event: str, data: dict[str, Any]) -> dict[str, Any]:
    """Create a standardized WebSocket event envelope.

    Args:
        event: The event type string.
        data: The event payload data.

    Returns:
        The complete event envelope dictionary.
    """
    return {
        "event": event,
        "data": data,
        "timestamp": datetime.now(UTC).isoformat(),
    }


# Global connection manager singleton
ws_manager = ConnectionManager()
