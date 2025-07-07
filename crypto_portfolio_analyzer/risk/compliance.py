"""Compliance monitoring and regulatory reporting system."""

from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timezone, timedelta
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)


class ComplianceStatus(Enum):
    """Compliance status levels."""
    COMPLIANT = "compliant"
    WARNING = "warning"
    VIOLATION = "violation"
    UNKNOWN = "unknown"


class RegulatoryFramework(Enum):
    """Regulatory frameworks."""
    MiFID_II = "mifid_ii"
    SEC_US = "sec_us"
    FCA_UK = "fca_uk"
    ESMA_EU = "esma_eu"
    CFTC_US = "cftc_us"
    CUSTOM = "custom"


class LimitType(Enum):
    """Types of risk limits."""
    POSITION_LIMIT = "position_limit"
    CONCENTRATION_LIMIT = "concentration_limit"
    VAR_LIMIT = "var_limit"
    LEVERAGE_LIMIT = "leverage_limit"
    EXPOSURE_LIMIT = "exposure_limit"
    SECTOR_LIMIT = "sector_limit"


@dataclass
class RiskLimit:
    """Risk limit definition."""
    limit_id: str
    limit_type: LimitType
    description: str
    threshold_value: Decimal
    threshold_percentage: Optional[float] = None
    currency: str = "USD"
    applies_to: Optional[str] = None  # Symbol, sector, or "portfolio"
    regulatory_framework: Optional[RegulatoryFramework] = None
    enabled: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "limit_id": self.limit_id,
            "limit_type": self.limit_type.value,
            "description": self.description,
            "threshold_value": float(self.threshold_value),
            "threshold_percentage": self.threshold_percentage,
            "currency": self.currency,
            "applies_to": self.applies_to,
            "regulatory_framework": self.regulatory_framework.value if self.regulatory_framework else None,
            "enabled": self.enabled,
            "created_at": self.created_at.isoformat()
        }


@dataclass
class ComplianceViolation:
    """Compliance violation record."""
    violation_id: str
    limit_id: str
    violation_type: LimitType
    current_value: Decimal
    limit_value: Decimal
    excess_amount: Decimal
    excess_percentage: float
    severity: ComplianceStatus
    description: str
    detected_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    resolved_at: Optional[datetime] = None
    resolution_notes: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "violation_id": self.violation_id,
            "limit_id": self.limit_id,
            "violation_type": self.violation_type.value,
            "current_value": float(self.current_value),
            "limit_value": float(self.limit_value),
            "excess_amount": float(self.excess_amount),
            "excess_percentage": self.excess_percentage,
            "severity": self.severity.value,
            "description": self.description,
            "detected_at": self.detected_at.isoformat(),
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "resolution_notes": self.resolution_notes
        }


@dataclass
class ComplianceReport:
    """Compliance monitoring report."""
    report_id: str
    generated_at: datetime
    portfolio_value: Decimal
    compliance_status: ComplianceStatus
    total_limits: int
    violated_limits: int
    warning_limits: int
    violations: List[ComplianceViolation] = field(default_factory=list)
    limit_utilization: Dict[str, float] = field(default_factory=dict)
    regulatory_summary: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "report_id": self.report_id,
            "generated_at": self.generated_at.isoformat(),
            "portfolio_value": float(self.portfolio_value),
            "compliance_status": self.compliance_status.value,
            "total_limits": self.total_limits,
            "violated_limits": self.violated_limits,
            "warning_limits": self.warning_limits,
            "violations": [v.to_dict() for v in self.violations],
            "limit_utilization": self.limit_utilization,
            "regulatory_summary": self.regulatory_summary
        }


class ComplianceMonitor:
    """Compliance monitoring and risk limits management system."""
    
    def __init__(self):
        """Initialize compliance monitor."""
        self.risk_limits: Dict[str, RiskLimit] = {}
        self.violations: List[ComplianceViolation] = []
        self.violation_handlers: List[callable] = []
        
        # Setup default limits
        self._setup_default_limits()
    
    def _setup_default_limits(self):
        """Setup default risk limits."""
        default_limits = [
            RiskLimit(
                limit_id="max_position_size",
                limit_type=LimitType.POSITION_LIMIT,
                description="Maximum position size per asset",
                threshold_value=Decimal("50000"),  # $50k per position
                threshold_percentage=20.0,  # 20% of portfolio
                applies_to="per_asset"
            ),
            RiskLimit(
                limit_id="portfolio_concentration",
                limit_type=LimitType.CONCENTRATION_LIMIT,
                description="Maximum concentration in single asset",
                threshold_value=Decimal("100000"),
                threshold_percentage=40.0,  # 40% max in single asset
                applies_to="portfolio"
            ),
            RiskLimit(
                limit_id="daily_var_limit",
                limit_type=LimitType.VAR_LIMIT,
                description="Daily Value at Risk limit (95% confidence)",
                threshold_value=Decimal("10000"),  # $10k daily VaR
                threshold_percentage=5.0,  # 5% of portfolio
                applies_to="portfolio"
            ),
            RiskLimit(
                limit_id="total_exposure",
                limit_type=LimitType.EXPOSURE_LIMIT,
                description="Total portfolio exposure limit",
                threshold_value=Decimal("500000"),  # $500k total exposure
                applies_to="portfolio"
            )
        ]
        
        for limit in default_limits:
            self.risk_limits[limit.limit_id] = limit
    
    def add_risk_limit(self, limit: RiskLimit):
        """Add new risk limit."""
        self.risk_limits[limit.limit_id] = limit
        logger.info(f"Added risk limit: {limit.limit_id}")
    
    def remove_risk_limit(self, limit_id: str):
        """Remove risk limit."""
        if limit_id in self.risk_limits:
            del self.risk_limits[limit_id]
            logger.info(f"Removed risk limit: {limit_id}")
    
    def update_risk_limit(self, limit_id: str, **kwargs):
        """Update existing risk limit."""
        if limit_id in self.risk_limits:
            limit = self.risk_limits[limit_id]
            for key, value in kwargs.items():
                if hasattr(limit, key):
                    setattr(limit, key, value)
            logger.info(f"Updated risk limit: {limit_id}")
    
    def check_compliance(
        self,
        portfolio_positions: Dict[str, Tuple[Decimal, Decimal]],  # symbol -> (quantity, price)
        portfolio_value: Decimal,
        risk_metrics: Optional[Dict[str, Any]] = None
    ) -> ComplianceReport:
        """Check portfolio compliance against all risk limits.
        
        Args:
            portfolio_positions: Current portfolio positions
            portfolio_value: Total portfolio value
            risk_metrics: Optional risk metrics (VaR, etc.)
            
        Returns:
            ComplianceReport with compliance status and violations
        """
        violations = []
        limit_utilization = {}
        overall_status = ComplianceStatus.COMPLIANT
        
        for limit_id, limit in self.risk_limits.items():
            if not limit.enabled:
                continue
            
            violation = self._check_limit(limit, portfolio_positions, portfolio_value, risk_metrics)
            
            # Calculate utilization
            if limit.limit_type == LimitType.POSITION_LIMIT:
                utilization = self._calculate_position_utilization(limit, portfolio_positions, portfolio_value)
            elif limit.limit_type == LimitType.CONCENTRATION_LIMIT:
                utilization = self._calculate_concentration_utilization(limit, portfolio_positions, portfolio_value)
            elif limit.limit_type == LimitType.VAR_LIMIT:
                utilization = self._calculate_var_utilization(limit, risk_metrics)
            elif limit.limit_type == LimitType.EXPOSURE_LIMIT:
                utilization = float(portfolio_value / limit.threshold_value * 100)
            else:
                utilization = 0.0
            
            limit_utilization[limit_id] = min(utilization, 100.0)
            
            if violation:
                violations.append(violation)
                if violation.severity == ComplianceStatus.VIOLATION:
                    overall_status = ComplianceStatus.VIOLATION
                elif violation.severity == ComplianceStatus.WARNING and overall_status == ComplianceStatus.COMPLIANT:
                    overall_status = ComplianceStatus.WARNING
        
        # Count violations by severity
        violated_limits = len([v for v in violations if v.severity == ComplianceStatus.VIOLATION])
        warning_limits = len([v for v in violations if v.severity == ComplianceStatus.WARNING])
        
        # Create regulatory summary
        regulatory_summary = self._create_regulatory_summary(violations, portfolio_value)
        
        report = ComplianceReport(
            report_id=f"compliance_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}",
            generated_at=datetime.now(timezone.utc),
            portfolio_value=portfolio_value,
            compliance_status=overall_status,
            total_limits=len(self.risk_limits),
            violated_limits=violated_limits,
            warning_limits=warning_limits,
            violations=violations,
            limit_utilization=limit_utilization,
            regulatory_summary=regulatory_summary
        )
        
        # Store violations
        self.violations.extend(violations)
        
        # Notify handlers
        for handler in self.violation_handlers:
            try:
                handler(report)
            except Exception as e:
                logger.error(f"Error in violation handler: {e}")
        
        return report
    
    def _check_limit(
        self,
        limit: RiskLimit,
        portfolio_positions: Dict[str, Tuple[Decimal, Decimal]],
        portfolio_value: Decimal,
        risk_metrics: Optional[Dict[str, Any]]
    ) -> Optional[ComplianceViolation]:
        """Check individual limit compliance."""
        
        if limit.limit_type == LimitType.POSITION_LIMIT:
            return self._check_position_limit(limit, portfolio_positions, portfolio_value)
        elif limit.limit_type == LimitType.CONCENTRATION_LIMIT:
            return self._check_concentration_limit(limit, portfolio_positions, portfolio_value)
        elif limit.limit_type == LimitType.VAR_LIMIT:
            return self._check_var_limit(limit, risk_metrics)
        elif limit.limit_type == LimitType.EXPOSURE_LIMIT:
            return self._check_exposure_limit(limit, portfolio_value)
        
        return None
    
    def _check_position_limit(
        self,
        limit: RiskLimit,
        portfolio_positions: Dict[str, Tuple[Decimal, Decimal]],
        portfolio_value: Decimal
    ) -> Optional[ComplianceViolation]:
        """Check position size limits."""
        for symbol, (quantity, price) in portfolio_positions.items():
            position_value = quantity * price
            
            # Check absolute limit
            if position_value > limit.threshold_value:
                excess = position_value - limit.threshold_value
                excess_pct = float(excess / limit.threshold_value * 100)
                
                return ComplianceViolation(
                    violation_id=f"pos_{symbol}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}",
                    limit_id=limit.limit_id,
                    violation_type=limit.limit_type,
                    current_value=position_value,
                    limit_value=limit.threshold_value,
                    excess_amount=excess,
                    excess_percentage=excess_pct,
                    severity=ComplianceStatus.VIOLATION if excess_pct > 20 else ComplianceStatus.WARNING,
                    description=f"Position {symbol} exceeds limit: ${position_value:,.2f} > ${limit.threshold_value:,.2f}"
                )
            
            # Check percentage limit
            if limit.threshold_percentage:
                position_pct = float(position_value / portfolio_value * 100)
                if position_pct > limit.threshold_percentage:
                    excess_pct = position_pct - limit.threshold_percentage
                    
                    return ComplianceViolation(
                        violation_id=f"pos_pct_{symbol}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}",
                        limit_id=limit.limit_id,
                        violation_type=limit.limit_type,
                        current_value=Decimal(str(position_pct)),
                        limit_value=Decimal(str(limit.threshold_percentage)),
                        excess_amount=Decimal(str(excess_pct)),
                        excess_percentage=excess_pct,
                        severity=ComplianceStatus.VIOLATION if excess_pct > 5 else ComplianceStatus.WARNING,
                        description=f"Position {symbol} concentration exceeds limit: {position_pct:.1f}% > {limit.threshold_percentage:.1f}%"
                    )
        
        return None
    
    def _check_concentration_limit(
        self,
        limit: RiskLimit,
        portfolio_positions: Dict[str, Tuple[Decimal, Decimal]],
        portfolio_value: Decimal
    ) -> Optional[ComplianceViolation]:
        """Check concentration limits."""
        # Find largest position
        max_position_value = Decimal('0')
        max_symbol = ""
        
        for symbol, (quantity, price) in portfolio_positions.items():
            position_value = quantity * price
            if position_value > max_position_value:
                max_position_value = position_value
                max_symbol = symbol
        
        if max_position_value > 0:
            concentration_pct = float(max_position_value / portfolio_value * 100)
            
            if limit.threshold_percentage and concentration_pct > limit.threshold_percentage:
                excess_pct = concentration_pct - limit.threshold_percentage
                
                return ComplianceViolation(
                    violation_id=f"conc_{max_symbol}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}",
                    limit_id=limit.limit_id,
                    violation_type=limit.limit_type,
                    current_value=Decimal(str(concentration_pct)),
                    limit_value=Decimal(str(limit.threshold_percentage)),
                    excess_amount=Decimal(str(excess_pct)),
                    excess_percentage=excess_pct,
                    severity=ComplianceStatus.VIOLATION if excess_pct > 10 else ComplianceStatus.WARNING,
                    description=f"Portfolio concentration in {max_symbol} exceeds limit: {concentration_pct:.1f}% > {limit.threshold_percentage:.1f}%"
                )
        
        return None
    
    def _check_var_limit(self, limit: RiskLimit, risk_metrics: Optional[Dict[str, Any]]) -> Optional[ComplianceViolation]:
        """Check VaR limits."""
        if not risk_metrics or 'var_95' not in risk_metrics:
            return None
        
        current_var = Decimal(str(risk_metrics['var_95']))
        
        if current_var > limit.threshold_value:
            excess = current_var - limit.threshold_value
            excess_pct = float(excess / limit.threshold_value * 100)
            
            return ComplianceViolation(
                violation_id=f"var_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}",
                limit_id=limit.limit_id,
                violation_type=limit.limit_type,
                current_value=current_var,
                limit_value=limit.threshold_value,
                excess_amount=excess,
                excess_percentage=excess_pct,
                severity=ComplianceStatus.VIOLATION if excess_pct > 25 else ComplianceStatus.WARNING,
                description=f"Daily VaR exceeds limit: ${current_var:,.2f} > ${limit.threshold_value:,.2f}"
            )
        
        return None
    
    def _check_exposure_limit(self, limit: RiskLimit, portfolio_value: Decimal) -> Optional[ComplianceViolation]:
        """Check total exposure limits."""
        if portfolio_value > limit.threshold_value:
            excess = portfolio_value - limit.threshold_value
            excess_pct = float(excess / limit.threshold_value * 100)
            
            return ComplianceViolation(
                violation_id=f"exp_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}",
                limit_id=limit.limit_id,
                violation_type=limit.limit_type,
                current_value=portfolio_value,
                limit_value=limit.threshold_value,
                excess_amount=excess,
                excess_percentage=excess_pct,
                severity=ComplianceStatus.VIOLATION if excess_pct > 15 else ComplianceStatus.WARNING,
                description=f"Total exposure exceeds limit: ${portfolio_value:,.2f} > ${limit.threshold_value:,.2f}"
            )
        
        return None
    
    def _calculate_position_utilization(
        self,
        limit: RiskLimit,
        portfolio_positions: Dict[str, Tuple[Decimal, Decimal]],
        portfolio_value: Decimal
    ) -> float:
        """Calculate position limit utilization."""
        max_utilization = 0.0
        
        for symbol, (quantity, price) in portfolio_positions.items():
            position_value = quantity * price
            utilization = float(position_value / limit.threshold_value * 100)
            max_utilization = max(max_utilization, utilization)
        
        return max_utilization
    
    def _calculate_concentration_utilization(
        self,
        limit: RiskLimit,
        portfolio_positions: Dict[str, Tuple[Decimal, Decimal]],
        portfolio_value: Decimal
    ) -> float:
        """Calculate concentration limit utilization."""
        if not limit.threshold_percentage:
            return 0.0
        
        max_position_value = max(
            (quantity * price for quantity, price in portfolio_positions.values()),
            default=Decimal('0')
        )
        
        concentration_pct = float(max_position_value / portfolio_value * 100) if portfolio_value > 0 else 0
        return concentration_pct / limit.threshold_percentage * 100
    
    def _calculate_var_utilization(self, limit: RiskLimit, risk_metrics: Optional[Dict[str, Any]]) -> float:
        """Calculate VaR limit utilization."""
        if not risk_metrics or 'var_95' not in risk_metrics:
            return 0.0
        
        current_var = risk_metrics['var_95']
        return float(current_var / float(limit.threshold_value) * 100)
    
    def _create_regulatory_summary(self, violations: List[ComplianceViolation], portfolio_value: Decimal) -> Dict[str, Any]:
        """Create regulatory compliance summary."""
        return {
            "total_violations": len(violations),
            "critical_violations": len([v for v in violations if v.severity == ComplianceStatus.VIOLATION]),
            "warning_violations": len([v for v in violations if v.severity == ComplianceStatus.WARNING]),
            "portfolio_value": float(portfolio_value),
            "compliance_score": max(0, 100 - len(violations) * 10),  # Simple scoring
            "last_assessment": datetime.now(timezone.utc).isoformat(),
            "regulatory_frameworks": ["SEC_US", "MiFID_II"],  # Example frameworks
            "next_review_date": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
        }
    
    def add_violation_handler(self, handler: callable):
        """Add violation event handler."""
        self.violation_handlers.append(handler)
    
    def get_compliance_history(self, days: int = 30) -> List[ComplianceViolation]:
        """Get compliance violation history."""
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
        return [v for v in self.violations if v.detected_at >= cutoff_date]
    
    def resolve_violation(self, violation_id: str, resolution_notes: str):
        """Mark violation as resolved."""
        for violation in self.violations:
            if violation.violation_id == violation_id:
                violation.resolved_at = datetime.now(timezone.utc)
                violation.resolution_notes = resolution_notes
                logger.info(f"Resolved violation: {violation_id}")
                break
