"""Integrated risk management system combining assessment and compliance."""

from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from decimal import Decimal
import logging
import asyncio

from .assessment import RiskAssessmentEngine, RiskMetrics, StressTestScenario, STANDARD_STRESS_SCENARIOS
from .compliance import ComplianceMonitor, ComplianceReport, RiskLimit, ComplianceViolation
from ..analytics.models import PortfolioHolding

logger = logging.getLogger(__name__)


@dataclass
class RiskDashboard:
    """Comprehensive risk dashboard data."""
    timestamp: datetime
    portfolio_value: Decimal
    risk_metrics: RiskMetrics
    compliance_report: ComplianceReport
    stress_test_results: Dict[str, Any]
    position_risks: Dict[str, Dict[str, Any]]
    risk_score: float
    recommendations: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "portfolio_value": float(self.portfolio_value),
            "risk_metrics": self.risk_metrics.to_dict(),
            "compliance_report": self.compliance_report.to_dict(),
            "stress_test_results": self.stress_test_results,
            "position_risks": self.position_risks,
            "risk_score": self.risk_score,
            "recommendations": self.recommendations
        }


class RiskManager:
    """Integrated risk management system."""
    
    def __init__(self, lookback_days: int = 252):
        """Initialize risk manager.
        
        Args:
            lookback_days: Number of days for risk calculations
        """
        self.risk_engine = RiskAssessmentEngine(lookback_days)
        self.compliance_monitor = ComplianceMonitor()
        self.risk_handlers: List[callable] = []
        
        # Risk thresholds
        self.risk_thresholds = {
            "high_risk_var": 0.05,  # 5% of portfolio
            "high_risk_concentration": 0.40,  # 40% in single asset
            "high_risk_volatility": 0.50,  # 50% annualized volatility
            "critical_drawdown": 0.20  # 20% maximum drawdown
        }
    
    async def assess_portfolio_risk(
        self,
        holdings: List[PortfolioHolding],
        historical_returns: List[float],
        benchmark_returns: Optional[List[float]] = None
    ) -> RiskDashboard:
        """Perform comprehensive portfolio risk assessment.
        
        Args:
            holdings: Current portfolio holdings
            historical_returns: Historical portfolio returns
            benchmark_returns: Optional benchmark returns
            
        Returns:
            RiskDashboard with complete risk analysis
        """
        # Calculate portfolio value and positions
        portfolio_value = sum(h.market_value for h in holdings)
        portfolio_positions = {
            h.symbol: (h.quantity, h.current_price) for h in holdings
        }
        
        # 1. Risk Assessment
        risk_metrics = self.risk_engine.calculate_portfolio_risk(
            historical_returns, portfolio_value, benchmark_returns
        )
        
        # 2. Compliance Check
        compliance_report = self.compliance_monitor.check_compliance(
            portfolio_positions, portfolio_value, risk_metrics.to_dict()
        )
        
        # 3. Stress Testing
        stress_results = self.risk_engine.run_stress_test(
            portfolio_positions, STANDARD_STRESS_SCENARIOS
        )
        
        # 4. Position-level Risk Analysis
        position_risks = {}
        for holding in holdings:
            # For demo, use simplified historical returns
            # In production, this would use actual historical data for each asset
            position_returns = historical_returns[-30:] if len(historical_returns) >= 30 else historical_returns
            
            position_risk = self.risk_engine.calculate_position_risk(
                holding.symbol,
                holding.quantity,
                holding.current_price,
                position_returns
            )
            position_risks[holding.symbol] = position_risk
        
        # 5. Calculate Overall Risk Score
        risk_score = self._calculate_risk_score(risk_metrics, compliance_report, stress_results)
        
        # 6. Generate Recommendations
        recommendations = self._generate_recommendations(
            risk_metrics, compliance_report, stress_results, holdings
        )
        
        dashboard = RiskDashboard(
            timestamp=datetime.now(timezone.utc),
            portfolio_value=portfolio_value,
            risk_metrics=risk_metrics,
            compliance_report=compliance_report,
            stress_test_results=stress_results,
            position_risks=position_risks,
            risk_score=risk_score,
            recommendations=recommendations
        )
        
        # Notify risk handlers
        for handler in self.risk_handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(dashboard)
                else:
                    handler(dashboard)
            except Exception as e:
                logger.error(f"Error in risk handler: {e}")
        
        return dashboard
    
    def _calculate_risk_score(
        self,
        risk_metrics: RiskMetrics,
        compliance_report: ComplianceReport,
        stress_results: Dict[str, Any]
    ) -> float:
        """Calculate overall portfolio risk score (0-100, lower is better)."""
        score = 0.0
        
        # VaR component (0-30 points)
        var_ratio = float(risk_metrics.var_95 / risk_metrics.portfolio_value)
        var_score = min(30, var_ratio * 600)  # Scale to 0-30
        score += var_score
        
        # Volatility component (0-25 points)
        vol_score = min(25, risk_metrics.volatility_annualized * 50)
        score += vol_score
        
        # Compliance component (0-25 points)
        compliance_score = compliance_report.violated_limits * 5 + compliance_report.warning_limits * 2
        score += min(25, compliance_score)
        
        # Stress test component (0-20 points)
        worst_stress = min(
            result.get("percentage_impact", 0) 
            for result in stress_results.values()
        )
        stress_score = min(20, abs(worst_stress) / 5)  # Scale worst case scenario
        score += stress_score
        
        return min(100.0, score)
    
    def _generate_recommendations(
        self,
        risk_metrics: RiskMetrics,
        compliance_report: ComplianceReport,
        stress_results: Dict[str, Any],
        holdings: List[PortfolioHolding]
    ) -> List[str]:
        """Generate risk management recommendations."""
        recommendations = []
        
        # VaR recommendations
        var_ratio = float(risk_metrics.var_95 / risk_metrics.portfolio_value)
        if var_ratio > self.risk_thresholds["high_risk_var"]:
            recommendations.append(
                f"High VaR detected ({var_ratio:.1%} of portfolio). Consider reducing position sizes or diversifying."
            )
        
        # Volatility recommendations
        if risk_metrics.volatility_annualized > self.risk_thresholds["high_risk_volatility"]:
            recommendations.append(
                f"High portfolio volatility ({risk_metrics.volatility_annualized:.1%}). "
                "Consider adding less volatile assets or reducing leverage."
            )
        
        # Concentration recommendations
        if holdings:
            largest_position = max(holdings, key=lambda h: h.market_value)
            concentration = float(largest_position.market_value / risk_metrics.portfolio_value)
            
            if concentration > self.risk_thresholds["high_risk_concentration"]:
                recommendations.append(
                    f"High concentration in {largest_position.symbol} ({concentration:.1%}). "
                    "Consider rebalancing to reduce single-asset risk."
                )
        
        # Compliance recommendations
        if compliance_report.violated_limits > 0:
            recommendations.append(
                f"{compliance_report.violated_limits} compliance violations detected. "
                "Review position sizes and risk limits immediately."
            )
        
        # Stress test recommendations
        worst_scenario = min(
            stress_results.items(),
            key=lambda x: x[1].get("percentage_impact", 0)
        )
        if worst_scenario[1].get("percentage_impact", 0) < -50:
            recommendations.append(
                f"Severe stress test impact in '{worst_scenario[0]}' scenario "
                f"({worst_scenario[1]['percentage_impact']:.1f}%). Consider hedging strategies."
            )
        
        # Sharpe ratio recommendations
        if risk_metrics.sharpe_ratio < 0.5:
            recommendations.append(
                f"Low risk-adjusted returns (Sharpe: {risk_metrics.sharpe_ratio:.2f}). "
                "Review asset selection and consider higher-quality investments."
            )
        
        # Maximum drawdown recommendations
        if abs(float(risk_metrics.max_drawdown)) > self.risk_thresholds["critical_drawdown"]:
            recommendations.append(
                f"High maximum drawdown ({abs(float(risk_metrics.max_drawdown)):.1%}). "
                "Implement stop-loss strategies or reduce position sizes."
            )
        
        # Default recommendation if portfolio looks good
        if not recommendations:
            recommendations.append("Portfolio risk profile appears well-managed. Continue monitoring.")
        
        return recommendations
    
    def add_risk_limit(self, limit: RiskLimit):
        """Add new risk limit."""
        self.compliance_monitor.add_risk_limit(limit)
    
    def update_risk_thresholds(self, thresholds: Dict[str, float]):
        """Update risk assessment thresholds."""
        self.risk_thresholds.update(thresholds)
        logger.info("Updated risk thresholds")
    
    def add_risk_handler(self, handler: callable):
        """Add risk event handler."""
        self.risk_handlers.append(handler)
    
    def get_risk_summary(self, dashboard: RiskDashboard) -> Dict[str, Any]:
        """Get simplified risk summary."""
        return {
            "risk_score": dashboard.risk_score,
            "risk_level": self._get_risk_level(dashboard.risk_score),
            "var_95": float(dashboard.risk_metrics.var_95),
            "var_percentage": float(dashboard.risk_metrics.var_95 / dashboard.portfolio_value * 100),
            "volatility": dashboard.risk_metrics.volatility_annualized,
            "max_drawdown": float(dashboard.risk_metrics.max_drawdown),
            "compliance_status": dashboard.compliance_report.compliance_status.value,
            "violations": dashboard.compliance_report.violated_limits,
            "top_recommendation": dashboard.recommendations[0] if dashboard.recommendations else "No recommendations",
            "last_updated": dashboard.timestamp.isoformat()
        }
    
    def _get_risk_level(self, risk_score: float) -> str:
        """Convert risk score to risk level."""
        if risk_score <= 25:
            return "LOW"
        elif risk_score <= 50:
            return "MODERATE"
        elif risk_score <= 75:
            return "HIGH"
        else:
            return "CRITICAL"
    
    async def run_custom_stress_test(
        self,
        holdings: List[PortfolioHolding],
        custom_scenarios: List[StressTestScenario]
    ) -> Dict[str, Any]:
        """Run custom stress test scenarios."""
        portfolio_positions = {
            h.symbol: (h.quantity, h.current_price) for h in holdings
        }
        
        return self.risk_engine.run_stress_test(portfolio_positions, custom_scenarios)
    
    def generate_risk_report(self, dashboard: RiskDashboard) -> str:
        """Generate formatted risk report."""
        report_lines = [
            "PORTFOLIO RISK ASSESSMENT REPORT",
            "=" * 50,
            f"Generated: {dashboard.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}",
            f"Portfolio Value: ${dashboard.portfolio_value:,.2f}",
            f"Risk Score: {dashboard.risk_score:.1f}/100 ({self._get_risk_level(dashboard.risk_score)})",
            "",
            "RISK METRICS:",
            f"  • VaR (95%): ${dashboard.risk_metrics.var_95:,.2f} ({float(dashboard.risk_metrics.var_95/dashboard.portfolio_value*100):.1f}%)",
            f"  • VaR (99%): ${dashboard.risk_metrics.var_99:,.2f}",
            f"  • Expected Shortfall: ${dashboard.risk_metrics.expected_shortfall:,.2f}",
            f"  • Volatility (Annual): {dashboard.risk_metrics.volatility_annualized:.1%}",
            f"  • Maximum Drawdown: {float(dashboard.risk_metrics.max_drawdown):.1%}",
            f"  • Sharpe Ratio: {dashboard.risk_metrics.sharpe_ratio:.2f}",
            f"  • Beta: {dashboard.risk_metrics.beta:.2f}",
            "",
            "COMPLIANCE STATUS:",
            f"  • Overall Status: {dashboard.compliance_report.compliance_status.value.upper()}",
            f"  • Violations: {dashboard.compliance_report.violated_limits}",
            f"  • Warnings: {dashboard.compliance_report.warning_limits}",
            "",
            "STRESS TEST RESULTS:",
        ]
        
        for scenario_name, result in dashboard.stress_test_results.items():
            impact = result.get("percentage_impact", 0)
            report_lines.append(f"  • {scenario_name}: {impact:+.1f}%")
        
        report_lines.extend([
            "",
            "RECOMMENDATIONS:",
        ])
        
        for i, rec in enumerate(dashboard.recommendations, 1):
            report_lines.append(f"  {i}. {rec}")
        
        return "\n".join(report_lines)


# Convenience functions
def create_basic_risk_manager() -> RiskManager:
    """Create risk manager with basic configuration."""
    return RiskManager(lookback_days=252)


def create_conservative_risk_manager() -> RiskManager:
    """Create risk manager with conservative settings."""
    manager = RiskManager(lookback_days=252)
    
    # Add conservative risk limits
    from .compliance import RiskLimit, LimitType
    
    conservative_limits = [
        RiskLimit(
            limit_id="conservative_position",
            limit_type=LimitType.POSITION_LIMIT,
            description="Conservative position limit",
            threshold_value=Decimal("25000"),  # $25k max position
            threshold_percentage=15.0  # 15% max concentration
        ),
        RiskLimit(
            limit_id="conservative_var",
            limit_type=LimitType.VAR_LIMIT,
            description="Conservative VaR limit",
            threshold_value=Decimal("5000"),  # $5k daily VaR
            threshold_percentage=2.5  # 2.5% of portfolio
        )
    ]
    
    for limit in conservative_limits:
        manager.add_risk_limit(limit)
    
    # Update risk thresholds
    manager.update_risk_thresholds({
        "high_risk_var": 0.025,  # 2.5%
        "high_risk_concentration": 0.25,  # 25%
        "high_risk_volatility": 0.30,  # 30%
        "critical_drawdown": 0.15  # 15%
    })
    
    return manager
