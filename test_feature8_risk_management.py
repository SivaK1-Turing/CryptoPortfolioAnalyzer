#!/usr/bin/env python3
"""
Comprehensive test suite for Feature 8: Advanced Risk Management and Compliance.
This script tests all components of the risk management system.
"""

import sys
import asyncio
import numpy as np
from pathlib import Path
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import List, Dict, Any

# Add the project root to Python path
sys.path.insert(0, str(Path(__file__).parent))

from crypto_portfolio_analyzer.risk import (
    RiskAssessmentEngine, RiskMetrics, StressTestScenario,
    ComplianceMonitor, RiskLimit, LimitType, ComplianceStatus,
    RiskManager, create_basic_risk_manager, create_conservative_risk_manager
)
from crypto_portfolio_analyzer.analytics.models import PortfolioHolding


def create_sample_portfolio() -> List[PortfolioHolding]:
    """Create sample portfolio for testing."""
    return [
        PortfolioHolding(
            symbol="BTC",
            quantity=Decimal("2.0"),
            average_cost=Decimal("45000"),
            current_price=Decimal("52000")
        ),
        PortfolioHolding(
            symbol="ETH",
            quantity=Decimal("15.0"),
            average_cost=Decimal("3000"),
            current_price=Decimal("3800")
        ),
        PortfolioHolding(
            symbol="SOL",
            quantity=Decimal("100.0"),
            average_cost=Decimal("80"),
            current_price=Decimal("110")
        ),
        PortfolioHolding(
            symbol="ADA",
            quantity=Decimal("5000.0"),
            average_cost=Decimal("1.0"),
            current_price=Decimal("1.3")
        )
    ]


def generate_sample_returns(days: int = 100, volatility: float = 0.02) -> List[float]:
    """Generate sample portfolio returns for testing."""
    np.random.seed(42)  # For reproducible results
    returns = np.random.normal(0.001, volatility, days)  # 0.1% daily return, 2% volatility
    return returns.tolist()


def test_risk_assessment_engine():
    """Test the risk assessment engine."""
    print("\n📊 Testing Risk Assessment Engine...")
    
    try:
        engine = RiskAssessmentEngine(lookback_days=252)
        print("✅ Risk assessment engine created")
        
        # Generate test data
        portfolio_returns = generate_sample_returns(100, 0.025)
        portfolio_value = Decimal("200000")  # $200k portfolio
        benchmark_returns = generate_sample_returns(100, 0.020)
        
        print(f"✅ Generated {len(portfolio_returns)} days of return data")
        
        # Calculate risk metrics
        risk_metrics = engine.calculate_portfolio_risk(
            portfolio_returns, portfolio_value, benchmark_returns
        )
        
        print("✅ Risk metrics calculated successfully")
        print(f"📊 Risk Metrics Summary:")
        print(f"  • Portfolio Value: ${risk_metrics.portfolio_value:,.2f}")
        print(f"  • VaR (95%): ${risk_metrics.var_95:,.2f}")
        print(f"  • VaR (99%): ${risk_metrics.var_99:,.2f}")
        print(f"  • CVaR (95%): ${risk_metrics.cvar_95:,.2f}")
        print(f"  • Volatility (Annual): {risk_metrics.volatility_annualized:.1%}")
        print(f"  • Max Drawdown: {float(risk_metrics.max_drawdown):.1%}")
        print(f"  • Sharpe Ratio: {risk_metrics.sharpe_ratio:.2f}")
        print(f"  • Beta: {risk_metrics.beta:.2f}")
        
        # Test serialization
        risk_dict = risk_metrics.to_dict()
        print(f"✅ Risk metrics serialization: {len(risk_dict)} fields")
        
        return True
        
    except Exception as e:
        print(f"❌ Risk assessment engine test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_stress_testing():
    """Test stress testing functionality."""
    print("\n🧪 Testing Stress Testing...")
    
    try:
        engine = RiskAssessmentEngine()
        holdings = create_sample_portfolio()
        
        # Create portfolio positions
        portfolio_positions = {
            h.symbol: (h.quantity, h.current_price) for h in holdings
        }
        
        print(f"✅ Created portfolio with {len(portfolio_positions)} positions")
        
        # Create custom stress scenario
        custom_scenario = StressTestScenario(
            name="test_crash",
            description="Test market crash scenario",
            price_shocks={
                "BTC": -0.50,  # -50%
                "ETH": -0.60,  # -60%
                "SOL": -0.70,  # -70%
                "ADA": -0.65   # -65%
            }
        )
        
        # Run stress test
        stress_results = engine.run_stress_test(portfolio_positions, [custom_scenario])
        
        print("✅ Stress test completed")
        print(f"📊 Stress Test Results:")
        
        for scenario_name, result in stress_results.items():
            print(f"  • {scenario_name}:")
            print(f"    - Current Value: ${result['current_value']:,.2f}")
            print(f"    - Stressed Value: ${result['stressed_value']:,.2f}")
            print(f"    - Impact: {result['percentage_impact']:+.1f}%")
        
        return True
        
    except Exception as e:
        print(f"❌ Stress testing failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_compliance_monitoring():
    """Test compliance monitoring system."""
    print("\n🔍 Testing Compliance Monitoring...")
    
    try:
        monitor = ComplianceMonitor()
        print("✅ Compliance monitor created")
        
        # Check default limits
        default_limits = len(monitor.risk_limits)
        print(f"✅ Default risk limits loaded: {default_limits}")
        
        # Add custom risk limit
        custom_limit = RiskLimit(
            limit_id="test_position_limit",
            limit_type=LimitType.POSITION_LIMIT,
            description="Test position size limit",
            threshold_value=Decimal("50000"),
            threshold_percentage=25.0
        )
        
        monitor.add_risk_limit(custom_limit)
        print("✅ Custom risk limit added")
        
        # Create test portfolio
        holdings = create_sample_portfolio()
        portfolio_value = sum(h.market_value for h in holdings)
        portfolio_positions = {
            h.symbol: (h.quantity, h.current_price) for h in holdings
        }
        
        print(f"✅ Test portfolio created: ${portfolio_value:,.2f}")
        
        # Run compliance check
        compliance_report = monitor.check_compliance(
            portfolio_positions, portfolio_value
        )
        
        print("✅ Compliance check completed")
        print(f"📊 Compliance Report:")
        print(f"  • Status: {compliance_report.compliance_status.value.upper()}")
        print(f"  • Total Limits: {compliance_report.total_limits}")
        print(f"  • Violations: {compliance_report.violated_limits}")
        print(f"  • Warnings: {compliance_report.warning_limits}")
        
        # Show limit utilization
        print(f"  • Limit Utilization:")
        for limit_id, utilization in compliance_report.limit_utilization.items():
            print(f"    - {limit_id}: {utilization:.1f}%")
        
        # Show violations if any
        if compliance_report.violations:
            print(f"  • Violations:")
            for violation in compliance_report.violations:
                print(f"    - {violation.description}")
        
        return True
        
    except Exception as e:
        print(f"❌ Compliance monitoring test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_position_risk_analysis():
    """Test individual position risk analysis."""
    print("\n📈 Testing Position Risk Analysis...")
    
    try:
        engine = RiskAssessmentEngine()
        holdings = create_sample_portfolio()
        
        print(f"✅ Analyzing {len(holdings)} positions")
        
        position_risks = {}
        for holding in holdings:
            # Generate sample returns for this position
            position_returns = generate_sample_returns(60, 0.03)  # 60 days, 3% volatility
            
            position_risk = engine.calculate_position_risk(
                holding.symbol,
                holding.quantity,
                holding.current_price,
                position_returns
            )
            
            position_risks[holding.symbol] = position_risk
            
            print(f"📊 {holding.symbol} Risk Analysis:")
            print(f"  • Position Value: ${position_risk['position_value']:,.2f}")
            print(f"  • VaR (95%): ${position_risk['var_95']:,.2f}")
            print(f"  • VaR (99%): ${position_risk['var_99']:,.2f}")
            print(f"  • Volatility: {position_risk['volatility_annualized']:.1%}")
            print(f"  • Max Drawdown: {position_risk['max_drawdown']:.1%}")
        
        print("✅ Position risk analysis completed")
        return True
        
    except Exception as e:
        print(f"❌ Position risk analysis failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_integrated_risk_manager():
    """Test the integrated risk management system."""
    print("\n🎛️ Testing Integrated Risk Manager...")
    
    try:
        # Create risk manager
        risk_manager = create_basic_risk_manager()
        print("✅ Risk manager created")
        
        # Create test data
        holdings = create_sample_portfolio()
        historical_returns = generate_sample_returns(100, 0.025)
        benchmark_returns = generate_sample_returns(100, 0.020)
        
        print(f"✅ Test data prepared: {len(holdings)} holdings, {len(historical_returns)} return observations")
        
        # Perform comprehensive risk assessment
        dashboard = await risk_manager.assess_portfolio_risk(
            holdings, historical_returns, benchmark_returns
        )
        
        print("✅ Comprehensive risk assessment completed")
        print(f"📊 Risk Dashboard Summary:")
        print(f"  • Portfolio Value: ${dashboard.portfolio_value:,.2f}")
        print(f"  • Risk Score: {dashboard.risk_score:.1f}/100")
        print(f"  • Risk Level: {risk_manager._get_risk_level(dashboard.risk_score)}")
        print(f"  • Compliance Status: {dashboard.compliance_report.compliance_status.value.upper()}")
        print(f"  • Recommendations: {len(dashboard.recommendations)}")
        
        # Show top recommendations
        if dashboard.recommendations:
            print(f"  • Top Recommendations:")
            for i, rec in enumerate(dashboard.recommendations[:3], 1):
                print(f"    {i}. {rec}")
        
        # Test risk summary
        risk_summary = risk_manager.get_risk_summary(dashboard)
        print(f"✅ Risk summary generated: {len(risk_summary)} metrics")
        
        # Test risk report generation
        risk_report = risk_manager.generate_risk_report(dashboard)
        print(f"✅ Risk report generated: {len(risk_report)} characters")
        
        return True
        
    except Exception as e:
        print(f"❌ Integrated risk manager test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_conservative_risk_manager():
    """Test conservative risk manager configuration."""
    print("\n🛡️ Testing Conservative Risk Manager...")
    
    try:
        # Create conservative risk manager
        conservative_manager = create_conservative_risk_manager()
        print("✅ Conservative risk manager created")
        
        # Check that conservative limits are applied
        compliance_monitor = conservative_manager.compliance_monitor
        conservative_limits = [
            limit for limit in compliance_monitor.risk_limits.values()
            if "conservative" in limit.limit_id
        ]
        
        print(f"✅ Conservative limits applied: {len(conservative_limits)}")
        
        # Check risk thresholds
        thresholds = conservative_manager.risk_thresholds
        print(f"📊 Conservative Risk Thresholds:")
        for threshold_name, value in thresholds.items():
            print(f"  • {threshold_name}: {value:.1%}")
        
        return True
        
    except Exception as e:
        print(f"❌ Conservative risk manager test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_risk_serialization():
    """Test risk data serialization."""
    print("\n💾 Testing Risk Data Serialization...")
    
    try:
        # Test risk metrics serialization
        engine = RiskAssessmentEngine()
        returns = generate_sample_returns(50, 0.02)
        portfolio_value = Decimal("150000")
        
        risk_metrics = engine.calculate_portfolio_risk(returns, portfolio_value)
        risk_dict = risk_metrics.to_dict()
        
        print(f"✅ Risk metrics serialized: {len(risk_dict)} fields")
        
        # Test compliance report serialization
        monitor = ComplianceMonitor()
        holdings = create_sample_portfolio()
        portfolio_positions = {h.symbol: (h.quantity, h.current_price) for h in holdings}
        portfolio_value = sum(h.market_value for h in holdings)
        
        compliance_report = monitor.check_compliance(portfolio_positions, portfolio_value)
        compliance_dict = compliance_report.to_dict()
        
        print(f"✅ Compliance report serialized: {len(compliance_dict)} fields")
        
        # Test risk limit serialization
        test_limit = RiskLimit(
            limit_id="test_serialization",
            limit_type=LimitType.VAR_LIMIT,
            description="Test limit for serialization",
            threshold_value=Decimal("10000")
        )
        
        limit_dict = test_limit.to_dict()
        print(f"✅ Risk limit serialized: {len(limit_dict)} fields")
        
        return True
        
    except Exception as e:
        print(f"❌ Risk serialization test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Main test function."""
    print("🚀 Testing Feature 8: Advanced Risk Management and Compliance")
    print("=" * 70)
    
    # Run all tests
    test_functions = [
        ("Risk Assessment Engine", test_risk_assessment_engine),
        ("Stress Testing", test_stress_testing),
        ("Compliance Monitoring", test_compliance_monitoring),
        ("Position Risk Analysis", test_position_risk_analysis),
        ("Integrated Risk Manager", test_integrated_risk_manager),
        ("Conservative Risk Manager", test_conservative_risk_manager),
        ("Risk Data Serialization", test_risk_serialization)
    ]
    
    results = []
    
    for test_name, test_func in test_functions:
        print(f"\n{'='*20} {test_name} {'='*20}")
        try:
            if asyncio.iscoroutinefunction(test_func):
                result = await test_func()
            else:
                result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name} failed with exception: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "=" * 70)
    print("📊 TEST SUMMARY")
    print("=" * 70)
    
    passed = 0
    for i, (test_name, result) in enumerate(results):
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{i+1}. {test_name}: {status}")
        if result:
            passed += 1
    
    total = len(results)
    print(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All risk management features are working!")
        print("\n🔧 Feature 8 Components Tested:")
        print("  ✅ Risk Assessment Engine (VaR, CVaR, Volatility)")
        print("  ✅ Stress Testing Framework")
        print("  ✅ Compliance Monitoring System")
        print("  ✅ Position-level Risk Analysis")
        print("  ✅ Integrated Risk Management")
        print("  ✅ Conservative Risk Profiles")
        print("  ✅ Risk Data Serialization")
        
        print("\n💡 Next Steps:")
        print("  • Integrate with live portfolio data")
        print("  • Configure custom risk limits")
        print("  • Set up automated compliance reporting")
        print("  • Implement risk alerts and notifications")
        print("  • Add regulatory reporting templates")
    else:
        print(f"\n⚠️  {total - passed} tests failed. Check the error messages above.")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(asyncio.run(main()))
