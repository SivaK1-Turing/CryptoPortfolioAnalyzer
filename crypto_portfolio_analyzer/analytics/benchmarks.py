"""Benchmark comparison and market analysis."""

import numpy as np
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional, Tuple
import logging

from .models import BenchmarkComparison, PortfolioSnapshot
from ..data.service import get_data_service

logger = logging.getLogger(__name__)


class BenchmarkAnalyzer:
    """Benchmark comparison and market analysis engine."""
    
    def __init__(self, data_service=None):
        """Initialize benchmark analyzer.
        
        Args:
            data_service: Data service for market data
        """
        self.data_service = data_service
        
        # Common cryptocurrency benchmarks
        self.benchmarks = {
            'BTC': 'Bitcoin',
            'ETH': 'Ethereum', 
            'TOTAL_MARKET': 'Total Crypto Market',
            'TOP_10': 'Top 10 Cryptocurrencies',
            'DEFI': 'DeFi Index'
        }
    
    async def compare_to_benchmark(self, 
                                 portfolio_snapshots: List[PortfolioSnapshot],
                                 benchmark_symbol: str,
                                 period_days: int = 90) -> BenchmarkComparison:
        """Compare portfolio performance to a benchmark.
        
        Args:
            portfolio_snapshots: Historical portfolio snapshots
            benchmark_symbol: Benchmark symbol (e.g., 'BTC', 'ETH')
            period_days: Analysis period in days
            
        Returns:
            BenchmarkComparison with detailed metrics
        """
        if not self.data_service:
            self.data_service = await get_data_service()
        
        # Calculate portfolio returns
        portfolio_returns = self._calculate_portfolio_returns(portfolio_snapshots, period_days)
        
        if not portfolio_returns:
            return self._create_empty_benchmark_comparison(benchmark_symbol)
        
        # Get benchmark returns
        benchmark_returns = await self._get_benchmark_returns(benchmark_symbol, period_days)
        
        if not benchmark_returns:
            return self._create_empty_benchmark_comparison(benchmark_symbol)
        
        # Align returns (use minimum length)
        min_length = min(len(portfolio_returns), len(benchmark_returns))
        portfolio_returns = portfolio_returns[:min_length]
        benchmark_returns = benchmark_returns[:min_length]
        
        if min_length < 2:
            return self._create_empty_benchmark_comparison(benchmark_symbol)
        
        # Calculate performance metrics
        portfolio_return = self._calculate_total_return(portfolio_returns)
        benchmark_return = self._calculate_total_return(benchmark_returns)
        
        # Calculate alpha and beta
        alpha, beta = self._calculate_alpha_beta(portfolio_returns, benchmark_returns)
        
        # Calculate correlation
        correlation = self._calculate_correlation(portfolio_returns, benchmark_returns)
        
        # Calculate tracking error
        tracking_error = self._calculate_tracking_error(portfolio_returns, benchmark_returns)
        
        # Calculate information ratio
        information_ratio = self._calculate_information_ratio(
            portfolio_returns, benchmark_returns, tracking_error
        )
        
        # Calculate up/down capture ratios
        up_capture, down_capture = self._calculate_capture_ratios(
            portfolio_returns, benchmark_returns
        )
        
        return BenchmarkComparison(
            benchmark_name=self.benchmarks.get(benchmark_symbol, benchmark_symbol),
            portfolio_return=portfolio_return,
            benchmark_return=benchmark_return,
            alpha=alpha,
            beta=beta,
            correlation=correlation,
            tracking_error=tracking_error,
            information_ratio=information_ratio,
            up_capture=up_capture,
            down_capture=down_capture
        )
    
    async def compare_to_multiple_benchmarks(self,
                                           portfolio_snapshots: List[PortfolioSnapshot],
                                           benchmark_symbols: List[str],
                                           period_days: int = 90) -> List[BenchmarkComparison]:
        """Compare portfolio to multiple benchmarks.
        
        Args:
            portfolio_snapshots: Historical portfolio snapshots
            benchmark_symbols: List of benchmark symbols
            period_days: Analysis period in days
            
        Returns:
            List of BenchmarkComparison objects
        """
        comparisons = []
        
        for benchmark_symbol in benchmark_symbols:
            try:
                comparison = await self.compare_to_benchmark(
                    portfolio_snapshots, benchmark_symbol, period_days
                )
                comparisons.append(comparison)
            except Exception as e:
                logger.error(f"Failed to compare to benchmark {benchmark_symbol}: {e}")
        
        return comparisons
    
    async def calculate_market_beta(self, 
                                  portfolio_snapshots: List[PortfolioSnapshot],
                                  market_symbol: str = 'BTC',
                                  period_days: int = 90) -> float:
        """Calculate portfolio beta relative to market.
        
        Args:
            portfolio_snapshots: Historical portfolio snapshots
            market_symbol: Market proxy symbol
            period_days: Analysis period in days
            
        Returns:
            Portfolio beta
        """
        portfolio_returns = self._calculate_portfolio_returns(portfolio_snapshots, period_days)
        market_returns = await self._get_benchmark_returns(market_symbol, period_days)
        
        if not portfolio_returns or not market_returns:
            return 1.0
        
        # Align returns
        min_length = min(len(portfolio_returns), len(market_returns))
        portfolio_returns = portfolio_returns[:min_length]
        market_returns = market_returns[:min_length]
        
        if min_length < 2:
            return 1.0
        
        # Calculate beta
        _, beta = self._calculate_alpha_beta(portfolio_returns, market_returns)
        
        return beta
    
    async def _get_benchmark_returns(self, benchmark_symbol: str, period_days: int) -> List[float]:
        """Get historical returns for benchmark."""
        try:
            end_date = datetime.now(timezone.utc)
            start_date = end_date - timedelta(days=period_days)
            
            # Handle special benchmarks
            if benchmark_symbol == 'TOTAL_MARKET':
                # Use Bitcoin as proxy for total market (could be improved)
                benchmark_symbol = 'BTC'
            elif benchmark_symbol == 'TOP_10':
                # Use Ethereum as proxy for top 10 (could be improved)
                benchmark_symbol = 'ETH'
            elif benchmark_symbol == 'DEFI':
                # Use Ethereum as DeFi proxy
                benchmark_symbol = 'ETH'
            
            historical_prices = await self.data_service.get_historical_prices(
                benchmark_symbol, start_date, end_date
            )
            
            if len(historical_prices) < 2:
                return []
            
            # Calculate returns
            prices = [float(price.price) for price in historical_prices]
            returns = []
            
            for i in range(1, len(prices)):
                if prices[i-1] > 0:
                    daily_return = (prices[i] - prices[i-1]) / prices[i-1]
                    returns.append(daily_return)
            
            return returns
            
        except Exception as e:
            logger.error(f"Failed to get benchmark returns for {benchmark_symbol}: {e}")
            return []
    
    def _calculate_portfolio_returns(self, 
                                   snapshots: List[PortfolioSnapshot], 
                                   period_days: int) -> List[float]:
        """Calculate portfolio returns for the specified period."""
        if len(snapshots) < 2:
            return []
        
        # Filter snapshots within period
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=period_days)
        
        period_snapshots = [
            s for s in snapshots 
            if start_date <= s.timestamp <= end_date
        ]
        
        period_snapshots.sort(key=lambda x: x.timestamp)
        
        if len(period_snapshots) < 2:
            return []
        
        # Calculate daily returns
        returns = []
        for i in range(1, len(period_snapshots)):
            prev_value = float(period_snapshots[i-1].portfolio_value)
            curr_value = float(period_snapshots[i].portfolio_value)
            
            if prev_value > 0:
                daily_return = (curr_value - prev_value) / prev_value
                returns.append(daily_return)
        
        return returns
    
    def _calculate_total_return(self, returns: List[float]) -> float:
        """Calculate total return from daily returns."""
        if not returns:
            return 0.0
        
        total_return = 1.0
        for daily_return in returns:
            total_return *= (1 + daily_return)
        
        return (total_return - 1) * 100  # Convert to percentage
    
    def _calculate_alpha_beta(self, 
                            portfolio_returns: List[float],
                            benchmark_returns: List[float]) -> Tuple[float, float]:
        """Calculate alpha and beta using linear regression."""
        if len(portfolio_returns) != len(benchmark_returns) or len(portfolio_returns) < 2:
            return 0.0, 1.0
        
        portfolio_array = np.array(portfolio_returns)
        benchmark_array = np.array(benchmark_returns)
        
        # Calculate beta (slope of regression line)
        benchmark_variance = np.var(benchmark_array)
        if benchmark_variance > 0:
            covariance = np.cov(portfolio_array, benchmark_array)[0, 1]
            beta = covariance / benchmark_variance
        else:
            beta = 1.0
        
        # Calculate alpha (intercept of regression line)
        portfolio_mean = np.mean(portfolio_array)
        benchmark_mean = np.mean(benchmark_array)
        alpha = portfolio_mean - beta * benchmark_mean
        
        # Annualize alpha
        alpha_annualized = alpha * 252 * 100  # Convert to percentage
        
        return float(alpha_annualized), float(beta)
    
    def _calculate_correlation(self, 
                             portfolio_returns: List[float],
                             benchmark_returns: List[float]) -> float:
        """Calculate correlation between portfolio and benchmark."""
        if len(portfolio_returns) != len(benchmark_returns) or len(portfolio_returns) < 2:
            return 0.0
        
        portfolio_array = np.array(portfolio_returns)
        benchmark_array = np.array(benchmark_returns)
        
        correlation_matrix = np.corrcoef(portfolio_array, benchmark_array)
        correlation = correlation_matrix[0, 1]
        
        return float(correlation) if not np.isnan(correlation) else 0.0
    
    def _calculate_tracking_error(self, 
                                portfolio_returns: List[float],
                                benchmark_returns: List[float]) -> float:
        """Calculate tracking error (volatility of excess returns)."""
        if len(portfolio_returns) != len(benchmark_returns) or len(portfolio_returns) < 2:
            return 0.0
        
        excess_returns = np.array(portfolio_returns) - np.array(benchmark_returns)
        tracking_error = np.std(excess_returns) * np.sqrt(252)  # Annualized
        
        return float(tracking_error) * 100  # Convert to percentage
    
    def _calculate_information_ratio(self, 
                                   portfolio_returns: List[float],
                                   benchmark_returns: List[float],
                                   tracking_error: float) -> float:
        """Calculate information ratio (excess return / tracking error)."""
        if tracking_error == 0 or len(portfolio_returns) != len(benchmark_returns):
            return 0.0
        
        portfolio_return = self._calculate_total_return(portfolio_returns)
        benchmark_return = self._calculate_total_return(benchmark_returns)
        
        excess_return = portfolio_return - benchmark_return
        information_ratio = excess_return / tracking_error if tracking_error > 0 else 0.0
        
        return float(information_ratio)
    
    def _calculate_capture_ratios(self, 
                                portfolio_returns: List[float],
                                benchmark_returns: List[float]) -> Tuple[float, float]:
        """Calculate up and down capture ratios."""
        if len(portfolio_returns) != len(benchmark_returns) or len(portfolio_returns) < 2:
            return 100.0, 100.0
        
        portfolio_array = np.array(portfolio_returns)
        benchmark_array = np.array(benchmark_returns)
        
        # Separate up and down periods
        up_periods = benchmark_array > 0
        down_periods = benchmark_array < 0
        
        # Calculate up capture ratio
        if np.any(up_periods):
            portfolio_up = np.mean(portfolio_array[up_periods])
            benchmark_up = np.mean(benchmark_array[up_periods])
            up_capture = (portfolio_up / benchmark_up) * 100 if benchmark_up != 0 else 100.0
        else:
            up_capture = 100.0
        
        # Calculate down capture ratio
        if np.any(down_periods):
            portfolio_down = np.mean(portfolio_array[down_periods])
            benchmark_down = np.mean(benchmark_array[down_periods])
            down_capture = (portfolio_down / benchmark_down) * 100 if benchmark_down != 0 else 100.0
        else:
            down_capture = 100.0
        
        return float(up_capture), float(down_capture)
    
    def _create_empty_benchmark_comparison(self, benchmark_symbol: str) -> BenchmarkComparison:
        """Create empty benchmark comparison for insufficient data."""
        return BenchmarkComparison(
            benchmark_name=self.benchmarks.get(benchmark_symbol, benchmark_symbol),
            portfolio_return=0.0,
            benchmark_return=0.0,
            alpha=0.0,
            beta=1.0,
            correlation=0.0,
            tracking_error=0.0,
            information_ratio=0.0,
            up_capture=100.0,
            down_capture=100.0
        )
