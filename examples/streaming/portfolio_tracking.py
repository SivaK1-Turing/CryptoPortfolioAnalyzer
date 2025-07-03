#!/usr/bin/env python3
"""
Real-Time Portfolio Tracking Example

This example demonstrates how to track portfolio value changes in real-time
using the streaming system.
"""

import asyncio
import logging
from decimal import Decimal
from datetime import datetime, timezone
from typing import Dict, Any

from crypto_portfolio_analyzer.streaming import (
    PortfolioMonitor, PriceFeedProvider, StreamEventBus, EventType
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class PortfolioTracker:
    """Advanced portfolio tracking with alerts and analytics."""
    
    def __init__(self):
        self.portfolio_monitor = PortfolioMonitor()
        self.event_bus = StreamEventBus()
        self.initial_value = None
        self.value_history = []
        self.alerts = []
        self.thresholds = {
            'gain_percent': 5.0,    # Alert on 5% gain
            'loss_percent': -3.0,   # Alert on 3% loss
            'value_change': 1000.0  # Alert on $1000 change
        }
    
    async def setup(self, holdings: Dict[str, Decimal]):
        """Set up portfolio tracking with initial holdings."""
        logger.info("Setting up portfolio tracking...")
        
        # Add holdings to monitor
        for symbol, amount in holdings.items():
            self.portfolio_monitor.add_holding(symbol, amount)
            logger.info(f"Added holding: {amount} {symbol}")
        
        # Set up event bus
        await self.event_bus.start()
        
        # Subscribe to portfolio value changes
        self.event_bus.subscribe(
            "portfolio_tracker",
            self.handle_portfolio_update,
            event_types={EventType.PORTFOLIO_UPDATE}
        )
        
        # Add value change handler to portfolio monitor
        self.portfolio_monitor.add_value_change_handler(self.handle_value_change)
        
        logger.info("Portfolio tracking setup complete")
    
    async def start(self, provider: PriceFeedProvider = PriceFeedProvider.MOCK):
        """Start portfolio monitoring."""
        logger.info("Starting portfolio monitoring...")
        
        # Start portfolio monitoring
        await self.portfolio_monitor.start_monitoring(provider)
        
        # Record initial value
        await asyncio.sleep(1)  # Wait for first price updates
        self.initial_value = self.portfolio_monitor.get_current_value()
        
        if self.initial_value:
            logger.info(f"Initial portfolio value: ${self.initial_value:.2f}")
        
        logger.info("Portfolio monitoring started")
    
    async def stop(self):
        """Stop portfolio monitoring."""
        logger.info("Stopping portfolio monitoring...")
        await self.portfolio_monitor.stop_monitoring()
        await self.event_bus.stop()
        logger.info("Portfolio monitoring stopped")
    
    def handle_value_change(self, data: Dict[str, Any]):
        """Handle portfolio value changes."""
        current_value = Decimal(str(data.get('total_value', 0)))
        timestamp = datetime.now(timezone.utc)
        
        # Add to history
        self.value_history.append({
            'timestamp': timestamp,
            'value': current_value,
            'holdings': data.get('holdings', {})
        })
        
        # Keep only last 1000 entries
        if len(self.value_history) > 1000:
            self.value_history = self.value_history[-1000:]
        
        # Check for alerts
        self.check_alerts(current_value, timestamp)
        
        # Log the change
        if self.initial_value:
            change = current_value - self.initial_value
            change_percent = (change / self.initial_value) * 100
            
            change_str = f"${change:+.2f} ({change_percent:+.2f}%)"
            logger.info(f"Portfolio value: ${current_value:.2f} [{change_str}]")
    
    async def handle_portfolio_update(self, event):
        """Handle portfolio update events."""
        # This could be used for additional processing or notifications
        pass
    
    def check_alerts(self, current_value: Decimal, timestamp: datetime):
        """Check if any alert thresholds are met."""
        if not self.initial_value:
            return
        
        change = current_value - self.initial_value
        change_percent = float((change / self.initial_value) * 100)
        
        alerts_triggered = []
        
        # Check percentage thresholds
        if change_percent >= self.thresholds['gain_percent']:
            alerts_triggered.append({
                'type': 'gain_threshold',
                'message': f"Portfolio gained {change_percent:.2f}% (${change:.2f})",
                'severity': 'info'
            })
        elif change_percent <= self.thresholds['loss_percent']:
            alerts_triggered.append({
                'type': 'loss_threshold',
                'message': f"Portfolio lost {abs(change_percent):.2f}% (${change:.2f})",
                'severity': 'warning'
            })
        
        # Check absolute value threshold
        if abs(change) >= self.thresholds['value_change']:
            direction = "gained" if change > 0 else "lost"
            alerts_triggered.append({
                'type': 'value_threshold',
                'message': f"Portfolio {direction} ${abs(change):.2f}",
                'severity': 'info' if change > 0 else 'warning'
            })
        
        # Process alerts
        for alert in alerts_triggered:
            # Avoid duplicate alerts
            alert_key = f"{alert['type']}_{timestamp.strftime('%Y%m%d_%H')}"
            if alert_key not in [a.get('key') for a in self.alerts]:
                alert['key'] = alert_key
                alert['timestamp'] = timestamp
                self.alerts.append(alert)
                
                # Log alert
                emoji = "🎉" if alert['severity'] == 'info' else "⚠️"
                print(f"{emoji} ALERT: {alert['message']}")
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get portfolio performance summary."""
        if not self.initial_value or not self.value_history:
            return {}
        
        current_value = self.value_history[-1]['value']
        change = current_value - self.initial_value
        change_percent = (change / self.initial_value) * 100
        
        # Calculate min/max values
        values = [entry['value'] for entry in self.value_history]
        min_value = min(values)
        max_value = max(values)
        
        return {
            'initial_value': float(self.initial_value),
            'current_value': float(current_value),
            'total_change': float(change),
            'total_change_percent': float(change_percent),
            'min_value': float(min_value),
            'max_value': float(max_value),
            'updates_count': len(self.value_history),
            'alerts_count': len(self.alerts)
        }
    
    def print_summary(self):
        """Print portfolio performance summary."""
        summary = self.get_performance_summary()
        
        if not summary:
            print("No portfolio data available")
            return
        
        print("\n" + "="*60)
        print("PORTFOLIO PERFORMANCE SUMMARY")
        print("="*60)
        
        print(f"Initial Value:     ${summary['initial_value']:>12,.2f}")
        print(f"Current Value:     ${summary['current_value']:>12,.2f}")
        print(f"Total Change:      ${summary['total_change']:>12,.2f}")
        print(f"Change Percent:    {summary['total_change_percent']:>12.2f}%")
        print(f"Minimum Value:     ${summary['min_value']:>12,.2f}")
        print(f"Maximum Value:     ${summary['max_value']:>12,.2f}")
        print(f"Updates Received:  {summary['updates_count']:>12}")
        print(f"Alerts Triggered:  {summary['alerts_count']:>12}")
        
        print("="*60)
        
        # Show recent alerts
        if self.alerts:
            print("\nRECENT ALERTS:")
            for alert in self.alerts[-5:]:  # Last 5 alerts
                timestamp = alert['timestamp'].strftime('%H:%M:%S')
                print(f"  {timestamp}: {alert['message']}")
    
    def get_holdings_breakdown(self) -> Dict[str, Any]:
        """Get current holdings breakdown."""
        return self.portfolio_monitor.get_holdings_summary()


async def main():
    """Main function demonstrating portfolio tracking."""
    # Define portfolio holdings
    holdings = {
        "BTC": Decimal("1.5"),      # 1.5 Bitcoin
        "ETH": Decimal("10.0"),     # 10 Ethereum
        "ADA": Decimal("1000.0")    # 1000 Cardano
    }
    
    # Create portfolio tracker
    tracker = PortfolioTracker()
    
    try:
        # Set up tracking
        await tracker.setup(holdings)
        
        # Start monitoring with mock provider
        await tracker.start(PriceFeedProvider.MOCK)
        
        print("\n🚀 Portfolio tracking started!")
        print("Monitoring portfolio value changes... (Press Ctrl+C to stop)")
        print("-" * 60)
        
        # Monitor for 60 seconds
        await asyncio.sleep(60)
        
    except KeyboardInterrupt:
        print("\n\n👋 Stopping portfolio tracking...")
    except Exception as e:
        logger.error(f"Error during tracking: {e}")
    finally:
        # Clean up and show summary
        await tracker.stop()
        
        # Print final summary
        tracker.print_summary()
        
        # Show holdings breakdown
        print("\nHOLDINGS BREAKDOWN:")
        holdings_summary = tracker.get_holdings_breakdown()
        for symbol, data in holdings_summary.items():
            amount = data.get('amount', 0)
            value = data.get('current_value', 0)
            change = data.get('change_24h', 0)
            print(f"  {symbol}: {amount} units = ${value:.2f} ({change:+.2f}%)")


if __name__ == "__main__":
    # Run the example
    asyncio.run(main())
