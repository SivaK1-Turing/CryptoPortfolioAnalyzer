"""Real-time portfolio monitoring and alerting."""

import asyncio
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional, Callable, Any
import logging

from .models import PortfolioAlert, PortfolioSnapshot, PortfolioHolding

logger = logging.getLogger(__name__)


class PortfolioMonitor:
    """Real-time portfolio monitoring and alerting system."""
    
    def __init__(self, data_service=None):
        """Initialize portfolio monitor.
        
        Args:
            data_service: Data service for price updates
        """
        self.data_service = data_service
        self.alert_handlers: List[Callable] = []
        self.monitoring_active = False
        self.alert_thresholds = {
            'price_drop_percentage': 5.0,
            'price_spike_percentage': 10.0,
            'portfolio_drop_percentage': 3.0,
            'volatility_threshold': 0.1,
            'volume_spike_multiplier': 3.0
        }
        self.last_snapshot: Optional[PortfolioSnapshot] = None
        self.price_history: Dict[str, List[float]] = {}
        self.alerts_history: List[PortfolioAlert] = []
    
    def add_alert_handler(self, handler: Callable[[PortfolioAlert], None]):
        """Add alert handler function.
        
        Args:
            handler: Function to handle alerts
        """
        self.alert_handlers.append(handler)
    
    def set_alert_threshold(self, alert_type: str, threshold: float):
        """Set alert threshold.
        
        Args:
            alert_type: Type of alert threshold
            threshold: Threshold value
        """
        self.alert_thresholds[alert_type] = threshold
    
    async def start_monitoring(self, portfolio_holdings: List[Dict], 
                             check_interval: int = 60):
        """Start real-time portfolio monitoring.
        
        Args:
            portfolio_holdings: Portfolio holdings to monitor
            check_interval: Check interval in seconds
        """
        self.monitoring_active = True
        logger.info("Started portfolio monitoring")
        
        try:
            while self.monitoring_active:
                await self._check_portfolio(portfolio_holdings)
                await asyncio.sleep(check_interval)
        except Exception as e:
            logger.error(f"Error in portfolio monitoring: {e}")
        finally:
            logger.info("Stopped portfolio monitoring")
    
    def stop_monitoring(self):
        """Stop portfolio monitoring."""
        self.monitoring_active = False
    
    async def _check_portfolio(self, portfolio_holdings: List[Dict]):
        """Check portfolio for alert conditions."""
        try:
            if not self.data_service:
                from ..data.service import get_data_service
                self.data_service = await get_data_service()
            
            # Create current snapshot
            from .portfolio import PortfolioAnalyzer
            analyzer = PortfolioAnalyzer(self.data_service)
            current_snapshot = await analyzer.create_portfolio_snapshot(portfolio_holdings)
            
            # Check for alerts
            alerts = await self._detect_alerts(current_snapshot)
            
            # Process alerts
            for alert in alerts:
                await self._handle_alert(alert)
            
            # Update state
            self.last_snapshot = current_snapshot
            
        except Exception as e:
            logger.error(f"Error checking portfolio: {e}")
    
    async def _detect_alerts(self, current_snapshot: PortfolioSnapshot) -> List[PortfolioAlert]:
        """Detect alert conditions in current snapshot."""
        alerts = []
        
        # Check individual asset alerts
        for holding in current_snapshot.holdings:
            alerts.extend(await self._check_asset_alerts(holding))
        
        # Check portfolio-level alerts
        if self.last_snapshot:
            alerts.extend(await self._check_portfolio_alerts(current_snapshot, self.last_snapshot))
        
        return alerts
    
    async def _check_asset_alerts(self, holding: PortfolioHolding) -> List[PortfolioAlert]:
        """Check for asset-specific alerts."""
        alerts = []
        symbol = holding.symbol
        current_price = float(holding.current_price)
        
        # Update price history
        if symbol not in self.price_history:
            self.price_history[symbol] = []
        
        self.price_history[symbol].append(current_price)
        
        # Keep only recent prices (last 24 hours worth)
        if len(self.price_history[symbol]) > 1440:  # Assuming 1-minute intervals
            self.price_history[symbol] = self.price_history[symbol][-1440:]
        
        # Check price drop alert
        if len(self.price_history[symbol]) >= 2:
            previous_price = self.price_history[symbol][-2]
            price_change_pct = ((current_price - previous_price) / previous_price) * 100
            
            if price_change_pct <= -self.alert_thresholds['price_drop_percentage']:
                alert = PortfolioAlert(
                    alert_type="price_drop",
                    severity="high" if price_change_pct <= -10 else "medium",
                    message=f"{symbol} dropped {abs(price_change_pct):.2f}% to ${current_price:,.2f}",
                    timestamp=datetime.now(timezone.utc),
                    symbol=symbol,
                    current_value=current_price,
                    threshold_value=previous_price * (1 - self.alert_thresholds['price_drop_percentage'] / 100),
                    metadata={
                        'price_change_percentage': price_change_pct,
                        'previous_price': previous_price
                    }
                )
                alerts.append(alert)
            
            elif price_change_pct >= self.alert_thresholds['price_spike_percentage']:
                alert = PortfolioAlert(
                    alert_type="price_spike",
                    severity="medium",
                    message=f"{symbol} spiked {price_change_pct:.2f}% to ${current_price:,.2f}",
                    timestamp=datetime.now(timezone.utc),
                    symbol=symbol,
                    current_value=current_price,
                    threshold_value=previous_price * (1 + self.alert_thresholds['price_spike_percentage'] / 100),
                    metadata={
                        'price_change_percentage': price_change_pct,
                        'previous_price': previous_price
                    }
                )
                alerts.append(alert)
        
        # Check volatility alert
        if len(self.price_history[symbol]) >= 10:
            recent_prices = self.price_history[symbol][-10:]
            volatility = self._calculate_volatility(recent_prices)
            
            if volatility > self.alert_thresholds['volatility_threshold']:
                alert = PortfolioAlert(
                    alert_type="high_volatility",
                    severity="medium",
                    message=f"{symbol} showing high volatility: {volatility:.4f}",
                    timestamp=datetime.now(timezone.utc),
                    symbol=symbol,
                    current_value=volatility,
                    threshold_value=self.alert_thresholds['volatility_threshold'],
                    metadata={
                        'volatility_period': '10_periods',
                        'current_price': current_price
                    }
                )
                alerts.append(alert)
        
        # Check position size alert (if position becomes too large)
        unrealized_pnl_pct = holding.unrealized_pnl_percentage
        if unrealized_pnl_pct <= -20:  # 20% loss threshold
            alert = PortfolioAlert(
                alert_type="large_loss",
                severity="high",
                message=f"{symbol} position down {abs(unrealized_pnl_pct):.2f}%",
                timestamp=datetime.now(timezone.utc),
                symbol=symbol,
                current_value=unrealized_pnl_pct,
                threshold_value=-20.0,
                metadata={
                    'unrealized_pnl': float(holding.unrealized_pnl),
                    'cost_basis': float(holding.cost_basis)
                }
            )
            alerts.append(alert)
        
        return alerts
    
    async def _check_portfolio_alerts(self, current_snapshot: PortfolioSnapshot,
                                    previous_snapshot: PortfolioSnapshot) -> List[PortfolioAlert]:
        """Check for portfolio-level alerts."""
        alerts = []
        
        # Check portfolio value drop
        current_value = float(current_snapshot.portfolio_value)
        previous_value = float(previous_snapshot.portfolio_value)
        
        if previous_value > 0:
            portfolio_change_pct = ((current_value - previous_value) / previous_value) * 100
            
            if portfolio_change_pct <= -self.alert_thresholds['portfolio_drop_percentage']:
                alert = PortfolioAlert(
                    alert_type="portfolio_drop",
                    severity="high" if portfolio_change_pct <= -10 else "medium",
                    message=f"Portfolio value dropped {abs(portfolio_change_pct):.2f}% to ${current_value:,.2f}",
                    timestamp=datetime.now(timezone.utc),
                    current_value=current_value,
                    threshold_value=previous_value * (1 - self.alert_thresholds['portfolio_drop_percentage'] / 100),
                    metadata={
                        'portfolio_change_percentage': portfolio_change_pct,
                        'previous_value': previous_value,
                        'value_change': current_value - previous_value
                    }
                )
                alerts.append(alert)
        
        # Check for new holdings or removed holdings
        current_symbols = {holding.symbol for holding in current_snapshot.holdings}
        previous_symbols = {holding.symbol for holding in previous_snapshot.holdings}
        
        new_symbols = current_symbols - previous_symbols
        removed_symbols = previous_symbols - current_symbols
        
        for symbol in new_symbols:
            alert = PortfolioAlert(
                alert_type="new_holding",
                severity="low",
                message=f"New holding added: {symbol}",
                timestamp=datetime.now(timezone.utc),
                symbol=symbol,
                metadata={'action': 'added'}
            )
            alerts.append(alert)
        
        for symbol in removed_symbols:
            alert = PortfolioAlert(
                alert_type="holding_removed",
                severity="low",
                message=f"Holding removed: {symbol}",
                timestamp=datetime.now(timezone.utc),
                symbol=symbol,
                metadata={'action': 'removed'}
            )
            alerts.append(alert)
        
        return alerts
    
    def _calculate_volatility(self, prices: List[float]) -> float:
        """Calculate volatility from price series."""
        if len(prices) < 2:
            return 0.0
        
        # Calculate returns
        returns = []
        for i in range(1, len(prices)):
            if prices[i-1] > 0:
                ret = (prices[i] - prices[i-1]) / prices[i-1]
                returns.append(ret)
        
        if not returns:
            return 0.0
        
        # Calculate standard deviation
        mean_return = sum(returns) / len(returns)
        variance = sum((r - mean_return) ** 2 for r in returns) / len(returns)
        volatility = variance ** 0.5
        
        return volatility
    
    async def _handle_alert(self, alert: PortfolioAlert):
        """Handle generated alert."""
        # Add to history
        self.alerts_history.append(alert)
        
        # Keep only recent alerts (last 24 hours)
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=24)
        self.alerts_history = [
            a for a in self.alerts_history 
            if a.timestamp >= cutoff_time
        ]
        
        # Log alert
        logger.warning(f"Portfolio Alert [{alert.severity.upper()}]: {alert.message}")
        
        # Call alert handlers
        for handler in self.alert_handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(alert)
                else:
                    handler(alert)
            except Exception as e:
                logger.error(f"Error in alert handler: {e}")
    
    def get_recent_alerts(self, hours: int = 24) -> List[PortfolioAlert]:
        """Get recent alerts within specified hours.
        
        Args:
            hours: Number of hours to look back
            
        Returns:
            List of recent alerts
        """
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)
        return [
            alert for alert in self.alerts_history
            if alert.timestamp >= cutoff_time
        ]
    
    def get_alert_summary(self) -> Dict[str, Any]:
        """Get summary of recent alerts.
        
        Returns:
            Alert summary dictionary
        """
        recent_alerts = self.get_recent_alerts(24)
        
        summary = {
            'total_alerts': len(recent_alerts),
            'by_severity': {},
            'by_type': {},
            'by_symbol': {},
            'latest_alert': None
        }
        
        for alert in recent_alerts:
            # Count by severity
            severity = alert.severity
            summary['by_severity'][severity] = summary['by_severity'].get(severity, 0) + 1
            
            # Count by type
            alert_type = alert.alert_type
            summary['by_type'][alert_type] = summary['by_type'].get(alert_type, 0) + 1
            
            # Count by symbol
            if alert.symbol:
                symbol = alert.symbol
                summary['by_symbol'][symbol] = summary['by_symbol'].get(symbol, 0) + 1
        
        # Get latest alert
        if recent_alerts:
            latest = max(recent_alerts, key=lambda x: x.timestamp)
            summary['latest_alert'] = {
                'type': latest.alert_type,
                'severity': latest.severity,
                'message': latest.message,
                'timestamp': latest.timestamp.isoformat(),
                'symbol': latest.symbol
            }
        
        return summary
