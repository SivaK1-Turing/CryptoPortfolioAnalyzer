"""Tests for the event system."""

import asyncio
import json
import pytest
from unittest.mock import Mock, AsyncMock
from datetime import datetime, timezone

from crypto_portfolio_analyzer.streaming.events import (
    StreamEvent, EventType, EventHandler, EventFilter, EventSubscription,
    StreamEventBus, WebSocketEventHandler, DatabaseEventHandler
)


class TestStreamEvent:
    """Test StreamEvent class."""
    
    def test_stream_event_creation(self):
        """Test creating a stream event."""
        event = StreamEvent(
            event_type=EventType.PRICE_UPDATE,
            data={"symbol": "BTC", "price": 50000},
            source="test_source",
            event_id="test_event",
            correlation_id="test_correlation"
        )
        
        assert event.event_type == EventType.PRICE_UPDATE
        assert event.data == {"symbol": "BTC", "price": 50000}
        assert event.source == "test_source"
        assert event.event_id == "test_event"
        assert event.correlation_id == "test_correlation"
        assert isinstance(event.timestamp, datetime)
    
    def test_stream_event_to_dict(self):
        """Test converting event to dictionary."""
        event = StreamEvent(
            event_type=EventType.ALERT_TRIGGERED,
            data={"message": "Test alert"}
        )
        
        result = event.to_dict()
        
        assert result["event_type"] == "alert_triggered"
        assert result["data"] == {"message": "Test alert"}
        assert "timestamp" in result
        assert result["source"] is None
    
    def test_stream_event_to_json(self):
        """Test converting event to JSON."""
        event = StreamEvent(
            event_type=EventType.PORTFOLIO_UPDATE,
            data={"total_value": 100000}
        )
        
        json_str = event.to_json()
        parsed = json.loads(json_str)
        
        assert parsed["event_type"] == "portfolio_update"
        assert parsed["data"] == {"total_value": 100000}


class TestEventFilter:
    """Test EventFilter class."""
    
    def test_event_filter_creation(self):
        """Test creating an event filter."""
        event_filter = EventFilter(
            event_types={EventType.PRICE_UPDATE, EventType.ALERT_TRIGGERED},
            sources={"binance", "coinbase"},
            symbols={"BTC", "ETH"}
        )
        
        assert EventType.PRICE_UPDATE in event_filter.event_types
        assert EventType.ALERT_TRIGGERED in event_filter.event_types
        assert "binance" in event_filter.sources
        assert "BTC" in event_filter.symbols
    
    def test_event_filter_matches_event_type(self):
        """Test filtering by event type."""
        event_filter = EventFilter(event_types={EventType.PRICE_UPDATE})
        
        price_event = StreamEvent(
            event_type=EventType.PRICE_UPDATE,
            data={"symbol": "BTC"}
        )
        
        alert_event = StreamEvent(
            event_type=EventType.ALERT_TRIGGERED,
            data={"message": "Alert"}
        )
        
        assert event_filter.matches(price_event)
        assert not event_filter.matches(alert_event)
    
    def test_event_filter_matches_source(self):
        """Test filtering by source."""
        event_filter = EventFilter(sources={"binance"})
        
        binance_event = StreamEvent(
            event_type=EventType.PRICE_UPDATE,
            data={},
            source="binance"
        )
        
        coinbase_event = StreamEvent(
            event_type=EventType.PRICE_UPDATE,
            data={},
            source="coinbase"
        )
        
        assert event_filter.matches(binance_event)
        assert not event_filter.matches(coinbase_event)
    
    def test_event_filter_matches_symbol(self):
        """Test filtering by symbol."""
        event_filter = EventFilter(symbols={"BTC"})
        
        btc_event = StreamEvent(
            event_type=EventType.PRICE_UPDATE,
            data={"symbol": "BTC"}
        )
        
        eth_event = StreamEvent(
            event_type=EventType.PRICE_UPDATE,
            data={"symbol": "ETH"}
        )
        
        no_symbol_event = StreamEvent(
            event_type=EventType.SYSTEM_STATUS,
            data={"status": "ok"}
        )
        
        assert event_filter.matches(btc_event)
        assert not event_filter.matches(eth_event)
        assert event_filter.matches(no_symbol_event)  # No symbol filter applied
    
    def test_event_filter_custom_filter(self):
        """Test custom filter function."""
        def custom_filter(event):
            return event.data.get("price", 0) > 50000
        
        event_filter = EventFilter(custom_filter=custom_filter)
        
        high_price_event = StreamEvent(
            event_type=EventType.PRICE_UPDATE,
            data={"price": 60000}
        )
        
        low_price_event = StreamEvent(
            event_type=EventType.PRICE_UPDATE,
            data={"price": 40000}
        )
        
        assert event_filter.matches(high_price_event)
        assert not event_filter.matches(low_price_event)
    
    def test_event_filter_empty_filter(self):
        """Test empty filter matches all events."""
        event_filter = EventFilter()
        
        event = StreamEvent(
            event_type=EventType.PRICE_UPDATE,
            data={"symbol": "BTC"}
        )
        
        assert event_filter.matches(event)


class MockEventHandler(EventHandler):
    """Mock event handler for testing."""
    
    def __init__(self, supported_types=None):
        self.handled_events = []
        self.supported_types = supported_types or {EventType.PRICE_UPDATE}
    
    async def handle_event(self, event: StreamEvent) -> bool:
        self.handled_events.append(event)
        return True
    
    def get_supported_event_types(self):
        return self.supported_types


class TestEventSubscription:
    """Test EventSubscription class."""
    
    def test_subscription_creation(self):
        """Test creating an event subscription."""
        handler = MockEventHandler()
        event_filter = EventFilter(event_types={EventType.PRICE_UPDATE})
        
        subscription = EventSubscription(
            subscription_id="test_sub",
            handler=handler,
            event_filter=event_filter,
            priority=5
        )
        
        assert subscription.subscription_id == "test_sub"
        assert subscription.handler == handler
        assert subscription.event_filter == event_filter
        assert subscription.priority == 5
        assert subscription.event_count == 0
        assert subscription.error_count == 0
    
    async def test_subscription_handle_matching_event(self):
        """Test handling matching event."""
        handler = MockEventHandler()
        event_filter = EventFilter(event_types={EventType.PRICE_UPDATE})
        subscription = EventSubscription("test", handler, event_filter)
        
        event = StreamEvent(
            event_type=EventType.PRICE_UPDATE,
            data={"symbol": "BTC"}
        )
        
        result = await subscription.handle_event(event)
        
        assert result is True
        assert subscription.event_count == 1
        assert len(handler.handled_events) == 1
        assert subscription.last_event_time is not None
    
    async def test_subscription_handle_non_matching_event(self):
        """Test handling non-matching event."""
        handler = MockEventHandler()
        event_filter = EventFilter(event_types={EventType.PRICE_UPDATE})
        subscription = EventSubscription("test", handler, event_filter)
        
        event = StreamEvent(
            event_type=EventType.ALERT_TRIGGERED,
            data={"message": "Alert"}
        )
        
        result = await subscription.handle_event(event)
        
        assert result is False
        assert subscription.event_count == 0
        assert len(handler.handled_events) == 0
    
    async def test_subscription_with_function_handler(self):
        """Test subscription with function handler."""
        handled_events = []
        
        def handler_func(event):
            handled_events.append(event)
        
        subscription = EventSubscription("test", handler_func)
        
        event = StreamEvent(
            event_type=EventType.PRICE_UPDATE,
            data={"symbol": "BTC"}
        )
        
        result = await subscription.handle_event(event)
        
        assert result is True
        assert len(handled_events) == 1
    
    async def test_subscription_with_async_function_handler(self):
        """Test subscription with async function handler."""
        handled_events = []
        
        async def async_handler(event):
            handled_events.append(event)
        
        subscription = EventSubscription("test", async_handler)
        
        event = StreamEvent(
            event_type=EventType.PRICE_UPDATE,
            data={"symbol": "BTC"}
        )
        
        result = await subscription.handle_event(event)
        
        assert result is True
        assert len(handled_events) == 1
    
    async def test_subscription_handler_error(self):
        """Test handling errors in event handlers."""
        def error_handler(event):
            raise ValueError("Handler error")
        
        subscription = EventSubscription("test", error_handler)
        
        event = StreamEvent(
            event_type=EventType.PRICE_UPDATE,
            data={"symbol": "BTC"}
        )
        
        result = await subscription.handle_event(event)
        
        assert result is False
        assert subscription.error_count == 1


@pytest.mark.asyncio
class TestStreamEventBus:
    """Test StreamEventBus class."""
    
    @pytest.fixture
    def event_bus(self):
        """Create an event bus."""
        return StreamEventBus(max_queue_size=100)
    
    def test_event_bus_creation(self, event_bus):
        """Test creating an event bus."""
        assert len(event_bus.subscriptions) == 0
        assert event_bus.event_queue.qsize() == 0
        assert len(event_bus.event_history) == 0
        assert not event_bus._running
    
    async def test_start_stop(self, event_bus):
        """Test starting and stopping the event bus."""
        assert not event_bus._running
        
        await event_bus.start()
        assert event_bus._running
        assert event_bus._processor_task is not None
        
        await event_bus.stop()
        assert not event_bus._running
        assert event_bus.event_queue.qsize() == 0
    
    def test_subscribe(self, event_bus):
        """Test subscribing to events."""
        handler = MockEventHandler()
        
        result = event_bus.subscribe("test_sub", handler)
        
        assert result is True
        assert "test_sub" in event_bus.subscriptions
        assert event_bus._stats["active_subscriptions"] == 1
    
    def test_subscribe_duplicate(self, event_bus):
        """Test subscribing with duplicate ID."""
        handler = MockEventHandler()
        
        event_bus.subscribe("test_sub", handler)
        result = event_bus.subscribe("test_sub", handler)
        
        assert result is False
        assert len(event_bus.subscriptions) == 1
    
    def test_unsubscribe(self, event_bus):
        """Test unsubscribing from events."""
        handler = MockEventHandler()
        event_bus.subscribe("test_sub", handler)
        
        result = event_bus.unsubscribe("test_sub")
        
        assert result is True
        assert "test_sub" not in event_bus.subscriptions
        assert event_bus._stats["active_subscriptions"] == 0
    
    def test_unsubscribe_nonexistent(self, event_bus):
        """Test unsubscribing non-existent subscription."""
        result = event_bus.unsubscribe("nonexistent")
        
        assert result is False
    
    async def test_publish_event(self, event_bus):
        """Test publishing an event."""
        await event_bus.start()
        
        event = StreamEvent(
            event_type=EventType.PRICE_UPDATE,
            data={"symbol": "BTC"}
        )
        
        result = await event_bus.publish(event)
        
        assert result is True
        assert event_bus._stats["events_published"] == 1
        
        await event_bus.stop()
    
    async def test_publish_when_stopped(self, event_bus):
        """Test publishing when bus is stopped."""
        event = StreamEvent(
            event_type=EventType.PRICE_UPDATE,
            data={"symbol": "BTC"}
        )
        
        result = await event_bus.publish(event)
        
        assert result is False
    
    async def test_convenience_publish_methods(self, event_bus):
        """Test convenience methods for publishing events."""
        await event_bus.start()
        
        # Test price update
        await event_bus.publish_price_update("BTC", {"price": 50000})
        
        # Test portfolio update
        await event_bus.publish_portfolio_update({"total_value": 100000})
        
        # Test alert
        await event_bus.publish_alert({"message": "Test alert"})
        
        assert event_bus._stats["events_published"] == 3
        
        await event_bus.stop()
    
    async def test_event_processing(self, event_bus):
        """Test event processing and dispatch."""
        handler = MockEventHandler()
        event_bus.subscribe("test_sub", handler)
        
        await event_bus.start()
        
        event = StreamEvent(
            event_type=EventType.PRICE_UPDATE,
            data={"symbol": "BTC"}
        )
        
        await event_bus.publish(event)
        
        # Wait for processing
        await asyncio.sleep(0.1)
        
        await event_bus.stop()
        
        # Event should have been processed
        assert len(handler.handled_events) == 1
        assert event_bus._stats["events_processed"] == 1
        assert len(event_bus.event_history) == 1
    
    async def test_priority_handling(self, event_bus):
        """Test priority-based event handling."""
        handler1 = MockEventHandler()
        handler2 = MockEventHandler()
        
        # Subscribe with different priorities
        event_bus.subscribe("low_priority", handler1, priority=1)
        event_bus.subscribe("high_priority", handler2, priority=10)
        
        await event_bus.start()
        
        event = StreamEvent(
            event_type=EventType.PRICE_UPDATE,
            data={"symbol": "BTC"}
        )
        
        await event_bus.publish(event)
        await asyncio.sleep(0.1)
        
        await event_bus.stop()
        
        # Both handlers should receive the event
        assert len(handler1.handled_events) == 1
        assert len(handler2.handled_events) == 1
    
    def test_get_subscription_stats(self, event_bus):
        """Test getting subscription statistics."""
        handler = MockEventHandler()
        event_bus.subscribe("test_sub", handler)
        
        stats = event_bus.get_subscription_stats("test_sub")
        
        assert stats is not None
        assert stats["subscription_id"] == "test_sub"
        assert stats["event_count"] == 0
        assert stats["error_count"] == 0
        
        # Non-existent subscription
        stats = event_bus.get_subscription_stats("nonexistent")
        assert stats is None
    
    def test_get_bus_stats(self, event_bus):
        """Test getting bus statistics."""
        stats = event_bus.get_bus_stats()
        
        assert "events_published" in stats
        assert "events_processed" in stats
        assert "events_dropped" in stats
        assert "active_subscriptions" in stats
        assert "queue_size" in stats
        assert "history_size" in stats
        assert "running" in stats
    
    def test_get_recent_events(self, event_bus):
        """Test getting recent events."""
        # Add some events to history
        event1 = StreamEvent(EventType.PRICE_UPDATE, {"symbol": "BTC"})
        event2 = StreamEvent(EventType.ALERT_TRIGGERED, {"message": "Alert"})
        
        event_bus.event_history.extend([event1, event2])
        
        # Get all events
        recent = event_bus.get_recent_events()
        assert len(recent) == 2
        
        # Get limited events
        recent = event_bus.get_recent_events(limit=1)
        assert len(recent) == 1
        
        # Get filtered events
        recent = event_bus.get_recent_events(event_type=EventType.PRICE_UPDATE)
        assert len(recent) == 1
        assert recent[0]["event_type"] == "price_update"


@pytest.mark.asyncio
class TestWebSocketEventHandler:
    """Test WebSocketEventHandler class."""
    
    def test_websocket_handler_creation(self):
        """Test creating WebSocket event handler."""
        mock_server = Mock()
        handler = WebSocketEventHandler(mock_server)
        
        supported_types = handler.get_supported_event_types()
        assert EventType.PRICE_UPDATE in supported_types
        assert EventType.PORTFOLIO_UPDATE in supported_types
        assert EventType.ALERT_TRIGGERED in supported_types
    
    async def test_handle_price_update_event(self):
        """Test handling price update event."""
        mock_server = Mock()
        mock_server.broadcast_price_update = AsyncMock()

        # Create handler with the mock server directly
        handler = WebSocketEventHandler(mock_server)

        event = StreamEvent(
            event_type=EventType.PRICE_UPDATE,
            data={"symbol": "BTC", "price": 50000}
        )

        result = await handler.handle_event(event)

        assert result is True
        mock_server.broadcast_price_update.assert_called_once_with("BTC", event.data)
    
    async def test_handle_portfolio_update_event(self):
        """Test handling portfolio update event."""
        mock_server = Mock()
        mock_server.broadcast_portfolio_update = AsyncMock()

        # Create handler with the mock server directly
        handler = WebSocketEventHandler(mock_server)

        event = StreamEvent(
            event_type=EventType.PORTFOLIO_UPDATE,
            data={"total_value": 100000}
        )

        result = await handler.handle_event(event)

        assert result is True
        mock_server.broadcast_portfolio_update.assert_called_once_with(event.data)
    
    async def test_handle_alert_event(self):
        """Test handling alert event."""
        mock_server = Mock()
        mock_server.send_alert = AsyncMock()

        # Create handler with the mock server directly
        handler = WebSocketEventHandler(mock_server)

        event = StreamEvent(
            event_type=EventType.ALERT_TRIGGERED,
            data={"message": "Test alert"}
        )

        result = await handler.handle_event(event)

        assert result is True
        mock_server.send_alert.assert_called_once_with(event.data)


@pytest.mark.asyncio
class TestDatabaseEventHandler:
    """Test DatabaseEventHandler class."""
    
    def test_database_handler_creation(self):
        """Test creating database event handler."""
        mock_db = Mock()
        handler = DatabaseEventHandler(mock_db)
        
        supported_types = handler.get_supported_event_types()
        assert EventType.PRICE_UPDATE in supported_types
        assert EventType.PORTFOLIO_UPDATE in supported_types
        assert EventType.ALERT_TRIGGERED in supported_types
    
    async def test_handle_event(self):
        """Test handling event with database persistence."""
        mock_db = Mock()
        # Create handler with the mock database directly
        handler = DatabaseEventHandler(mock_db)

        event = StreamEvent(
            event_type=EventType.PRICE_UPDATE,
            data={"symbol": "BTC", "price": 50000}
        )

        result = await handler.handle_event(event)

        # For now, just check that it returns True
        # In a real implementation, this would test database operations
        assert result is True
