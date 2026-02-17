"""
WebSocket Connection Manager
Handles real-time broadcasting to all connected dashboard clients.
"""

from fastapi import WebSocket, WebSocketDisconnect
from typing import List, Dict
import json
import asyncio
from datetime import datetime


class ConnectionManager:
    """
    Manages WebSocket connections for real-time updates.
    
    Features:
    - Add/remove connections
    - Broadcast messages to all clients
    - Handle disconnections gracefully
    - Send individual messages
    - Track connection metadata
    """
    
    def __init__(self):
        # Store active WebSocket connections with metadata
        self.active_connections: Dict[str, WebSocket] = {}  # Changed to dict
        self.connection_count = 0
    
    def _get_connection_key(self, websocket: WebSocket) -> str:
        """Generate unique key for a WebSocket connection."""
        client_host = websocket.client.host if websocket.client else "unknown"
        client_port = websocket.client.port if websocket.client else 0
        return f"{client_host}:{client_port}"
    
    async def connect(self, websocket: WebSocket):
        """
        Accept a new WebSocket connection.
        
        Args:
            websocket: WebSocket client connection
        """
        try:
            await websocket.accept()
            
            # Generate unique key
            conn_key = self._get_connection_key(websocket)
            
            # Remove old connection from same client (if exists)
            if conn_key in self.active_connections:
                old_ws = self.active_connections[conn_key]
                try:
                    await old_ws.close()
                except:
                    pass
                print(f"🔄 Replaced existing connection from {conn_key}")
            
            self.active_connections[conn_key] = websocket
            self.connection_count += 1
            
            print(f"✅ WebSocket connected. Total connections: {len(self.active_connections)}")
            
            # Send welcome message
            await self.send_personal_message(
                {
                    "event": "connected",
                    "message": "Connected to Smart Care Medical Center",
                    "timestamp": datetime.now().isoformat(),
                    "connection_id": self.connection_count
                },
                websocket
            )
        except Exception as e:
            print(f"❌ Error accepting WebSocket connection: {e}")
            conn_key = self._get_connection_key(websocket)
            if conn_key in self.active_connections:
                del self.active_connections[conn_key]
    
    def disconnect(self, websocket: WebSocket):
        """
        Remove a WebSocket connection.
        
        Args:
            websocket: WebSocket client to disconnect
        """
        conn_key = self._get_connection_key(websocket)
        if conn_key in self.active_connections:
            del self.active_connections[conn_key]
            print(f"🔌 WebSocket disconnected. Total connections: {len(self.active_connections)}")
    
    async def send_personal_message(self, message: dict, websocket: WebSocket):
        """
        Send a message to a specific client.
        
        Args:
            message: Dictionary to send as JSON
            websocket: Target WebSocket connection
        """
        try:
            # Check if websocket is still connected
            if websocket.client_state.name == "CONNECTED":
                await websocket.send_json(message)
            else:
                self.disconnect(websocket)
        except WebSocketDisconnect:
            self.disconnect(websocket)
        except RuntimeError as e:
            if "WebSocket is not connected" in str(e):
                self.disconnect(websocket)
            else:
                print(f"❌ Runtime error sending message: {e}")
                self.disconnect(websocket)
        except Exception as e:
            print(f"❌ Error sending message to client: {e}")
            self.disconnect(websocket)
    
    async def broadcast(self, message: dict, skip_failed: bool = True):
        """
        Broadcast a message to all connected clients.
        
        This method handles disconnections gracefully by removing
        failed connections from the active list.
        
        Args:
            message: Dictionary to broadcast as JSON
            skip_failed: If True, silently skip failed connections
        """
        if not self.active_connections:
            print("⚠️ No active WebSocket connections to broadcast to")
            return
        
        print(f"📡 Broadcasting to {len(self.active_connections)} client(s): {message.get('event', 'unknown')}")
        
        # Track disconnected clients
        disconnected_keys = []
        
        # Send to all active connections
        for conn_key, connection in list(self.active_connections.items()):
            try:
                # Check connection state before sending
                if connection.client_state.name != "CONNECTED":
                    disconnected_keys.append(conn_key)
                    continue
                
                await connection.send_json(message)
                
            except WebSocketDisconnect:
                disconnected_keys.append(conn_key)
            except RuntimeError as e:
                if "WebSocket is not connected" in str(e):
                    disconnected_keys.append(conn_key)
                else:
                    print(f"❌ Runtime error during broadcast: {e}")
                    disconnected_keys.append(conn_key)
            except Exception as e:
                if not skip_failed:
                    print(f"❌ Failed to send to client {conn_key}: {e}")
                disconnected_keys.append(conn_key)
        
        # Remove disconnected clients
        for conn_key in disconnected_keys:
            if conn_key in self.active_connections:
                del self.active_connections[conn_key]
                print(f"🗑️ Removed disconnected client: {conn_key}")
    
    async def broadcast_new_booking(
        self,
        patient_name: str,
        appointment_time: str,
        reason: str,
        appointment_id: int,
        phone_number: str = None
    ):
        """
        Broadcast a new booking event to all connected dashboards.
        
        Args:
            patient_name: Patient's name
            appointment_time: Formatted appointment time
            reason: Reason for appointment
            appointment_id: Appointment ID
            phone_number: Patient's phone number (optional)
        """
        message = {
            "event": "new_booking",
            "data": {
                "id": appointment_id,
                "patient": patient_name,
                "time": appointment_time,
                "reason": reason,
                "phone": phone_number,
                "timestamp": datetime.now().isoformat(),
                "status": "confirmed"
            }
        }
        
        await self.broadcast(message)
    
    async def broadcast_cancellation(
        self,
        patient_name: str,
        appointment_time: str,
        appointment_id: int,
        canceled_count: int
    ):
        """
        Broadcast a cancellation event to all connected dashboards.
        
        Args:
            patient_name: Patient's name
            appointment_time: Canceled appointment time
            appointment_id: Appointment ID
            canceled_count: Number of appointments canceled
        """
        message = {
            "event": "booking_canceled",
            "data": {
                "id": appointment_id,
                "patient": patient_name,
                "time": appointment_time,
                "canceled_count": canceled_count,
                "timestamp": datetime.now().isoformat(),
                "status": "canceled"
            }
        }
        
        await self.broadcast(message)
    
    async def broadcast_system_message(self, message_text: str, level: str = "info"):
        """
        Broadcast a system message (info, warning, error).
        
        Args:
            message_text: Message content
            level: Message level (info, warning, error)
        """
        message = {
            "event": "system_message",
            "data": {
                "message": message_text,
                "level": level,
                "timestamp": datetime.now().isoformat()
            }
        }
        
        await self.broadcast(message)
    
    def get_connection_count(self) -> int:
        """Get the number of active connections."""
        return len(self.active_connections)
    
    async def cleanup_dead_connections(self):
        """Remove any connections that are no longer active."""
        dead_keys = [
            key for key, conn in self.active_connections.items()
            if conn.client_state.name != "CONNECTED"
        ]
        
        for key in dead_keys:
            del self.active_connections[key]
        
        if dead_keys:
            print(f"🧹 Cleaned up {len(dead_keys)} dead connection(s)")


# Global instance
manager = ConnectionManager()


# Helper function to broadcast from non-async code
def broadcast_sync(message: dict):
    """
    Synchronous wrapper for broadcasting.
    Use this when calling from non-async functions.
    """
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.create_task(manager.broadcast(message))
        else:
            loop.run_until_complete(manager.broadcast(message))
    except Exception as e:
        print(f"❌ Error broadcasting message: {e}")