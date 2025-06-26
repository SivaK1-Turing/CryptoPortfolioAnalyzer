"""
Unit tests for the event bus system.

Tests event publishing, subscription, async handling, and lifecycle management.
"""

import asyncio
import pytest
from unittest.mock import Mock, AsyncMock
from datetime import datetime

from crypto_portfolio_analyzer.core.events import (
    EventBus, Event, EventType, get_event_bus, start_event_bus, stop_event_bus
)


class TestEvent:
    """Test the Event data structure."""
    
    def test_event_creation(self):
        """Test basic event creation."""
        event = Event(
            event_type=EventType.PLUGIN_LOADED,
            source="test_source",
            data={"key": "value"},
            timestamp=datetime.now()
        )
        
        assert event.event_type == EventType.PLUGIN_LOADED
        assert event.source == "test_source"
        assert event.data == {"key": "value"}
        assert event.event_id is not None
        assert event.metadata == {}
    
    def test_event_auto_id_generation(self):
        """Test automatic event ID generation."""
        event = Event(
            event_type=EventType.COMMAND_START,
            source="test",
            data={},
            timestamp=datetime.now()
        )
        
        assert event.event_id is not None
        assert len(event.event_id) > 0
    
    def test_event_with_custom_metadata(self):
        """Test event creation with custom metadata."""
        metadata = {"correlation_id": "test-123", "user_id": "user-456"}
        event = Event(
            event_type=EventType.COMMAND_END,
            source="test",
            data={},
            timestamp=datetime.now(),
            metadata=metadata
        )
        
        assert event.metadata == metadata


class TestEventBus:
    """Test the EventBus class."""
    
    @pytest.mark.asyncio
    async def test_event_bus_lifecycle(self):
        """Test event bus start and stop."""
        bus = EventBus()
        
        assert bus._running is False
        
        await bus.start()
        assert bus._running is True
        
        await bus.stop()
        assert bus._running is False
    
    @pytest.mark.asyncio
    async def test_subscribe_and_publish(self):
        """Test basic event subscription and publishing."""
        bus = EventBus()
        await bus.start()
        
        # Track received events
        received_events = []
        
        def handler(event):
            received_events.append(event)
        
        # Subscribe to events
        bus.subscribe(EventType.PLUGIN_LOADED, handler)
        
        # Publish an event
        test_event = Event(
            event_type=EventType.PLUGIN_LOADED,
            source="test",
            data={"plugin_name": "test_plugin"},
            timestamp=datetime.now()
        )
        
        await bus.publish(test_event)
        
        # Wait for event processing
        await asyncio.sleep(0.1)
        
        assert len(received_events) == 1
        assert received_events[0].event_type == EventType.PLUGIN_LOADED
        assert received_events[0].data["plugin_name"] == "test_plugin"
        
        await bus.stop()
    
    @pytest.mark.asyncio
    async def test_async_event_handler(self):
        """Test async event handlers."""
        bus = EventBus()
        await bus.start()
        
        received_events = []
        
        async def async_handler(event):
            await asyncio.sleep(0.01)  # Simulate async work
            received_events.append(event)
        
        bus.subscribe(EventType.COMMAND_START, async_handler)
        
        await bus.publish_event(
            EventType.COMMAND_START,
            "test",
            {"command": "test_command"}
        )
        
        # Wait for async processing
        await asyncio.sleep(0.1)
        
        assert len(received_events) == 1
        assert received_events[0].data["command"] == "test_command"
        
        await bus.stop()
    
    @pytest.mark.asyncio
    async def test_multiple_subscribers(self):
        """Test multiple subscribers to the same event type."""
        bus = EventBus()
        await bus.start()
        
        handler1_calls = []
        handler2_calls = []
        
        def handler1(event):
            handler1_calls.append(event)
        
        def handler2(event):
            handler2_calls.append(event)
        
        bus.subscribe(EventType.PLUGIN_LOADED, handler1)
        bus.subscribe(EventType.PLUGIN_LOADED, handler2)
        
        await bus.publish_event(
            EventType.PLUGIN_LOADED,
            "test",
            {"plugin": "test"}
        )
        
        await asyncio.sleep(0.1)
        
        assert len(handler1_calls) == 1
        assert len(handler2_calls) == 1
        
        await bus.stop()
    
    @pytest.mark.asyncio
    async def test_unsubscribe(self):
        """Test event unsubscription."""
        bus = EventBus()
        await bus.start()
        
        received_events = []
        
        def handler(event):
            received_events.append(event)
        
        # Subscribe and then unsubscribe
        bus.subscribe(EventType.PLUGIN_LOADED, handler)
        bus.unsubscribe(EventType.PLUGIN_LOADED, handler)
        
        await bus.publish_event(
            EventType.PLUGIN_LOADED,
            "test",
            {"plugin": "test"}
        )
        
        await asyncio.sleep(0.1)
        
        # Should not receive any events
        assert len(received_events) == 0
        
        await bus.stop()
    
    @pytest.mark.asyncio
    async def test_weak_references(self):
        """Test weak reference handling for subscribers."""
        bus = EventBus()
        await bus.start()
        
        class TestHandler:
            def __init__(self):
                self.events = []
            
            def handle_event(self, event):
                self.events.append(event)
        
        # Create handler and subscribe with weak reference
        handler = TestHandler()
        bus.subscribe(EventType.PLUGIN_LOADED, handler.handle_event, weak=True)
        
        # Publish event - should work
        await bus.publish_event(EventType.PLUGIN_LOADED, "test", {})
        await asyncio.sleep(0.1)
        assert len(handler.events) == 1
        
        # Delete handler reference
        del handler
        
        # Publish another event - weak reference should be cleaned up
        await bus.publish_event(EventType.PLUGIN_LOADED, "test", {})
        await asyncio.sleep(0.1)
        
        # Check that weak reference was cleaned up
        assert EventType.PLUGIN_LOADED.value not in bus._weak_handlers or \
               len(bus._weak_handlers[EventType.PLUGIN_LOADED.value]) == 0
        
        await bus.stop()
    
    @pytest.mark.asyncio
    async def test_error_handling_in_handlers(self):
        """Test error handling when event handlers fail."""
        bus = EventBus()
        await bus.start()
        
        def failing_handler(event):
            raise ValueError("Handler failed")
        
        def working_handler(event):
            working_handler.called = True
        
        working_handler.called = False
        
        # Subscribe both handlers
        bus.subscribe(EventType.PLUGIN_LOADED, failing_handler)
        bus.subscribe(EventType.PLUGIN_LOADED, working_handler)
        
        # Publish event
        await bus.publish_event(EventType.PLUGIN_LOADED, "test", {})
        await asyncio.sleep(0.1)
        
        # Working handler should still be called despite failing handler
        assert working_handler.called is True
        
        # Error count should be incremented
        stats = bus.get_stats()
        assert stats['errors'] > 0
        
        await bus.stop()
    
    @pytest.mark.asyncio
    async def test_custom_event_types(self):
        """Test using custom event types (strings)."""
        bus = EventBus()
        await bus.start()
        
        received_events = []
        
        def handler(event):
            received_events.append(event)
        
        # Subscribe to custom event type
        bus.subscribe("custom_event", handler)
        
        await bus.publish_event("custom_event", "test", {"custom": "data"})
        await asyncio.sleep(0.1)
        
        assert len(received_events) == 1
        assert received_events[0].event_type == "custom_event"
        
        await bus.stop()
    
    def test_get_handler_count(self):
        """Test getting handler counts."""
        bus = EventBus()
        
        def handler1(event):
            pass
        
        def handler2(event):
            pass
        
        # Subscribe handlers
        bus.subscribe(EventType.PLUGIN_LOADED, handler1)
        bus.subscribe(EventType.PLUGIN_LOADED, handler2)
        bus.subscribe(EventType.COMMAND_START, handler1)
        
        # Test specific event type count
        assert bus.get_handler_count(EventType.PLUGIN_LOADED) == 2
        assert bus.get_handler_count(EventType.COMMAND_START) == 1
        assert bus.get_handler_count(EventType.COMMAND_END) == 0
        
        # Test total count
        assert bus.get_handler_count() == 3
    
    def test_get_stats(self):
        """Test getting event bus statistics."""
        bus = EventBus()
        
        stats = bus.get_stats()
        
        assert 'events_published' in stats
        assert 'events_processed' in stats
        assert 'handlers_called' in stats
        assert 'errors' in stats
        
        # All should start at 0
        assert all(count == 0 for count in stats.values())
    
    @pytest.mark.asyncio
    async def test_publish_convenience_method(self):
        """Test the publish_event convenience method."""
        bus = EventBus()
        await bus.start()
        
        received_events = []
        
        def handler(event):
            received_events.append(event)
        
        bus.subscribe(EventType.PLUGIN_LOADED, handler)
        
        # Use convenience method
        await bus.publish_event(
            EventType.PLUGIN_LOADED,
            "test_source",
            {"key": "value"},
            correlation_id="test-123"
        )
        
        await asyncio.sleep(0.1)
        
        assert len(received_events) == 1
        event = received_events[0]
        assert event.event_type == EventType.PLUGIN_LOADED
        assert event.source == "test_source"
        assert event.data == {"key": "value"}
        assert event.correlation_id == "test-123"
        
        await bus.stop()


class TestGlobalEventBus:
    """Test global event bus functions."""
    
    @pytest.mark.asyncio
    async def test_global_event_bus_singleton(self):
        """Test that get_event_bus returns the same instance."""
        bus1 = get_event_bus()
        bus2 = get_event_bus()
        
        assert bus1 is bus2
    
    @pytest.mark.asyncio
    async def test_start_stop_global_event_bus(self):
        """Test starting and stopping the global event bus."""
        # Start global event bus
        await start_event_bus()
        
        bus = get_event_bus()
        assert bus._running is True
        
        # Stop global event bus
        await stop_event_bus()
        
        # Should create a new instance after stopping
        new_bus = get_event_bus()
        assert new_bus is not bus


@pytest.mark.asyncio
class TestEventBusIntegration:
    """Integration tests for event bus with other components."""
    
    async def test_plugin_lifecycle_events(self):
        """Test event bus integration with plugin lifecycle."""
        bus = EventBus()
        await bus.start()
        
        lifecycle_events = []
        
        def track_events(event):
            lifecycle_events.append((event.event_type, event.data))
        
        # Subscribe to all plugin events
        bus.subscribe(EventType.PLUGIN_LOADING, track_events)
        bus.subscribe(EventType.PLUGIN_LOADED, track_events)
        bus.subscribe(EventType.PLUGIN_FAILED, track_events)
        bus.subscribe(EventType.PLUGIN_UNLOADING, track_events)
        bus.subscribe(EventType.PLUGIN_UNLOADED, track_events)
        
        # Simulate plugin lifecycle
        await bus.publish_event(
            EventType.PLUGIN_LOADING,
            "plugin_manager",
            {"plugin_name": "test_plugin"}
        )
        
        await bus.publish_event(
            EventType.PLUGIN_LOADED,
            "plugin_manager",
            {"plugin_name": "test_plugin"}
        )
        
        await bus.publish_event(
            EventType.PLUGIN_UNLOADING,
            "plugin_manager",
            {"plugin_name": "test_plugin"}
        )
        
        await bus.publish_event(
            EventType.PLUGIN_UNLOADED,
            "plugin_manager",
            {"plugin_name": "test_plugin"}
        )
        
        await asyncio.sleep(0.1)
        
        # Verify all events were received
        assert len(lifecycle_events) == 4
        event_types = [event[0] for event in lifecycle_events]
        assert EventType.PLUGIN_LOADING in event_types
        assert EventType.PLUGIN_LOADED in event_types
        assert EventType.PLUGIN_UNLOADING in event_types
        assert EventType.PLUGIN_UNLOADED in event_types
        
        await bus.stop()
    
    async def test_command_lifecycle_events(self):
        """Test event bus integration with command lifecycle."""
        bus = EventBus()
        await bus.start()
        
        command_events = []
        
        def track_commands(event):
            command_events.append((event.event_type, event.data))
        
        # Subscribe to command events
        bus.subscribe(EventType.COMMAND_START, track_commands)
        bus.subscribe(EventType.COMMAND_END, track_commands)
        bus.subscribe(EventType.COMMAND_ERROR, track_commands)
        
        # Simulate command execution
        await bus.publish_event(
            EventType.COMMAND_START,
            "cli",
            {"command": "portfolio status"}
        )
        
        await bus.publish_event(
            EventType.COMMAND_END,
            "cli",
            {"command": "portfolio status", "result": "success"}
        )
        
        await asyncio.sleep(0.1)
        
        assert len(command_events) == 2
        assert command_events[0][0] == EventType.COMMAND_START
        assert command_events[1][0] == EventType.COMMAND_END
        
        await bus.stop()
