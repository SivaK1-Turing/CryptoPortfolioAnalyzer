"""Risk assessment and analysis module."""

import numpy as np
import pandas as pd
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional, Tuple
from scipy import stats
import logging

from .models import RiskMetrics, PortfolioSnapshot, PortfolioHolding
from ..data.service import get_data_service

logger = logging.getLogger(__name__)


class RiskAnalyzer:
    """Risk assessment and volatility analysis engine."""
    
    def __init__(self, data_service=None):
        """Initialize risk analyzer.
        
        Args:
            data_service: Data service for historical price data
        """
        self.data_service = data_service
    
    async def calculate_risk_metrics(self, 
                                   portfolio_snapshots: List[PortfolioSnapshot],
                                   benchmark_returns: Optional[List[float]] = None) -> RiskMetrics:
        """Calculate comprehensive risk metrics for portfolio.
        
        Args:
            portfolio_snapshots: Historical portfolio snapshots
            benchmark_returns: Optional benchmark returns for beta calculation
            
        Returns:
            RiskMetrics with comprehensive risk assessment
        """
        if len(portfolio_snapshots) < 2:
            return self._create_default_risk_metrics()
        
        # Calculate daily returns
        daily_returns = self._calculate_portfolio_returns(portfolio_snapshots)
        
        if len(daily_returns) < 2:
            return self._create_default_risk_metrics()
        
        # Convert to numpy array for calculations
        returns_array = np.array(daily_returns)
        
        # Calculate volatility metrics
        volatility_daily = float(np.std(returns_array))
        volatility_annualized = volatility_daily * np.sqrt(252)
        
        # Calculate Value at Risk (VaR)
        var_95_daily = float(np.percentile(returns_array, 5))
        var_99_daily = float(np.percentile(returns_array, 1))
        var_95_monthly = var_95_daily * np.sqrt(21)  # Monthly VaR
        var_99_monthly = var_99_daily * np.sqrt(21)
        
        # Calculate Sharpe ratio (assuming 2% risk-free rate)
        risk_free_rate_daily = 0.02 / 252
        mean_return = float(np.mean(returns_array))
        sharpe_ratio = (mean_return - risk_free_rate_daily) / volatility_daily if volatility_daily > 0 else 0.0
        sharpe_ratio_annualized = sharpe_ratio * np.sqrt(252)
        
        # Calculate Sortino ratio (downside deviation)
        downside_returns = returns_array[returns_array < 0]
        downside_deviation = float(np.std(downside_returns)) if len(downside_returns) > 0 else 0.0
        sortino_ratio = (mean_return - risk_free_rate_daily) / downside_deviation if downside_deviation > 0 else 0.0
        sortino_ratio_annualized = sortino_ratio * np.sqrt(252)
        
        # Calculate maximum drawdown
        max_drawdown, max_drawdown_duration = self._calculate_max_drawdown_detailed(portfolio_snapshots)
        
        # Calculate beta and correlation with benchmark
        beta = None
        correlation_with_market = None
        if benchmark_returns and len(benchmark_returns) == len(daily_returns):
            beta, correlation_with_market = self._calculate_beta_and_correlation(
                daily_returns, benchmark_returns
            )
        
        return RiskMetrics(
            volatility_daily=volatility_daily,
            volatility_annualized=volatility_annualized,
            var_95_daily=var_95_daily,
            var_99_daily=var_99_daily,
            var_95_monthly=var_95_monthly,
            var_99_monthly=var_99_monthly,
            sharpe_ratio=sharpe_ratio_annualized,
            sortino_ratio=sortino_ratio_annualized,
            max_drawdown=max_drawdown,
            max_drawdown_duration=max_drawdown_duration,
            beta=beta,
            correlation_with_market=correlation_with_market
        )
    
    async def calculate_portfolio_volatility(self, 
                                           holdings: List[PortfolioHolding],
                                           correlation_matrix: Optional[np.ndarray] = None) -> float:
        """Calculate portfolio volatility using modern portfolio theory.
        
        Args:
            holdings: Portfolio holdings
            correlation_matrix: Asset correlation matrix (optional)
            
        Returns:
            Portfolio volatility (annualized)
        """
        if not holdings:
            return 0.0
        
        # Get individual asset volatilities
        symbols = [holding.symbol for holding in holdings]
        volatilities = await self._get_asset_volatilities(symbols)
        
        # Calculate weights
        total_value = sum(holding.market_value for holding in holdings)
        weights = np.array([
            float(holding.market_value / total_value) for holding in holdings
        ])
        
        # Get volatilities array
        vol_array = np.array([volatilities.get(holding.symbol, 0.0) for holding in holdings])
        
        if correlation_matrix is None:
            # Simple weighted average if no correlation matrix
            portfolio_vol = np.sum(weights * vol_array)
        else:
            # Use correlation matrix for more accurate calculation
            covariance_matrix = np.outer(vol_array, vol_array) * correlation_matrix
            portfolio_variance = np.dot(weights, np.dot(covariance_matrix, weights))
            portfolio_vol = np.sqrt(portfolio_variance)
        
        return float(portfolio_vol)
    
    async def calculate_correlation_matrix(self, symbols: List[str], 
                                         days: int = 90) -> np.ndarray:
        """Calculate correlation matrix for given symbols.
        
        Args:
            symbols: List of cryptocurrency symbols
            days: Number of days for correlation calculation
            
        Returns:
            Correlation matrix as numpy array
        """
        if not self.data_service:
            self.data_service = await get_data_service()
        
        # Get historical data for all symbols
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=days)
        
        returns_data = {}
        
        for symbol in symbols:
            try:
                if hasattr(self.data_service, 'get_historical_prices'):
                    historical_prices = await self.data_service.get_historical_prices(
                        symbol, start_date, end_date
                    )
                else:
                    # If data_service is the service manager, get the actual service
                    from ..data.service import get_data_service as get_service
                    actual_service = await get_service()
                    historical_prices = await actual_service.get_historical_prices(
                        symbol, start_date, end_date
                    )
                
                if len(historical_prices) > 1:
                    prices = [float(price.price) for price in historical_prices]
                    returns = np.diff(np.log(prices))  # Log returns
                    returns_data[symbol] = returns
                    
            except Exception as e:
                logger.warning(f"Failed to get historical data for {symbol}: {e}")
                returns_data[symbol] = np.array([])
        
        # Create correlation matrix
        if not returns_data:
            return np.eye(len(symbols))
        
        # Align returns data (use minimum length)
        min_length = min(len(returns) for returns in returns_data.values() if len(returns) > 0)
        if min_length == 0:
            return np.eye(len(symbols))
        
        aligned_returns = np.array([
            returns_data[symbol][:min_length] if len(returns_data[symbol]) >= min_length 
            else np.zeros(min_length)
            for symbol in symbols
        ])
        
        # Calculate correlation matrix
        correlation_matrix = np.corrcoef(aligned_returns)
        
        # Handle NaN values
        correlation_matrix = np.nan_to_num(correlation_matrix, nan=0.0)
        
        # Ensure diagonal is 1.0
        np.fill_diagonal(correlation_matrix, 1.0)
        
        return correlation_matrix
    
    def calculate_var_monte_carlo(self, 
                                 portfolio_value: float,
                                 daily_returns: List[float],
                                 confidence_level: float = 0.95,
                                 time_horizon: int = 1,
                                 num_simulations: int = 10000) -> float:
        """Calculate Value at Risk using Monte Carlo simulation.
        
        Args:
            portfolio_value: Current portfolio value
            daily_returns: Historical daily returns
            confidence_level: Confidence level (0.95 for 95% VaR)
            time_horizon: Time horizon in days
            num_simulations: Number of Monte Carlo simulations
            
        Returns:
            Value at Risk in absolute terms
        """
        if not daily_returns:
            return 0.0
        
        returns_array = np.array(daily_returns)
        mean_return = np.mean(returns_array)
        std_return = np.std(returns_array)
        
        # Generate random returns
        random_returns = np.random.normal(
            mean_return * time_horizon,
            std_return * np.sqrt(time_horizon),
            num_simulations
        )
        
        # Calculate portfolio values
        simulated_values = portfolio_value * (1 + random_returns)
        portfolio_changes = simulated_values - portfolio_value
        
        # Calculate VaR
        var_percentile = (1 - confidence_level) * 100
        var_value = np.percentile(portfolio_changes, var_percentile)
        
        return abs(float(var_value))
    
    def _calculate_portfolio_returns(self, snapshots: List[PortfolioSnapshot]) -> List[float]:
        """Calculate daily portfolio returns from snapshots."""
        if len(snapshots) < 2:
            return []
        
        # Sort snapshots by timestamp
        sorted_snapshots = sorted(snapshots, key=lambda x: x.timestamp)
        
        returns = []
        for i in range(1, len(sorted_snapshots)):
            prev_value = float(sorted_snapshots[i-1].portfolio_value)
            curr_value = float(sorted_snapshots[i].portfolio_value)
            
            if prev_value > 0:
                daily_return = (curr_value - prev_value) / prev_value
                returns.append(daily_return)
        
        return returns
    
    def _calculate_max_drawdown_detailed(self, 
                                       snapshots: List[PortfolioSnapshot]) -> Tuple[float, int]:
        """Calculate maximum drawdown and its duration."""
        if len(snapshots) < 2:
            return 0.0, 0
        
        sorted_snapshots = sorted(snapshots, key=lambda x: x.timestamp)
        values = [float(s.portfolio_value) for s in sorted_snapshots]
        
        running_max = values[0]
        max_drawdown = 0.0
        max_drawdown_duration = 0
        current_drawdown_duration = 0
        
        for value in values[1:]:
            if value >= running_max:
                running_max = value
                current_drawdown_duration = 0
            else:
                current_drawdown_duration += 1
                drawdown = (running_max - value) / running_max
                if drawdown > max_drawdown:
                    max_drawdown = drawdown
                    max_drawdown_duration = current_drawdown_duration
        
        return max_drawdown * 100, max_drawdown_duration
    
    def _calculate_beta_and_correlation(self, 
                                      portfolio_returns: List[float],
                                      benchmark_returns: List[float]) -> Tuple[float, float]:
        """Calculate beta and correlation with benchmark."""
        if len(portfolio_returns) != len(benchmark_returns) or len(portfolio_returns) < 2:
            return 0.0, 0.0
        
        portfolio_array = np.array(portfolio_returns)
        benchmark_array = np.array(benchmark_returns)
        
        # Calculate correlation
        correlation = float(np.corrcoef(portfolio_array, benchmark_array)[0, 1])
        
        # Calculate beta
        benchmark_variance = np.var(benchmark_array)
        if benchmark_variance > 0:
            covariance = np.cov(portfolio_array, benchmark_array)[0, 1]
            beta = covariance / benchmark_variance
        else:
            beta = 0.0
        
        return float(beta), correlation
    
    async def _get_asset_volatilities(self, symbols: List[str]) -> Dict[str, float]:
        """Get historical volatilities for assets."""
        if not self.data_service:
            self.data_service = await get_data_service()
        
        volatilities = {}
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=90)
        
        for symbol in symbols:
            try:
                if hasattr(self.data_service, 'get_historical_prices'):
                    historical_prices = await self.data_service.get_historical_prices(
                        symbol, start_date, end_date
                    )
                else:
                    # If data_service is the service manager, get the actual service
                    from ..data.service import get_data_service as get_service
                    actual_service = await get_service()
                    historical_prices = await actual_service.get_historical_prices(
                        symbol, start_date, end_date
                    )
                
                if len(historical_prices) > 1:
                    prices = [float(price.price) for price in historical_prices]
                    returns = np.diff(np.log(prices))
                    volatility = float(np.std(returns) * np.sqrt(252))  # Annualized
                    volatilities[symbol] = volatility
                else:
                    volatilities[symbol] = 0.0
                    
            except Exception as e:
                logger.warning(f"Failed to calculate volatility for {symbol}: {e}")
                volatilities[symbol] = 0.0
        
        return volatilities
    
    def _create_default_risk_metrics(self) -> RiskMetrics:
        """Create default risk metrics when insufficient data."""
        return RiskMetrics(
            volatility_daily=0.0,
            volatility_annualized=0.0,
            var_95_daily=0.0,
            var_99_daily=0.0,
            var_95_monthly=0.0,
            var_99_monthly=0.0,
            sharpe_ratio=0.0,
            sortino_ratio=0.0,
            max_drawdown=0.0,
            max_drawdown_duration=0
        )
