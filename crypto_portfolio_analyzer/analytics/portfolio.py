"""Portfolio performance analytics engine."""

import asyncio
import numpy as np
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import List, Dict, Optional, Tuple
import logging

from .models import (
    PortfolioHolding, PortfolioSnapshot, PerformanceMetrics, 
    PerformancePeriod, AnalyticsReport
)
from ..data.service import get_data_service

logger = logging.getLogger(__name__)


class PortfolioAnalyzer:
    """Portfolio performance analytics engine."""
    
    def __init__(self, data_service=None):
        """Initialize portfolio analyzer.
        
        Args:
            data_service: Data service for price fetching
        """
        self.data_service = data_service
        self._price_cache = {}
    
    async def create_portfolio_snapshot(self, holdings_data: List[Dict]) -> PortfolioSnapshot:
        """Create current portfolio snapshot with live prices.
        
        Args:
            holdings_data: List of holdings with symbol, quantity, average_cost
            
        Returns:
            PortfolioSnapshot with current market values
        """
        # Always get fresh data service to ensure proper initialization
        from ..data.service import get_data_service as get_service
        data_service = await get_service()

        # Get symbols for price fetching
        symbols = [holding['symbol'] for holding in holdings_data]

        # Fetch current prices
        current_prices = await data_service.get_multiple_prices(symbols, "usd")
        price_map = {price.symbol: price.current_price for price in current_prices}
        
        # Create holdings with current prices
        holdings = []
        total_value = Decimal("0")
        total_cost = Decimal("0")
        
        for holding_data in holdings_data:
            symbol = holding_data['symbol'].upper()
            quantity = Decimal(str(holding_data['quantity']))
            average_cost = Decimal(str(holding_data['average_cost']))
            current_price = price_map.get(symbol, Decimal("0"))
            
            holding = PortfolioHolding(
                symbol=symbol,
                quantity=quantity,
                average_cost=average_cost,
                current_price=current_price,
                purchase_date=holding_data.get('purchase_date')
            )
            
            holdings.append(holding)
            total_value += holding.market_value
            total_cost += holding.cost_basis
        
        return PortfolioSnapshot(
            timestamp=datetime.now(timezone.utc),
            holdings=holdings,
            total_value=total_value,
            total_cost=total_cost,
            cash_balance=Decimal(str(holdings_data[0].get('cash_balance', 0))) if holdings_data else Decimal("0")
        )
    
    async def calculate_performance_metrics(self, 
                                          current_snapshot: PortfolioSnapshot,
                                          historical_snapshots: List[PortfolioSnapshot],
                                          period: PerformancePeriod) -> PerformanceMetrics:
        """Calculate performance metrics for a specific period.
        
        Args:
            current_snapshot: Current portfolio snapshot
            historical_snapshots: Historical portfolio snapshots
            period: Performance period to analyze
            
        Returns:
            PerformanceMetrics for the specified period
        """
        # Determine date range based on period
        end_date = current_snapshot.timestamp
        
        if period == PerformancePeriod.DAY_1:
            start_date = end_date - timedelta(days=1)
        elif period == PerformancePeriod.DAYS_7:
            start_date = end_date - timedelta(days=7)
        elif period == PerformancePeriod.DAYS_30:
            start_date = end_date - timedelta(days=30)
        elif period == PerformancePeriod.DAYS_90:
            start_date = end_date - timedelta(days=90)
        elif period == PerformancePeriod.DAYS_365:
            start_date = end_date - timedelta(days=365)
        else:  # ALL_TIME
            start_date = min(snapshot.timestamp for snapshot in historical_snapshots) if historical_snapshots else end_date
        
        # Find closest historical snapshot to start date
        start_snapshot = self._find_closest_snapshot(historical_snapshots, start_date)
        if not start_snapshot:
            start_snapshot = current_snapshot
        
        # Calculate basic metrics
        start_value = start_snapshot.portfolio_value
        end_value = current_snapshot.portfolio_value
        total_return = end_value - start_value
        
        total_return_percentage = float((total_return / start_value) * 100) if start_value > 0 else 0.0
        
        # Calculate annualized return
        days_elapsed = max((end_date - start_date).days, 1)
        annualized_return = self._calculate_annualized_return(total_return_percentage, days_elapsed)
        
        # Calculate volatility from daily returns
        daily_returns = self._calculate_daily_returns(historical_snapshots, start_date, end_date)
        volatility = float(np.std(daily_returns) * np.sqrt(252)) if len(daily_returns) > 1 else 0.0
        
        # Calculate Sharpe ratio (assuming 2% risk-free rate)
        risk_free_rate = 0.02
        sharpe_ratio = (annualized_return - risk_free_rate) / volatility if volatility > 0 else None
        
        # Calculate maximum drawdown
        max_drawdown = self._calculate_max_drawdown(historical_snapshots, start_date, end_date)
        
        # Calculate win rate
        win_rate = self._calculate_win_rate(daily_returns)
        
        return PerformanceMetrics(
            period=period,
            start_date=start_date,
            end_date=end_date,
            start_value=start_value,
            end_value=end_value,
            total_return=total_return,
            total_return_percentage=total_return_percentage,
            annualized_return=annualized_return,
            volatility=volatility,
            sharpe_ratio=sharpe_ratio,
            max_drawdown=max_drawdown,
            win_rate=win_rate
        )
    
    def _find_closest_snapshot(self, snapshots: List[PortfolioSnapshot], 
                              target_date: datetime) -> Optional[PortfolioSnapshot]:
        """Find snapshot closest to target date."""
        if not snapshots:
            return None
        
        closest_snapshot = None
        min_diff = float('inf')
        
        for snapshot in snapshots:
            diff = abs((snapshot.timestamp - target_date).total_seconds())
            if diff < min_diff:
                min_diff = diff
                closest_snapshot = snapshot
        
        return closest_snapshot
    
    def _calculate_annualized_return(self, total_return_percentage: float, days: int) -> float:
        """Calculate annualized return from total return."""
        if days <= 0:
            return 0.0
        
        years = days / 365.25
        if years <= 0:
            return total_return_percentage
        
        # Convert percentage to decimal, annualize, convert back to percentage
        return ((1 + total_return_percentage / 100) ** (1 / years) - 1) * 100
    
    def _calculate_daily_returns(self, snapshots: List[PortfolioSnapshot], 
                                start_date: datetime, end_date: datetime) -> List[float]:
        """Calculate daily returns for the period."""
        # Filter snapshots within date range and sort by timestamp
        period_snapshots = [
            s for s in snapshots 
            if start_date <= s.timestamp <= end_date
        ]
        period_snapshots.sort(key=lambda x: x.timestamp)
        
        if len(period_snapshots) < 2:
            return []
        
        daily_returns = []
        for i in range(1, len(period_snapshots)):
            prev_value = float(period_snapshots[i-1].portfolio_value)
            curr_value = float(period_snapshots[i].portfolio_value)
            
            if prev_value > 0:
                daily_return = (curr_value - prev_value) / prev_value
                daily_returns.append(daily_return)
        
        return daily_returns
    
    def _calculate_max_drawdown(self, snapshots: List[PortfolioSnapshot],
                               start_date: datetime, end_date: datetime) -> Optional[float]:
        """Calculate maximum drawdown for the period."""
        # Filter and sort snapshots
        period_snapshots = [
            s for s in snapshots 
            if start_date <= s.timestamp <= end_date
        ]
        period_snapshots.sort(key=lambda x: x.timestamp)
        
        if len(period_snapshots) < 2:
            return None
        
        values = [float(s.portfolio_value) for s in period_snapshots]
        
        # Calculate running maximum and drawdowns
        running_max = values[0]
        max_drawdown = 0.0
        
        for value in values[1:]:
            running_max = max(running_max, value)
            drawdown = (running_max - value) / running_max if running_max > 0 else 0
            max_drawdown = max(max_drawdown, drawdown)
        
        return max_drawdown * 100  # Convert to percentage
    
    def _calculate_win_rate(self, daily_returns: List[float]) -> Optional[float]:
        """Calculate win rate (percentage of positive returns)."""
        if not daily_returns:
            return None
        
        positive_returns = sum(1 for r in daily_returns if r > 0)
        return (positive_returns / len(daily_returns)) * 100
    
    async def calculate_time_weighted_return(self, snapshots: List[PortfolioSnapshot],
                                           cash_flows: List[Dict]) -> float:
        """Calculate time-weighted return accounting for cash flows.
        
        Args:
            snapshots: Portfolio snapshots over time
            cash_flows: List of cash flows with 'date', 'amount', 'type'
            
        Returns:
            Time-weighted return as percentage
        """
        if len(snapshots) < 2:
            return 0.0
        
        # Sort snapshots and cash flows by date
        snapshots.sort(key=lambda x: x.timestamp)
        cash_flows.sort(key=lambda x: x['date'])
        
        # Calculate sub-period returns between cash flows
        sub_returns = []
        start_idx = 0
        
        for cash_flow in cash_flows:
            # Find snapshots before this cash flow
            end_idx = start_idx
            while (end_idx < len(snapshots) and 
                   snapshots[end_idx].timestamp <= cash_flow['date']):
                end_idx += 1
            
            if end_idx > start_idx + 1:
                # Calculate return for this sub-period
                start_value = float(snapshots[start_idx].portfolio_value)
                end_value = float(snapshots[end_idx - 1].portfolio_value)
                
                if start_value > 0:
                    sub_return = (end_value - start_value) / start_value
                    sub_returns.append(sub_return)
            
            start_idx = end_idx
        
        # Handle final period after last cash flow
        if start_idx < len(snapshots) - 1:
            start_value = float(snapshots[start_idx].portfolio_value)
            end_value = float(snapshots[-1].portfolio_value)
            
            if start_value > 0:
                sub_return = (end_value - start_value) / start_value
                sub_returns.append(sub_return)
        
        # Calculate compound return
        if not sub_returns:
            return 0.0
        
        compound_return = 1.0
        for sub_return in sub_returns:
            compound_return *= (1 + sub_return)
        
        return (compound_return - 1) * 100  # Convert to percentage
