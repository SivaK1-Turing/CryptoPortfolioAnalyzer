#!/usr/bin/env python3
"""
Demo script showing how to use Feature 8: Advanced Risk Management and Compliance.
This demonstrates practical usage of the risk management system.
"""

import sys
import asyncio
import numpy as np
from pathlib import Path
from datetime import datetime, timezone
from decimal import Decimal

# Add the project root to Python path
sys.path.insert(0, str(Path(__file__).parent))

from crypto_portfolio_analyzer.risk import (
    create_basic_risk_manager, create_conservative_risk_manager,
    RiskLimit, LimitType, StressTestScenario, STANDARD_STRESS_SCENARIOS
)
from crypto_portfolio_analyzer.analytics.models import PortfolioHolding


def create_demo_portfolio() -> list:
    """Create a demo portfolio for risk analysis."""
    return [
        PortfolioHolding(
            symbol="BTC",
            quantity=Decimal("1.5"),
            average_cost=Decimal("45000"),
            current_price=Decimal("52000")
        ),
        PortfolioHolding(
            symbol="ETH",
            quantity=Decimal("12.0"),
            average_cost=Decimal("3000"),
            current_price=Decimal("3800")
        ),
        PortfolioHolding(
            symbol="SOL",
            quantity=Decimal("80.0"),
            average_cost=Decimal("80"),
            current_price=Decimal("110")
        ),
        PortfolioHolding(
            symbol="ADA",
            quantity=Decimal("3000.0"),
            average_cost=Decimal("1.0"),
            current_price=Decimal("1.3")
        ),
        PortfolioHolding(
            symbol="MATIC",
            quantity=Decimal("2000.0"),
            average_cost=Decimal("1.2"),
            current_price=Decimal("1.8")
        )
    ]


def generate_realistic_returns(days: int = 252) -> list:
    """Generate realistic crypto portfolio returns."""
    np.random.seed(42)
    
    # Simulate crypto-like returns with higher volatility and some correlation
    base_return = 0.0008  # ~20% annual return
    volatility = 0.035    # ~55% annual volatility
    
    returns = []
    for i in range(days):
        # Add some autocorrelation and volatility clustering
        if i == 0:
            daily_return = np.random.normal(base_return, volatility)
        else:
            # Simple GARCH-like effect
            prev_return = returns[i-1]
            vol_adjustment = 1 + abs(prev_return) * 2
            daily_return = np.random.normal(base_return, volatility * vol_adjustment)
        
        returns.append(daily_return)
    
    return returns


async def demo_basic_risk_assessment():
    """Demonstrate basic risk assessment."""
    print("🔍 BASIC RISK ASSESSMENT DEMO")
    print("=" * 50)
    
    # Create portfolio and risk manager
    portfolio = create_demo_portfolio()
    risk_manager = create_basic_risk_manager()
    
    # Generate historical returns
    historical_returns = generate_realistic_returns(180)  # 6 months of data
    benchmark_returns = generate_realistic_returns(180)   # BTC benchmark
    
    # Calculate portfolio value
    total_value = sum(h.market_value for h in portfolio)
    print(f"📊 Portfolio Overview:")
    print(f"  • Total Value: ${total_value:,.2f}")
    print(f"  • Holdings: {len(portfolio)} assets")
    
    for holding in portfolio:
        allocation = float(holding.market_value / total_value * 100)
        print(f"  • {holding.symbol}: ${holding.market_value:,.2f} ({allocation:.1f}%)")
    
    # Perform risk assessment
    print(f"\n🔍 Performing Risk Assessment...")
    dashboard = await risk_manager.assess_portfolio_risk(
        portfolio, historical_returns, benchmark_returns
    )
    
    # Display results
    print(f"\n📊 RISK ASSESSMENT RESULTS:")
    print(f"  • Risk Score: {dashboard.risk_score:.1f}/100 ({risk_manager._get_risk_level(dashboard.risk_score)})")
    print(f"  • VaR (95%): ${dashboard.risk_metrics.var_95:,.2f} ({float(dashboard.risk_metrics.var_95/dashboard.portfolio_value*100):.1f}%)")
    print(f"  • Expected Shortfall: ${dashboard.risk_metrics.expected_shortfall:,.2f}")
    print(f"  • Volatility: {dashboard.risk_metrics.volatility_annualized:.1%}")
    print(f"  • Max Drawdown: {float(dashboard.risk_metrics.max_drawdown):.1%}")
    print(f"  • Sharpe Ratio: {dashboard.risk_metrics.sharpe_ratio:.2f}")
    
    print(f"\n🚨 COMPLIANCE STATUS:")
    print(f"  • Status: {dashboard.compliance_report.compliance_status.value.upper()}")
    print(f"  • Violations: {dashboard.compliance_report.violated_limits}")
    print(f"  • Warnings: {dashboard.compliance_report.warning_limits}")
    
    if dashboard.compliance_report.violations:
        print(f"  • Issues:")
        for violation in dashboard.compliance_report.violations[:3]:  # Show top 3
            print(f"    - {violation.description}")
    
    print(f"\n💡 TOP RECOMMENDATIONS:")
    for i, rec in enumerate(dashboard.recommendations[:3], 1):
        print(f"  {i}. {rec}")
    
    return dashboard


async def demo_stress_testing():
    """Demonstrate stress testing."""
    print(f"\n🧪 STRESS TESTING DEMO")
    print("=" * 50)
    
    portfolio = create_demo_portfolio()
    risk_manager = create_basic_risk_manager()
    
    # Run standard stress tests
    stress_results = await risk_manager.run_custom_stress_test(portfolio, STANDARD_STRESS_SCENARIOS)
    
    print(f"📊 STRESS TEST RESULTS:")
    current_value = sum(h.market_value for h in portfolio)
    
    for scenario_name, result in stress_results.items():
        impact = result['percentage_impact']
        impact_color = "🔴" if impact < -30 else "🟡" if impact < -10 else "🟢"
        
        print(f"  {impact_color} {scenario_name}:")
        print(f"    • Impact: {impact:+.1f}%")
        print(f"    • New Value: ${result['stressed_value']:,.2f}")
        print(f"    • Loss: ${abs(result['absolute_impact']):,.2f}")
    
    # Find worst case scenario
    worst_scenario = min(stress_results.items(), key=lambda x: x[1]['percentage_impact'])
    print(f"\n⚠️  WORST CASE SCENARIO: {worst_scenario[0]}")
    print(f"   • Potential Loss: {worst_scenario[1]['percentage_impact']:.1f}%")
    print(f"   • Dollar Impact: ${abs(worst_scenario[1]['absolute_impact']):,.2f}")


async def demo_custom_risk_limits():
    """Demonstrate custom risk limits."""
    print(f"\n⚙️ CUSTOM RISK LIMITS DEMO")
    print("=" * 50)
    
    # Create conservative risk manager
    risk_manager = create_conservative_risk_manager()
    
    # Add custom risk limits
    custom_limits = [
        RiskLimit(
            limit_id="crypto_concentration",
            limit_type=LimitType.CONCENTRATION_LIMIT,
            description="Maximum crypto concentration per asset",
            threshold_value=Decimal("30000"),
            threshold_percentage=20.0,  # Max 20% in any single crypto
            applies_to="crypto_assets"
        ),
        RiskLimit(
            limit_id="high_risk_assets",
            limit_type=LimitType.POSITION_LIMIT,
            description="Limit on high-risk altcoins",
            threshold_value=Decimal("15000"),
            threshold_percentage=10.0,  # Max 10% in high-risk assets
            applies_to="altcoins"
        )
    ]
    
    for limit in custom_limits:
        risk_manager.add_risk_limit(limit)
        print(f"✅ Added custom limit: {limit.description}")
    
    # Test with portfolio
    portfolio = create_demo_portfolio()
    historical_returns = generate_realistic_returns(100)
    
    dashboard = await risk_manager.assess_portfolio_risk(portfolio, historical_returns)
    
    print(f"\n📊 CUSTOM LIMITS COMPLIANCE:")
    print(f"  • Total Limits: {dashboard.compliance_report.total_limits}")
    print(f"  • Status: {dashboard.compliance_report.compliance_status.value.upper()}")
    
    print(f"\n📈 LIMIT UTILIZATION:")
    for limit_id, utilization in dashboard.compliance_report.limit_utilization.items():
        status = "🔴" if utilization > 90 else "🟡" if utilization > 70 else "🟢"
        print(f"  {status} {limit_id}: {utilization:.1f}%")


async def demo_risk_monitoring():
    """Demonstrate continuous risk monitoring."""
    print(f"\n📡 RISK MONITORING DEMO")
    print("=" * 50)
    
    risk_manager = create_basic_risk_manager()
    portfolio = create_demo_portfolio()
    
    # Add risk event handler
    def risk_alert_handler(dashboard):
        if dashboard.risk_score > 70:
            print(f"🚨 HIGH RISK ALERT: Risk score {dashboard.risk_score:.1f}/100")
        if dashboard.compliance_report.violated_limits > 0:
            print(f"⚠️  COMPLIANCE ALERT: {dashboard.compliance_report.violated_limits} violations")
    
    risk_manager.add_risk_handler(risk_alert_handler)
    print("✅ Risk monitoring handler added")
    
    # Simulate monitoring over time
    print(f"\n📊 Simulating Risk Monitoring...")
    
    for day in range(1, 4):  # Simulate 3 days
        print(f"\n--- Day {day} ---")
        
        # Generate new returns (simulate market changes)
        daily_returns = generate_realistic_returns(30)
        
        # Assess risk
        dashboard = await risk_manager.assess_portfolio_risk(portfolio, daily_returns)
        
        print(f"Risk Score: {dashboard.risk_score:.1f} ({risk_manager._get_risk_level(dashboard.risk_score)})")
        print(f"VaR: ${dashboard.risk_metrics.var_95:,.2f}")
        print(f"Compliance: {dashboard.compliance_report.compliance_status.value}")


async def demo_risk_reporting():
    """Demonstrate risk reporting."""
    print(f"\n📋 RISK REPORTING DEMO")
    print("=" * 50)
    
    risk_manager = create_basic_risk_manager()
    portfolio = create_demo_portfolio()
    historical_returns = generate_realistic_returns(252)
    
    # Generate comprehensive risk assessment
    dashboard = await risk_manager.assess_portfolio_risk(portfolio, historical_returns)
    
    # Generate formatted report
    risk_report = risk_manager.generate_risk_report(dashboard)
    
    print("📄 GENERATED RISK REPORT:")
    print("-" * 50)
    print(risk_report)
    print("-" * 50)
    
    # Generate risk summary for API/dashboard
    risk_summary = risk_manager.get_risk_summary(dashboard)
    
    print(f"\n📊 RISK SUMMARY (API Format):")
    for key, value in risk_summary.items():
        print(f"  • {key}: {value}")


async def main():
    """Main demo function."""
    print("🚀 Feature 8: Advanced Risk Management and Compliance - DEMO")
    print("=" * 70)
    print("This demo shows practical usage of the risk management system.")
    print()
    
    try:
        # Run all demos
        await demo_basic_risk_assessment()
        await demo_stress_testing()
        await demo_custom_risk_limits()
        await demo_risk_monitoring()
        await demo_risk_reporting()
        
        print(f"\n🎉 DEMO COMPLETED SUCCESSFULLY!")
        print(f"\n💡 Key Features Demonstrated:")
        print(f"  ✅ Comprehensive Risk Assessment (VaR, CVaR, Volatility)")
        print(f"  ✅ Stress Testing with Multiple Scenarios")
        print(f"  ✅ Compliance Monitoring with Custom Limits")
        print(f"  ✅ Real-time Risk Monitoring and Alerts")
        print(f"  ✅ Professional Risk Reporting")
        
        print(f"\n🔧 Ready for Production Use:")
        print(f"  • Integrate with live portfolio data")
        print(f"  • Configure organization-specific risk limits")
        print(f"  • Set up automated compliance reporting")
        print(f"  • Implement risk alerts and notifications")
        
    except Exception as e:
        print(f"❌ Demo failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    exit(asyncio.run(main()))
