"""Advanced risk assessment engine for portfolio risk management."""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timezone, timedelta
from decimal import Decimal
import logging
from scipy import stats
import warnings

logger = logging.getLogger(__name__)


class RiskMetricType(Enum):
    """Types of risk metrics."""
    VALUE_AT_RISK = "var"
    CONDITIONAL_VAR = "cvar"
    EXPECTED_SHORTFALL = "expected_shortfall"
    MAXIMUM_DRAWDOWN = "max_drawdown"
    VOLATILITY = "volatility"
    BETA = "beta"
    CORRELATION = "correlation"
    SHARPE_RATIO = "sharpe_ratio"
    SORTINO_RATIO = "sortino_ratio"


class ConfidenceLevel(Enum):
    """Confidence levels for risk calculations."""
    NINETY_FIVE = 0.95
    NINETY_NINE = 0.99
    NINETY_NINE_NINE = 0.999


@dataclass
class RiskMetrics:
    """Container for risk assessment results."""
    portfolio_value: Decimal
    var_95: Decimal  # Value at Risk at 95% confidence
    var_99: Decimal  # Value at Risk at 99% confidence
    cvar_95: Decimal  # Conditional VaR at 95%
    cvar_99: Decimal  # Conditional VaR at 99%
    expected_shortfall: Decimal
    max_drawdown: Decimal
    volatility_daily: float
    volatility_annualized: float
    beta: float
    correlation_btc: float
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float
    calculated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "portfolio_value": float(self.portfolio_value),
            "var_95": float(self.var_95),
            "var_99": float(self.var_99),
            "cvar_95": float(self.cvar_95),
            "cvar_99": float(self.cvar_99),
            "expected_shortfall": float(self.expected_shortfall),
            "max_drawdown": float(self.max_drawdown),
            "volatility_daily": self.volatility_daily,
            "volatility_annualized": self.volatility_annualized,
            "beta": self.beta,
            "correlation_btc": self.correlation_btc,
            "sharpe_ratio": self.sharpe_ratio,
            "sortino_ratio": self.sortino_ratio,
            "calmar_ratio": self.calmar_ratio,
            "calculated_at": self.calculated_at.isoformat()
        }


@dataclass
class StressTestScenario:
    """Stress test scenario definition."""
    name: str
    description: str
    price_shocks: Dict[str, float]  # Symbol -> percentage change
    correlation_changes: Optional[Dict[str, float]] = None
    volatility_multiplier: float = 1.0
    
    def apply_shock(self, current_prices: Dict[str, Decimal]) -> Dict[str, Decimal]:
        """Apply stress scenario to current prices."""
        shocked_prices = {}
        for symbol, current_price in current_prices.items():
            shock = self.price_shocks.get(symbol, 0.0)
            shocked_price = current_price * Decimal(str(1 + shock))
            shocked_prices[symbol] = shocked_price
        return shocked_prices


class RiskAssessmentEngine:
    """Advanced risk assessment engine."""
    
    def __init__(self, lookback_days: int = 252):
        """Initialize risk assessment engine.
        
        Args:
            lookback_days: Number of days to look back for calculations
        """
        self.lookback_days = lookback_days
        self.risk_free_rate = 0.02  # 2% annual risk-free rate
        
    def calculate_portfolio_risk(
        self,
        portfolio_returns: List[float],
        portfolio_value: Decimal,
        benchmark_returns: Optional[List[float]] = None
    ) -> RiskMetrics:
        """Calculate comprehensive risk metrics for portfolio.
        
        Args:
            portfolio_returns: List of daily portfolio returns
            portfolio_value: Current portfolio value
            benchmark_returns: Optional benchmark returns for beta calculation
            
        Returns:
            RiskMetrics object with all calculated metrics
        """
        if len(portfolio_returns) < 30:
            logger.warning("Insufficient data for reliable risk calculations")
        
        returns_array = np.array(portfolio_returns)
        
        # Calculate VaR and CVaR
        var_95 = self._calculate_var(returns_array, 0.95, portfolio_value)
        var_99 = self._calculate_var(returns_array, 0.99, portfolio_value)
        cvar_95 = self._calculate_cvar(returns_array, 0.95, portfolio_value)
        cvar_99 = self._calculate_cvar(returns_array, 0.99, portfolio_value)
        
        # Calculate volatility
        daily_vol = np.std(returns_array)
        annual_vol = daily_vol * np.sqrt(252)
        
        # Calculate maximum drawdown
        max_dd = self._calculate_max_drawdown(returns_array)
        
        # Calculate Sharpe ratio
        excess_returns = returns_array - (self.risk_free_rate / 252)
        sharpe = np.mean(excess_returns) / np.std(excess_returns) * np.sqrt(252) if np.std(excess_returns) > 0 else 0
        
        # Calculate Sortino ratio
        downside_returns = returns_array[returns_array < 0]
        downside_std = np.std(downside_returns) if len(downside_returns) > 0 else 0
        sortino = np.mean(excess_returns) / downside_std * np.sqrt(252) if downside_std > 0 else 0
        
        # Calculate Calmar ratio
        annual_return = np.mean(returns_array) * 252
        calmar = annual_return / abs(max_dd) if max_dd != 0 else 0
        
        # Calculate beta and correlation
        beta = 1.0
        correlation_btc = 0.0
        if benchmark_returns and len(benchmark_returns) == len(portfolio_returns):
            beta, correlation_btc = self._calculate_beta_correlation(returns_array, np.array(benchmark_returns))
        
        # Expected shortfall (same as CVaR 95%)
        expected_shortfall = cvar_95
        
        return RiskMetrics(
            portfolio_value=portfolio_value,
            var_95=var_95,
            var_99=var_99,
            cvar_95=cvar_95,
            cvar_99=cvar_99,
            expected_shortfall=expected_shortfall,
            max_drawdown=Decimal(str(max_dd)),
            volatility_daily=daily_vol,
            volatility_annualized=annual_vol,
            beta=beta,
            correlation_btc=correlation_btc,
            sharpe_ratio=sharpe,
            sortino_ratio=sortino,
            calmar_ratio=calmar
        )
    
    def _calculate_var(self, returns: np.ndarray, confidence_level: float, portfolio_value: Decimal) -> Decimal:
        """Calculate Value at Risk."""
        if len(returns) == 0:
            return Decimal('0')
        
        percentile = (1 - confidence_level) * 100
        var_return = np.percentile(returns, percentile)
        var_amount = abs(var_return * float(portfolio_value))
        return Decimal(str(var_amount))
    
    def _calculate_cvar(self, returns: np.ndarray, confidence_level: float, portfolio_value: Decimal) -> Decimal:
        """Calculate Conditional Value at Risk (Expected Shortfall)."""
        if len(returns) == 0:
            return Decimal('0')
        
        percentile = (1 - confidence_level) * 100
        var_threshold = np.percentile(returns, percentile)
        tail_returns = returns[returns <= var_threshold]
        
        if len(tail_returns) == 0:
            return Decimal('0')
        
        cvar_return = np.mean(tail_returns)
        cvar_amount = abs(cvar_return * float(portfolio_value))
        return Decimal(str(cvar_amount))
    
    def _calculate_max_drawdown(self, returns: np.ndarray) -> float:
        """Calculate maximum drawdown."""
        if len(returns) == 0:
            return 0.0
        
        cumulative_returns = np.cumprod(1 + returns)
        running_max = np.maximum.accumulate(cumulative_returns)
        drawdowns = (cumulative_returns - running_max) / running_max
        return float(np.min(drawdowns))
    
    def _calculate_beta_correlation(self, portfolio_returns: np.ndarray, benchmark_returns: np.ndarray) -> Tuple[float, float]:
        """Calculate beta and correlation with benchmark."""
        if len(portfolio_returns) != len(benchmark_returns) or len(portfolio_returns) < 2:
            return 1.0, 0.0
        
        # Calculate correlation
        correlation = np.corrcoef(portfolio_returns, benchmark_returns)[0, 1]
        if np.isnan(correlation):
            correlation = 0.0
        
        # Calculate beta
        portfolio_var = np.var(portfolio_returns)
        benchmark_var = np.var(benchmark_returns)
        
        if benchmark_var > 0:
            covariance = np.cov(portfolio_returns, benchmark_returns)[0, 1]
            beta = covariance / benchmark_var
        else:
            beta = 1.0
        
        return float(beta), float(correlation)
    
    def run_stress_test(
        self,
        current_portfolio: Dict[str, Tuple[Decimal, Decimal]],  # symbol -> (quantity, price)
        scenarios: List[StressTestScenario]
    ) -> Dict[str, Dict[str, Any]]:
        """Run stress tests on portfolio.
        
        Args:
            current_portfolio: Current portfolio positions
            scenarios: List of stress test scenarios
            
        Returns:
            Dictionary of scenario results
        """
        results = {}
        
        # Calculate current portfolio value
        current_value = sum(quantity * price for quantity, price in current_portfolio.values())
        current_prices = {symbol: price for symbol, (_, price) in current_portfolio.items()}
        
        for scenario in scenarios:
            # Apply price shocks
            shocked_prices = scenario.apply_shock(current_prices)
            
            # Calculate new portfolio value
            new_value = sum(
                quantity * shocked_prices.get(symbol, price)
                for symbol, (quantity, price) in current_portfolio.items()
            )
            
            # Calculate impact
            absolute_impact = new_value - current_value
            percentage_impact = float(absolute_impact / current_value * 100) if current_value > 0 else 0
            
            results[scenario.name] = {
                "scenario_description": scenario.description,
                "current_value": float(current_value),
                "stressed_value": float(new_value),
                "absolute_impact": float(absolute_impact),
                "percentage_impact": percentage_impact,
                "price_shocks": scenario.price_shocks,
                "volatility_multiplier": scenario.volatility_multiplier
            }
        
        return results
    
    def calculate_position_risk(
        self,
        symbol: str,
        quantity: Decimal,
        current_price: Decimal,
        historical_returns: List[float]
    ) -> Dict[str, Any]:
        """Calculate risk metrics for individual position.
        
        Args:
            symbol: Asset symbol
            quantity: Position quantity
            current_price: Current asset price
            historical_returns: Historical daily returns
            
        Returns:
            Dictionary of position risk metrics
        """
        position_value = quantity * current_price
        returns_array = np.array(historical_returns)
        
        if len(returns_array) == 0:
            return {
                "symbol": symbol,
                "position_value": float(position_value),
                "var_95": 0.0,
                "var_99": 0.0,
                "volatility": 0.0,
                "max_drawdown": 0.0
            }
        
        # Calculate position-specific metrics
        var_95 = self._calculate_var(returns_array, 0.95, position_value)
        var_99 = self._calculate_var(returns_array, 0.99, position_value)
        volatility = np.std(returns_array) * np.sqrt(252)
        max_dd = self._calculate_max_drawdown(returns_array)
        
        return {
            "symbol": symbol,
            "position_value": float(position_value),
            "var_95": float(var_95),
            "var_99": float(var_99),
            "volatility_annualized": volatility,
            "max_drawdown": max_dd,
            "quantity": float(quantity),
            "current_price": float(current_price)
        }


# Predefined stress test scenarios
STANDARD_STRESS_SCENARIOS = [
    StressTestScenario(
        name="crypto_crash_2022",
        description="Crypto market crash similar to 2022 (BTC -70%, ETH -80%, Alts -85%)",
        price_shocks={
            "BTC": -0.70,
            "ETH": -0.80,
            "SOL": -0.85,
            "ADA": -0.85,
            "MATIC": -0.85,
            "DOT": -0.85
        }
    ),
    StressTestScenario(
        name="moderate_correction",
        description="Moderate market correction (BTC -30%, ETH -40%, Alts -50%)",
        price_shocks={
            "BTC": -0.30,
            "ETH": -0.40,
            "SOL": -0.50,
            "ADA": -0.50,
            "MATIC": -0.50,
            "DOT": -0.50
        }
    ),
    StressTestScenario(
        name="regulatory_crackdown",
        description="Regulatory crackdown scenario (All assets -60%)",
        price_shocks={
            "BTC": -0.60,
            "ETH": -0.60,
            "SOL": -0.60,
            "ADA": -0.60,
            "MATIC": -0.60,
            "DOT": -0.60
        }
    ),
    StressTestScenario(
        name="bull_market_surge",
        description="Bull market surge (BTC +200%, ETH +300%, Alts +500%)",
        price_shocks={
            "BTC": 2.00,
            "ETH": 3.00,
            "SOL": 5.00,
            "ADA": 5.00,
            "MATIC": 5.00,
            "DOT": 5.00
        }
    )
]
