#!/usr/bin/env python3
"""
WebSocket Client Example

This example demonstrates how to connect to the Crypto Portfolio Analyzer
WebSocket server and receive real-time updates.
"""

import asyncio
import json
import logging
import websockets
from datetime import datetime
from typing import Dict, Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class StreamingClient:
    """WebSocket client for receiving real-time updates."""
    
    def __init__(self, server_url: str = "ws://localhost:8000/ws"):
        self.server_url = server_url
        self.websocket = None
        self.running = False
        self.message_handlers = {}
        self.stats = {
            'messages_received': 0,
            'price_updates': 0,
            'portfolio_updates': 0,
            'alerts': 0,
            'errors': 0
        }
    
    def add_message_handler(self, message_type: str, handler):
        """Add a handler for specific message types."""
        if message_type not in self.message_handlers:
            self.message_handlers[message_type] = []
        self.message_handlers[message_type].append(handler)
    
    async def connect(self):
        """Connect to the WebSocket server."""
        try:
            logger.info(f"Connecting to {self.server_url}")
            self.websocket = await websockets.connect(self.server_url)
            self.running = True
            logger.info("Connected to streaming server")
            return True
        except Exception as e:
            logger.error(f"Failed to connect: {e}")
            return False
    
    async def disconnect(self):
        """Disconnect from the WebSocket server."""
        self.running = False
        if self.websocket:
            await self.websocket.close()
            logger.info("Disconnected from streaming server")
    
    async def send_message(self, message: Dict[str, Any]):
        """Send a message to the server."""
        if self.websocket and not self.websocket.closed:
            try:
                await self.websocket.send(json.dumps(message))
                logger.debug(f"Sent message: {message}")
            except Exception as e:
                logger.error(f"Failed to send message: {e}")
    
    async def join_room(self, room: str):
        """Join a specific room for targeted updates."""
        await self.send_message({
            "type": "join_room",
            "room": room
        })
        logger.info(f"Joined room: {room}")
    
    async def leave_room(self, room: str):
        """Leave a specific room."""
        await self.send_message({
            "type": "leave_room",
            "room": room
        })
        logger.info(f"Left room: {room}")
    
    async def handle_message(self, message_data: Dict[str, Any]):
        """Handle incoming messages from the server."""
        message_type = message_data.get('type', 'unknown')
        
        # Update statistics
        self.stats['messages_received'] += 1
        if message_type == 'price_update':
            self.stats['price_updates'] += 1
        elif message_type == 'portfolio_update':
            self.stats['portfolio_updates'] += 1
        elif message_type == 'alert':
            self.stats['alerts'] += 1
        elif message_type == 'error':
            self.stats['errors'] += 1
        
        # Call registered handlers
        handlers = self.message_handlers.get(message_type, [])
        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(message_data)
                else:
                    handler(message_data)
            except Exception as e:
                logger.error(f"Error in message handler: {e}")
    
    async def listen(self):
        """Listen for messages from the server."""
        try:
            async for message in self.websocket:
                if not self.running:
                    break
                
                try:
                    data = json.loads(message)
                    await self.handle_message(data)
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse message: {e}")
                except Exception as e:
                    logger.error(f"Error handling message: {e}")
        
        except websockets.exceptions.ConnectionClosed:
            logger.info("Connection closed by server")
        except Exception as e:
            logger.error(f"Error in listen loop: {e}")
        finally:
            self.running = False
    
    def print_stats(self):
        """Print client statistics."""
        print("\n" + "="*50)
        print("CLIENT STATISTICS")
        print("="*50)
        for key, value in self.stats.items():
            print(f"{key.replace('_', ' ').title():>20}: {value}")
        print("="*50)


# Message handlers
def handle_price_update(message: Dict[str, Any]):
    """Handle price update messages."""
    data = message.get('data', {})
    symbol = data.get('symbol', 'Unknown')
    price = data.get('price', 0)
    change_percent = data.get('change_percent_24h', 0)
    timestamp = message.get('timestamp', '')
    
    change_str = f" ({change_percent:+.2f}%)" if change_percent else ""
    print(f"💰 {symbol}: ${price:.2f}{change_str} at {timestamp}")


def handle_portfolio_update(message: Dict[str, Any]):
    """Handle portfolio update messages."""
    data = message.get('data', {})
    total_value = data.get('total_value', 0)
    total_change = data.get('total_change_percent_24h', 0)
    timestamp = message.get('timestamp', '')
    
    change_str = f" ({total_change:+.2f}%)" if total_change else ""
    print(f"📊 Portfolio: ${total_value:.2f}{change_str} at {timestamp}")


def handle_alert(message: Dict[str, Any]):
    """Handle alert messages."""
    data = message.get('data', {})
    alert_message = data.get('message', 'Alert triggered')
    severity = data.get('severity', 'info')
    timestamp = message.get('timestamp', '')
    
    emoji = "🚨" if severity == "critical" else "⚠️" if severity == "warning" else "ℹ️"
    print(f"{emoji} Alert: {alert_message} at {timestamp}")


def handle_status(message: Dict[str, Any]):
    """Handle status messages."""
    data = message.get('data', {})
    status = data.get('status', 'unknown')
    print(f"📡 Status: {status}")


def handle_error(message: Dict[str, Any]):
    """Handle error messages."""
    data = message.get('data', {})
    error_message = data.get('message', 'Unknown error')
    error_code = data.get('code', 'UNKNOWN')
    print(f"❌ Error [{error_code}]: {error_message}")


async def main():
    """Main function demonstrating WebSocket client usage."""
    # Create client
    client = StreamingClient("ws://localhost:8000/ws")
    
    # Register message handlers
    client.add_message_handler('price_update', handle_price_update)
    client.add_message_handler('portfolio_update', handle_portfolio_update)
    client.add_message_handler('alert', handle_alert)
    client.add_message_handler('status', handle_status)
    client.add_message_handler('error', handle_error)
    
    try:
        # Connect to server
        if not await client.connect():
            logger.error("Failed to connect to server")
            return
        
        # Join rooms for specific updates
        await client.join_room('prices')
        await client.join_room('portfolio')
        await client.join_room('alerts')
        
        print("\n🚀 Connected to streaming server!")
        print("Listening for real-time updates... (Press Ctrl+C to stop)")
        print("-" * 60)
        
        # Listen for messages
        await client.listen()
        
    except KeyboardInterrupt:
        print("\n\n👋 Disconnecting...")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
    finally:
        # Clean up
        await client.disconnect()
        client.print_stats()


if __name__ == "__main__":
    # Run the client
    asyncio.run(main())
