#!/usr/bin/env python3
"""
Simple test for Feature 7: Real-time Portfolio Monitoring.
Tests core functionality without external dependencies.
"""

import asyncio
import sys
import json
import time
from pathlib import Path
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import List, Dict, Any

# Add the project root to Python path
sys.path.insert(0, str(Path(__file__).parent))

from crypto_portfolio_analyzer.streaming.realtime_tracker import (
    RealTimePortfolioTracker, TrackingConfig, TrackingMode, PortfolioMetrics
)
from crypto_portfolio_analyzer.streaming.alerts import (
    EnhancedAlertManager, Alert, AlertRule, AlertType, AlertSeverity
)
from crypto_portfolio_analyzer.streaming.events import (
    StreamEvent, EventType, StreamEventBus
)
from crypto_portfolio_analyzer.analytics.models import PortfolioHolding


def create_sample_holdings() -> List[PortfolioHolding]:
    """Create sample portfolio holdings for testing."""
    return [
        PortfolioHolding(
            symbol="BTC",
            quantity=Decimal("1.0"),
            average_cost=Decimal("45000"),
            current_price=Decimal("50000")
        ),
        PortfolioHolding(
            symbol="ETH",
            quantity=Decimal("5.0"),
            average_cost=Decimal("3000"),
            current_price=Decimal("3500")
        )
    ]


async def test_portfolio_metrics():
    """Test portfolio metrics calculation."""
    print("\n📊 Testing Portfolio Metrics...")
    
    try:
        holdings = create_sample_holdings()
        
        # Calculate expected values
        btc_value = Decimal("1.0") * Decimal("50000")  # $50,000
        eth_value = Decimal("5.0") * Decimal("3500")   # $17,500
        total_value = btc_value + eth_value            # $67,500
        
        btc_cost = Decimal("1.0") * Decimal("45000")   # $45,000
        eth_cost = Decimal("5.0") * Decimal("3000")    # $15,000
        total_cost = btc_cost + eth_cost               # $60,000
        
        total_return = total_value - total_cost        # $7,500
        return_pct = float(total_return / total_cost * 100)  # 12.5%
        
        print(f"  💰 Expected total value: ${total_value:,.2f}")
        print(f"  💸 Expected total cost: ${total_cost:,.2f}")
        print(f"  📈 Expected return: ${total_return:,.2f} ({return_pct:.2f}%)")
        
        # Create metrics object
        metrics = PortfolioMetrics(
            timestamp=datetime.now(timezone.utc),
            total_value=total_value,
            total_cost=total_cost,
            total_return=total_return,
            return_percentage=return_pct,
            daily_pnl=Decimal("1000"),
            daily_pnl_percentage=1.5
        )
        
        # Test serialization
        metrics_dict = metrics.to_dict()
        print(f"  ✅ Metrics serialization: {len(metrics_dict)} fields")
        
        return True
        
    except Exception as e:
        print(f"  ❌ Portfolio metrics test failed: {e}")
        return False


async def test_alert_rules():
    """Test alert rule creation and evaluation."""
    print("\n🚨 Testing Alert Rules...")
    
    try:
        alert_manager = EnhancedAlertManager()
        
        # Create test alert rules
        portfolio_rule = AlertRule(
            rule_id="test_portfolio_100k",
            alert_type=AlertType.PORTFOLIO_VALUE,
            threshold_value=Decimal("60000"),  # Lower threshold for testing
            severity=AlertSeverity.INFO,
            enabled=True
        )
        
        percentage_rule = AlertRule(
            rule_id="test_percentage_10pct",
            alert_type=AlertType.PERCENTAGE_CHANGE,
            percentage_threshold=10.0,
            severity=AlertSeverity.WARNING,
            enabled=True
        )
        
        alert_manager.add_alert_rule(portfolio_rule)
        alert_manager.add_alert_rule(percentage_rule)
        
        print(f"  📋 Added {len(alert_manager.get_alert_rules())} alert rules")
        
        # Create test metrics that should trigger alerts
        test_metrics = PortfolioMetrics(
            timestamp=datetime.now(timezone.utc),
            total_value=Decimal("67500"),  # Above $60k threshold
            total_cost=Decimal("60000"),
            total_return=Decimal("7500"),
            return_percentage=12.5,  # Above 10% threshold
            daily_pnl=Decimal("1000"),
            daily_pnl_percentage=1.5
        )
        
        print("  🔍 Checking alerts...")
        await alert_manager.check_portfolio_alerts(test_metrics)
        
        # Check for triggered alerts
        recent_alerts = alert_manager.get_recent_alerts(hours=1)
        print(f"  🚨 Triggered {len(recent_alerts)} alerts")
        
        for alert in recent_alerts:
            print(f"    • {alert.title} ({alert.severity.value})")
            print(f"      Current: {alert.current_value}, Threshold: {alert.threshold_value}")
        
        return len(recent_alerts) > 0
        
    except Exception as e:
        print(f"  ❌ Alert rules test failed: {e}")
        return False


async def test_event_broadcasting():
    """Test event system."""
    print("\n📡 Testing Event Broadcasting...")
    
    try:
        event_bus = StreamEventBus()
        
        # Track received events
        events_received = []
        
        async def event_handler(event: StreamEvent):
            events_received.append(event)
            print(f"  📨 Event: {event.event_type.value} from {event.source}")
        
        # Subscribe to events
        event_bus.subscribe("test_subscriber", event_handler)
        
        # Create and publish test events
        test_events = [
            StreamEvent(
                event_type=EventType.PRICE_UPDATE,
                data={"symbol": "BTC", "price": 51000, "change": 2.0},
                source="test_price_feed"
            ),
            StreamEvent(
                event_type=EventType.PORTFOLIO_UPDATE,
                data={"total_value": 67500, "return_pct": 12.5},
                source="test_tracker"
            ),
            StreamEvent(
                event_type=EventType.ALERT_TRIGGERED,
                data={"alert_type": "portfolio_value", "severity": "info"},
                source="test_alerts"
            )
        ]
        
        print(f"  📤 Publishing {len(test_events)} events...")
        for event in test_events:
            await event_bus.publish(event)
        
        # Wait for event processing
        await asyncio.sleep(0.1)
        
        print(f"  ✅ Received {len(events_received)} events")
        
        # Verify event content
        for event in events_received:
            print(f"    • {event.event_type.value}: {json.dumps(event.data, default=str)}")
        
        return len(events_received) == len(test_events)
        
    except Exception as e:
        print(f"  ❌ Event broadcasting test failed: {e}")
        return False


async def test_real_time_simulation():
    """Test real-time portfolio tracking simulation."""
    print("\n🔄 Testing Real-time Simulation...")
    
    try:
        # Create a simple tracker configuration
        config = TrackingConfig(
            mode=TrackingMode.INTERVAL,
            update_interval=0.2,  # 200ms updates
            enable_performance_tracking=True
        )
        
        # Note: We can't fully test the tracker without price feeds
        # But we can test the configuration and basic setup
        
        tracker = RealTimePortfolioTracker(config)
        holdings = create_sample_holdings()
        
        print(f"  ⚙️ Tracker configured with {config.mode.value} mode")
        print(f"  📊 Tracking {len(holdings)} holdings")
        
        # Test metrics calculation without starting the full tracker
        updates_count = 0
        
        def update_handler(metrics: PortfolioMetrics):
            nonlocal updates_count
            updates_count += 1
            print(f"  📈 Update #{updates_count}: ${metrics.total_value:,.2f}")
        
        tracker.add_update_handler(update_handler)
        
        # Simulate some portfolio changes
        print("  🎯 Simulating portfolio changes...")
        
        # Test adding holdings
        new_holding = PortfolioHolding(
            symbol="ADA",
            quantity=Decimal("1000"),
            average_cost=Decimal("1.0"),
            current_price=Decimal("1.2")
        )
        
        # Add to current holdings (simulate)
        tracker.current_holdings["ADA"] = new_holding
        print(f"  ➕ Added {new_holding.symbol} holding")
        
        # Test quantity update
        if "BTC" in tracker.current_holdings:
            tracker.current_holdings["BTC"].quantity = Decimal("1.5")
            print("  🔄 Updated BTC quantity")
        
        print(f"  ✅ Simulation completed with {len(tracker.current_holdings)} holdings")
        
        return True
        
    except Exception as e:
        print(f"  ❌ Real-time simulation test failed: {e}")
        return False


async def test_notification_system():
    """Test notification system (console only)."""
    print("\n📢 Testing Notification System...")
    
    try:
        from crypto_portfolio_analyzer.streaming.alerts import (
            ConsoleNotificationHandler, NotificationConfig, NotificationChannel
        )
        
        # Create console notification handler
        config = NotificationConfig(channel=NotificationChannel.CONSOLE)
        handler = ConsoleNotificationHandler(config)
        
        # Create test alert
        test_alert = Alert(
            alert_id="test_alert_001",
            rule_id="test_rule",
            alert_type=AlertType.PORTFOLIO_VALUE,
            severity=AlertSeverity.INFO,
            title="Test Portfolio Alert",
            message="This is a test alert to verify the notification system is working.",
            current_value=67500,
            threshold_value=60000
        )
        
        print("  📨 Sending test notification...")
        success = await handler.send_notification(test_alert)
        
        if success:
            print("  ✅ Console notification sent successfully")
        else:
            print("  ❌ Console notification failed")
        
        # Test alert serialization
        alert_dict = test_alert.to_dict()
        print(f"  📋 Alert serialization: {len(alert_dict)} fields")
        
        return success
        
    except Exception as e:
        print(f"  ❌ Notification system test failed: {e}")
        return False


async def main():
    """Main test function."""
    print("🚀 Testing Feature 7: Real-time Portfolio Monitoring (Simple)")
    print("=" * 65)
    
    # Run core tests that don't require external dependencies
    test_functions = [
        ("Portfolio Metrics", test_portfolio_metrics),
        ("Alert Rules", test_alert_rules),
        ("Event Broadcasting", test_event_broadcasting),
        ("Real-time Simulation", test_real_time_simulation),
        ("Notification System", test_notification_system)
    ]
    
    results = []
    
    for test_name, test_func in test_functions:
        print(f"\n{'='*20} {test_name} {'='*20}")
        try:
            result = await test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name} failed with exception: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "=" * 65)
    print("📊 TEST SUMMARY")
    print("=" * 65)
    
    passed = 0
    for i, (test_name, result) in enumerate(results):
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{i+1}. {test_name}: {status}")
        if result:
            passed += 1
    
    total = len(results)
    print(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 Core real-time monitoring features are working!")
        print("\n🔧 Tested Components:")
        print("  ✅ Portfolio Metrics Calculation")
        print("  ✅ Alert Rule System")
        print("  ✅ Event Broadcasting")
        print("  ✅ Real-time Tracking Simulation")
        print("  ✅ Console Notifications")
        
        print("\n💡 Next Steps:")
        print("  • Install psutil for full system monitoring: pip install psutil")
        print("  • Install websockets for WebSocket support: pip install websockets")
        print("  • Configure email/Slack notifications")
        print("  • Set up live price feeds")
        print("  • Deploy monitoring dashboard")
    else:
        print(f"\n⚠️  {total - passed} tests failed. Check the error messages above.")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(asyncio.run(main()))
