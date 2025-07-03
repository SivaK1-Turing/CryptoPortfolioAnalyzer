"""Asset allocation analysis and optimization."""

import numpy as np
from typing import List, Dict, Tuple, Optional
from decimal import Decimal
import logging

from .models import AllocationMetrics, PortfolioHolding, PortfolioSnapshot

logger = logging.getLogger(__name__)


class AllocationAnalyzer:
    """Asset allocation analysis and optimization engine."""
    
    def __init__(self):
        """Initialize allocation analyzer."""
        pass
    
    def analyze_allocation(self, portfolio_snapshot: PortfolioSnapshot,
                          target_allocations: Optional[Dict[str, float]] = None) -> AllocationMetrics:
        """Analyze current asset allocation and provide metrics.
        
        Args:
            portfolio_snapshot: Current portfolio snapshot
            target_allocations: Optional target allocation percentages
            
        Returns:
            AllocationMetrics with comprehensive allocation analysis
        """
        if not portfolio_snapshot.holdings:
            return self._create_empty_allocation_metrics()
        
        # Calculate current allocations
        total_value = portfolio_snapshot.total_value
        allocations = {}
        
        for holding in portfolio_snapshot.holdings:
            if total_value > 0:
                allocation_pct = float((holding.market_value / total_value) * 100)
                allocations[holding.symbol] = allocation_pct
            else:
                allocations[holding.symbol] = 0.0
        
        # Calculate concentration metrics
        concentration_risk = self._calculate_concentration_risk(allocations)
        diversification_ratio = self._calculate_diversification_ratio(allocations)
        herfindahl_index = self._calculate_herfindahl_index(allocations)
        effective_assets = self._calculate_effective_assets(allocations)
        
        # Calculate position metrics
        largest_position = max(allocations.values()) if allocations else 0.0
        top_5_concentration = self._calculate_top_n_concentration(allocations, 5)
        
        # Generate rebalancing suggestions
        rebalancing_suggestions = []
        if target_allocations:
            rebalancing_suggestions = self._generate_rebalancing_suggestions(
                allocations, target_allocations, float(total_value)
            )
        
        return AllocationMetrics(
            allocations=allocations,
            concentration_risk=concentration_risk,
            diversification_ratio=diversification_ratio,
            herfindahl_index=herfindahl_index,
            effective_assets=effective_assets,
            largest_position=largest_position,
            top_5_concentration=top_5_concentration,
            rebalancing_suggestions=rebalancing_suggestions
        )
    
    def calculate_optimal_allocation(self, 
                                   expected_returns: Dict[str, float],
                                   covariance_matrix: np.ndarray,
                                   symbols: List[str],
                                   risk_tolerance: float = 0.5) -> Dict[str, float]:
        """Calculate optimal allocation using modern portfolio theory.
        
        Args:
            expected_returns: Expected returns for each asset
            covariance_matrix: Asset covariance matrix
            symbols: List of asset symbols
            risk_tolerance: Risk tolerance (0 = risk averse, 1 = risk seeking)
            
        Returns:
            Optimal allocation percentages
        """
        if len(symbols) != len(expected_returns) or covariance_matrix.shape[0] != len(symbols):
            logger.warning("Mismatched dimensions for optimization")
            return {symbol: 100.0 / len(symbols) for symbol in symbols}
        
        try:
            # Convert expected returns to array
            returns_array = np.array([expected_returns.get(symbol, 0.0) for symbol in symbols])
            
            # Calculate inverse covariance matrix
            inv_cov = np.linalg.inv(covariance_matrix)
            
            # Calculate optimal weights using mean-variance optimization
            ones = np.ones((len(symbols), 1))
            
            # Risk-adjusted optimization
            risk_aversion = 2 * (1 - risk_tolerance) + 0.1  # Scale risk aversion
            
            # Optimal weights: w = (1/λ) * Σ^(-1) * μ
            optimal_weights = (1 / risk_aversion) * np.dot(inv_cov, returns_array)
            
            # Normalize to sum to 1
            weight_sum = np.sum(optimal_weights)
            if weight_sum > 0:
                optimal_weights = optimal_weights / weight_sum
            else:
                optimal_weights = np.ones(len(symbols)) / len(symbols)
            
            # Convert to percentages and create dictionary
            allocation = {}
            for i, symbol in enumerate(symbols):
                allocation[symbol] = max(0.0, float(optimal_weights[i] * 100))
            
            # Ensure allocations sum to 100%
            total_allocation = sum(allocation.values())
            if total_allocation > 0:
                for symbol in allocation:
                    allocation[symbol] = (allocation[symbol] / total_allocation) * 100
            
            return allocation
            
        except Exception as e:
            logger.error(f"Failed to calculate optimal allocation: {e}")
            # Return equal weights as fallback
            return {symbol: 100.0 / len(symbols) for symbol in symbols}
    
    def calculate_rebalancing_trades(self, 
                                   current_holdings: List[PortfolioHolding],
                                   target_allocations: Dict[str, float],
                                   available_cash: Decimal = Decimal("0")) -> List[Dict]:
        """Calculate trades needed to rebalance portfolio.
        
        Args:
            current_holdings: Current portfolio holdings
            target_allocations: Target allocation percentages
            available_cash: Available cash for rebalancing
            
        Returns:
            List of trade recommendations
        """
        if not current_holdings:
            return []
        
        # Calculate current total value
        total_value = sum(holding.market_value for holding in current_holdings) + available_cash
        
        # Calculate current allocations
        current_allocations = {}
        for holding in current_holdings:
            if total_value > 0:
                current_allocations[holding.symbol] = float((holding.market_value / total_value) * 100)
            else:
                current_allocations[holding.symbol] = 0.0
        
        # Calculate target values
        trades = []
        for symbol, target_pct in target_allocations.items():
            target_value = float(total_value) * (target_pct / 100)
            
            # Find current holding
            current_holding = next((h for h in current_holdings if h.symbol == symbol), None)
            current_value = float(current_holding.market_value) if current_holding else 0.0
            
            # Calculate trade amount
            trade_amount = target_value - current_value
            
            if abs(trade_amount) > float(total_value) * 0.01:  # Only suggest trades > 1% of portfolio
                trade_type = "BUY" if trade_amount > 0 else "SELL"
                
                if current_holding:
                    if trade_amount > 0:
                        # Calculate quantity to buy
                        quantity_to_trade = Decimal(str(abs(trade_amount))) / current_holding.current_price
                    else:
                        # Calculate quantity to sell
                        quantity_to_trade = min(
                            Decimal(str(abs(trade_amount))) / current_holding.current_price,
                            current_holding.quantity
                        )
                else:
                    # New position - need current price
                    quantity_to_trade = Decimal("0")  # Would need current price to calculate
                
                trades.append({
                    'symbol': symbol,
                    'action': trade_type,
                    'amount_usd': abs(trade_amount),
                    'quantity': float(quantity_to_trade),
                    'current_allocation': current_allocations.get(symbol, 0.0),
                    'target_allocation': target_pct,
                    'deviation': target_pct - current_allocations.get(symbol, 0.0)
                })
        
        # Sort by largest deviation first
        trades.sort(key=lambda x: abs(x['deviation']), reverse=True)
        
        return trades
    
    def _calculate_concentration_risk(self, allocations: Dict[str, float]) -> float:
        """Calculate concentration risk score (0-100, higher = more concentrated)."""
        if not allocations:
            return 0.0
        
        # Use Herfindahl index as basis for concentration risk
        hhi = sum(pct ** 2 for pct in allocations.values())
        
        # Normalize to 0-100 scale
        # HHI ranges from 1/n (perfectly diversified) to 100 (fully concentrated)
        n = len(allocations)
        min_hhi = 100 / n  # Perfectly diversified
        max_hhi = 100 ** 2  # Fully concentrated
        
        if max_hhi > min_hhi:
            concentration_risk = ((hhi - min_hhi) / (max_hhi - min_hhi)) * 100
        else:
            concentration_risk = 0.0
        
        return min(100.0, max(0.0, concentration_risk))
    
    def _calculate_diversification_ratio(self, allocations: Dict[str, float]) -> float:
        """Calculate diversification ratio (higher = better diversified)."""
        if not allocations:
            return 0.0
        
        n = len(allocations)
        if n <= 1:
            return 0.0
        
        # Calculate effective number of assets
        sum_squared_weights = sum((pct / 100) ** 2 for pct in allocations.values())
        effective_assets = 1 / sum_squared_weights if sum_squared_weights > 0 else 1
        
        # Diversification ratio = effective assets / total assets
        diversification_ratio = effective_assets / n
        
        return min(1.0, max(0.0, diversification_ratio))
    
    def _calculate_herfindahl_index(self, allocations: Dict[str, float]) -> float:
        """Calculate Herfindahl-Hirschman Index for concentration."""
        if not allocations:
            return 0.0
        
        # HHI = sum of squared market shares (percentages)
        hhi = sum(pct ** 2 for pct in allocations.values())
        
        return hhi
    
    def _calculate_effective_assets(self, allocations: Dict[str, float]) -> float:
        """Calculate effective number of assets."""
        if not allocations:
            return 0.0
        
        sum_squared_weights = sum((pct / 100) ** 2 for pct in allocations.values())
        effective_assets = 1 / sum_squared_weights if sum_squared_weights > 0 else 0
        
        return effective_assets
    
    def _calculate_top_n_concentration(self, allocations: Dict[str, float], n: int) -> float:
        """Calculate concentration of top N positions."""
        if not allocations:
            return 0.0
        
        sorted_allocations = sorted(allocations.values(), reverse=True)
        top_n_allocations = sorted_allocations[:min(n, len(sorted_allocations))]
        
        return sum(top_n_allocations)
    
    def _generate_rebalancing_suggestions(self, 
                                        current_allocations: Dict[str, float],
                                        target_allocations: Dict[str, float],
                                        total_value: float) -> List[Dict]:
        """Generate rebalancing suggestions."""
        suggestions = []
        
        for symbol, target_pct in target_allocations.items():
            current_pct = current_allocations.get(symbol, 0.0)
            deviation = target_pct - current_pct
            
            if abs(deviation) > 1.0:  # Only suggest if deviation > 1%
                action = "INCREASE" if deviation > 0 else "DECREASE"
                amount = abs(deviation) * total_value / 100
                
                suggestions.append({
                    'symbol': symbol,
                    'action': action,
                    'current_allocation': current_pct,
                    'target_allocation': target_pct,
                    'deviation': deviation,
                    'suggested_amount': amount,
                    'priority': 'HIGH' if abs(deviation) > 5 else 'MEDIUM' if abs(deviation) > 2 else 'LOW'
                })
        
        # Sort by absolute deviation (highest priority first)
        suggestions.sort(key=lambda x: abs(x['deviation']), reverse=True)
        
        return suggestions
    
    def _create_empty_allocation_metrics(self) -> AllocationMetrics:
        """Create empty allocation metrics for empty portfolio."""
        return AllocationMetrics(
            allocations={},
            concentration_risk=0.0,
            diversification_ratio=0.0,
            herfindahl_index=0.0,
            effective_assets=0.0,
            largest_position=0.0,
            top_5_concentration=0.0,
            rebalancing_suggestions=[]
        )
