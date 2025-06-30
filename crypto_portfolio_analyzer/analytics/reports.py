"""Report generation and formatting module."""

import json
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
import logging

from .models import AnalyticsReport, PortfolioSnapshot, PerformanceMetrics, RiskMetrics, AllocationMetrics

logger = logging.getLogger(__name__)


class ReportGenerator:
    """Generate comprehensive portfolio reports."""
    
    def __init__(self):
        """Initialize report generator."""
        pass
    
    def generate_json_report(self, analytics_report: AnalyticsReport) -> str:
        """Generate JSON format report.
        
        Args:
            analytics_report: Analytics report data
            
        Returns:
            JSON formatted report string
        """
        try:
            report_dict = analytics_report.to_dict()
            return json.dumps(report_dict, indent=2, default=str)
        except Exception as e:
            logger.error(f"Failed to generate JSON report: {e}")
            return "{}"
    
    def generate_summary_report(self, analytics_report: AnalyticsReport) -> Dict[str, Any]:
        """Generate summary report with key metrics.
        
        Args:
            analytics_report: Analytics report data
            
        Returns:
            Summary report dictionary
        """
        try:
            snapshot = analytics_report.portfolio_snapshot
            
            # Get latest performance metrics
            latest_performance = None
            if analytics_report.performance_metrics:
                latest_performance = list(analytics_report.performance_metrics.values())[-1]
            
            summary = {
                'report_id': analytics_report.report_id,
                'generated_at': analytics_report.generated_at.isoformat(),
                'portfolio_summary': {
                    'total_value': float(snapshot.total_value),
                    'total_cost': float(snapshot.total_cost),
                    'unrealized_pnl': float(snapshot.total_unrealized_pnl),
                    'unrealized_pnl_percentage': snapshot.total_unrealized_pnl_percentage,
                    'holdings_count': len(snapshot.holdings),
                    'cash_balance': float(snapshot.cash_balance)
                },
                'performance_summary': {
                    'total_return_percentage': latest_performance.total_return_percentage if latest_performance else 0.0,
                    'annualized_return': latest_performance.annualized_return if latest_performance else 0.0,
                    'volatility': latest_performance.volatility if latest_performance else 0.0,
                    'sharpe_ratio': latest_performance.sharpe_ratio if latest_performance else None
                },
                'risk_summary': {
                    'volatility_annualized': analytics_report.risk_metrics.volatility_annualized,
                    'var_95_daily': analytics_report.risk_metrics.var_95_daily,
                    'max_drawdown': analytics_report.risk_metrics.max_drawdown,
                    'sharpe_ratio': analytics_report.risk_metrics.sharpe_ratio
                },
                'allocation_summary': {
                    'largest_position': analytics_report.allocation_metrics.largest_position,
                    'concentration_risk': analytics_report.allocation_metrics.concentration_risk,
                    'effective_assets': analytics_report.allocation_metrics.effective_assets,
                    'top_holdings': dict(list(analytics_report.allocation_metrics.allocations.items())[:5])
                },
                'alerts_count': len(analytics_report.alerts),
                'benchmark_count': len(analytics_report.benchmark_comparisons)
            }
            
            return summary
            
        except Exception as e:
            logger.error(f"Failed to generate summary report: {e}")
            return {}
    
    def generate_performance_report(self, performance_metrics: Dict[Any, PerformanceMetrics]) -> Dict[str, Any]:
        """Generate detailed performance report.
        
        Args:
            performance_metrics: Performance metrics by period
            
        Returns:
            Performance report dictionary
        """
        try:
            report = {
                'performance_analysis': {},
                'summary': {
                    'best_period': None,
                    'worst_period': None,
                    'average_return': 0.0,
                    'volatility_range': {'min': 0.0, 'max': 0.0}
                }
            }
            
            returns = []
            volatilities = []
            
            for period, metrics in performance_metrics.items():
                period_data = {
                    'period': period.value if hasattr(period, 'value') else str(period),
                    'total_return_percentage': metrics.total_return_percentage,
                    'annualized_return': metrics.annualized_return,
                    'volatility': metrics.volatility,
                    'sharpe_ratio': metrics.sharpe_ratio,
                    'max_drawdown': metrics.max_drawdown,
                    'win_rate': metrics.win_rate,
                    'days_elapsed': metrics.days_elapsed
                }
                
                report['performance_analysis'][period_data['period']] = period_data
                returns.append(metrics.total_return_percentage)
                volatilities.append(metrics.volatility)
            
            # Calculate summary statistics
            if returns:
                best_return = max(returns)
                worst_return = min(returns)
                
                # Find periods with best/worst returns
                for period, metrics in performance_metrics.items():
                    if metrics.total_return_percentage == best_return:
                        report['summary']['best_period'] = period.value if hasattr(period, 'value') else str(period)
                    if metrics.total_return_percentage == worst_return:
                        report['summary']['worst_period'] = period.value if hasattr(period, 'value') else str(period)
                
                report['summary']['average_return'] = sum(returns) / len(returns)
                
            if volatilities:
                report['summary']['volatility_range'] = {
                    'min': min(volatilities),
                    'max': max(volatilities)
                }
            
            return report
            
        except Exception as e:
            logger.error(f"Failed to generate performance report: {e}")
            return {}
    
    def generate_risk_report(self, risk_metrics: RiskMetrics) -> Dict[str, Any]:
        """Generate detailed risk analysis report.
        
        Args:
            risk_metrics: Risk metrics data
            
        Returns:
            Risk report dictionary
        """
        try:
            report = {
                'risk_analysis': risk_metrics.to_dict(),
                'risk_assessment': {
                    'volatility_level': self._assess_volatility_level(risk_metrics.volatility_annualized),
                    'var_assessment': self._assess_var_level(risk_metrics.var_95_daily),
                    'sharpe_assessment': self._assess_sharpe_ratio(risk_metrics.sharpe_ratio),
                    'drawdown_assessment': self._assess_drawdown_level(risk_metrics.max_drawdown),
                    'overall_risk_score': self._calculate_overall_risk_score(risk_metrics)
                },
                'recommendations': self._generate_risk_recommendations(risk_metrics)
            }
            
            return report
            
        except Exception as e:
            logger.error(f"Failed to generate risk report: {e}")
            return {}
    
    def generate_allocation_report(self, allocation_metrics: AllocationMetrics) -> Dict[str, Any]:
        """Generate detailed allocation analysis report.
        
        Args:
            allocation_metrics: Allocation metrics data
            
        Returns:
            Allocation report dictionary
        """
        try:
            report = {
                'allocation_analysis': allocation_metrics.to_dict(),
                'diversification_assessment': {
                    'concentration_level': self._assess_concentration_level(allocation_metrics.concentration_risk),
                    'diversification_level': self._assess_diversification_level(allocation_metrics.diversification_ratio),
                    'effective_assets_assessment': self._assess_effective_assets(allocation_metrics.effective_assets),
                    'overall_diversification_score': self._calculate_diversification_score(allocation_metrics)
                },
                'rebalancing_analysis': {
                    'needs_rebalancing': len(allocation_metrics.rebalancing_suggestions) > 0,
                    'priority_actions': [
                        suggestion for suggestion in allocation_metrics.rebalancing_suggestions
                        if suggestion.get('priority') == 'HIGH'
                    ],
                    'total_suggestions': len(allocation_metrics.rebalancing_suggestions)
                }
            }
            
            return report
            
        except Exception as e:
            logger.error(f"Failed to generate allocation report: {e}")
            return {}
    
    def _assess_volatility_level(self, volatility: float) -> str:
        """Assess volatility level."""
        if volatility < 0.2:
            return "LOW"
        elif volatility < 0.5:
            return "MODERATE"
        elif volatility < 1.0:
            return "HIGH"
        else:
            return "VERY_HIGH"
    
    def _assess_var_level(self, var_95: float) -> str:
        """Assess Value at Risk level."""
        var_abs = abs(var_95)
        if var_abs < 0.02:
            return "LOW"
        elif var_abs < 0.05:
            return "MODERATE"
        elif var_abs < 0.1:
            return "HIGH"
        else:
            return "VERY_HIGH"
    
    def _assess_sharpe_ratio(self, sharpe_ratio: float) -> str:
        """Assess Sharpe ratio level."""
        if sharpe_ratio < 0:
            return "POOR"
        elif sharpe_ratio < 0.5:
            return "BELOW_AVERAGE"
        elif sharpe_ratio < 1.0:
            return "AVERAGE"
        elif sharpe_ratio < 2.0:
            return "GOOD"
        else:
            return "EXCELLENT"
    
    def _assess_drawdown_level(self, max_drawdown: float) -> str:
        """Assess maximum drawdown level."""
        if max_drawdown < 5:
            return "LOW"
        elif max_drawdown < 15:
            return "MODERATE"
        elif max_drawdown < 30:
            return "HIGH"
        else:
            return "VERY_HIGH"
    
    def _calculate_overall_risk_score(self, risk_metrics: RiskMetrics) -> float:
        """Calculate overall risk score (0-100, higher = riskier)."""
        # Normalize different risk metrics to 0-100 scale
        vol_score = min(100, risk_metrics.volatility_annualized * 100)
        var_score = min(100, abs(risk_metrics.var_95_daily) * 1000)
        drawdown_score = min(100, risk_metrics.max_drawdown)
        
        # Sharpe ratio contributes negatively to risk (higher Sharpe = lower risk)
        sharpe_score = max(0, 50 - (risk_metrics.sharpe_ratio * 25))
        
        # Weighted average
        overall_score = (vol_score * 0.3 + var_score * 0.3 + drawdown_score * 0.3 + sharpe_score * 0.1)
        
        return min(100, max(0, overall_score))
    
    def _generate_risk_recommendations(self, risk_metrics: RiskMetrics) -> List[str]:
        """Generate risk management recommendations."""
        recommendations = []
        
        if risk_metrics.volatility_annualized > 1.0:
            recommendations.append("Consider reducing position sizes or diversifying to lower volatility")
        
        if abs(risk_metrics.var_95_daily) > 0.1:
            recommendations.append("High Value at Risk detected - consider risk management strategies")
        
        if risk_metrics.max_drawdown > 30:
            recommendations.append("Significant drawdown risk - implement stop-loss strategies")
        
        if risk_metrics.sharpe_ratio < 0.5:
            recommendations.append("Poor risk-adjusted returns - review investment strategy")
        
        if not recommendations:
            recommendations.append("Risk profile appears reasonable - continue monitoring")
        
        return recommendations
    
    def _assess_concentration_level(self, concentration_risk: float) -> str:
        """Assess portfolio concentration level."""
        if concentration_risk < 20:
            return "LOW"
        elif concentration_risk < 40:
            return "MODERATE"
        elif concentration_risk < 70:
            return "HIGH"
        else:
            return "VERY_HIGH"
    
    def _assess_diversification_level(self, diversification_ratio: float) -> str:
        """Assess diversification level."""
        if diversification_ratio > 0.8:
            return "EXCELLENT"
        elif diversification_ratio > 0.6:
            return "GOOD"
        elif diversification_ratio > 0.4:
            return "MODERATE"
        else:
            return "POOR"
    
    def _assess_effective_assets(self, effective_assets: float) -> str:
        """Assess effective number of assets."""
        if effective_assets >= 10:
            return "HIGHLY_DIVERSIFIED"
        elif effective_assets >= 5:
            return "WELL_DIVERSIFIED"
        elif effective_assets >= 3:
            return "MODERATELY_DIVERSIFIED"
        else:
            return "POORLY_DIVERSIFIED"
    
    def _calculate_diversification_score(self, allocation_metrics: AllocationMetrics) -> float:
        """Calculate overall diversification score (0-100, higher = better diversified)."""
        # Invert concentration risk (lower concentration = higher score)
        concentration_score = 100 - allocation_metrics.concentration_risk
        
        # Diversification ratio score
        diversification_score = allocation_metrics.diversification_ratio * 100
        
        # Effective assets score (normalized)
        effective_assets_score = min(100, (allocation_metrics.effective_assets / 10) * 100)
        
        # Weighted average
        overall_score = (concentration_score * 0.4 + diversification_score * 0.4 + effective_assets_score * 0.2)
        
        return min(100, max(0, overall_score))
