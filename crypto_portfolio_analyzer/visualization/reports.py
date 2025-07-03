"""Report generation system for portfolio analysis."""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Union
from enum import Enum
from dataclasses import dataclass, field
from pathlib import Path
import json
import base64
from io import BytesIO
import jinja2
import weasyprint
import plotly.graph_objects as go
from plotly.offline import plot

from .charts import ChartGenerator, ChartConfig, ChartType
from ..analytics.models import PortfolioSnapshot, PerformanceMetrics

logger = logging.getLogger(__name__)


class ReportType(Enum):
    """Report type enumeration."""
    PORTFOLIO_SUMMARY = "portfolio_summary"
    PERFORMANCE_ANALYSIS = "performance_analysis"
    RISK_ASSESSMENT = "risk_assessment"
    ALLOCATION_REPORT = "allocation_report"
    CUSTOM = "custom"


class ReportFormat(Enum):
    """Report format enumeration."""
    HTML = "html"
    PDF = "pdf"
    JSON = "json"


@dataclass
class ReportConfig:
    """Report configuration settings."""
    report_type: ReportType
    format: ReportFormat = ReportFormat.HTML
    title: str = ""
    include_charts: bool = True
    include_tables: bool = True
    include_summary: bool = True
    date_range: Optional[tuple] = None
    custom_template: Optional[str] = None
    output_path: Optional[str] = None
    theme: str = "default"
    logo_path: Optional[str] = None


@dataclass
class ReportData:
    """Report data container."""
    portfolio_snapshots: List[PortfolioSnapshot] = field(default_factory=list)
    performance_metrics: Optional[PerformanceMetrics] = None
    charts: Dict[str, go.Figure] = field(default_factory=dict)
    tables: Dict[str, List[Dict[str, Any]]] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class ReportTemplate:
    """Report template manager."""
    
    def __init__(self, template_dir: Optional[str] = None):
        """Initialize report template manager.
        
        Args:
            template_dir: Directory containing templates
        """
        self.template_dir = Path(template_dir) if template_dir else Path(__file__).parent / "templates"
        self.template_dir.mkdir(exist_ok=True)
        
        # Setup Jinja2 environment
        self.env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(str(self.template_dir)),
            autoescape=jinja2.select_autoescape(['html', 'xml'])
        )
        
        # Create default templates if they don't exist
        self._create_default_templates()
    
    def _create_default_templates(self):
        """Create default report templates."""
        # Portfolio summary template
        portfolio_template = """
<!DOCTYPE html>
<html>
<head>
    <title>{{ title }}</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; }
        .header { text-align: center; margin-bottom: 30px; }
        .summary { background: #f8f9fa; padding: 20px; border-radius: 5px; margin-bottom: 20px; }
        .chart { margin: 20px 0; text-align: center; }
        .table { width: 100%; border-collapse: collapse; margin: 20px 0; }
        .table th, .table td { border: 1px solid #ddd; padding: 8px; text-align: left; }
        .table th { background-color: #f2f2f2; }
        .metric { display: inline-block; margin: 10px 20px; text-align: center; }
        .metric-value { font-size: 24px; font-weight: bold; color: #1f77b4; }
        .metric-label { font-size: 14px; color: #666; }
    </style>
</head>
<body>
    <div class="header">
        <h1>{{ title }}</h1>
        <p>Generated on {{ generated_at.strftime('%Y-%m-%d %H:%M:%S UTC') }}</p>
    </div>
    
    {% if include_summary %}
    <div class="summary">
        <h2>Portfolio Summary</h2>
        <div class="metric">
            <div class="metric-value">${{ "%.2f"|format(portfolio_value) }}</div>
            <div class="metric-label">Total Value</div>
        </div>
        <div class="metric">
            <div class="metric-value">{{ "%.2f"|format(total_return_percent) }}%</div>
            <div class="metric-label">Total Return</div>
        </div>
        <div class="metric">
            <div class="metric-value">{{ holdings_count }}</div>
            <div class="metric-label">Holdings</div>
        </div>
    </div>
    {% endif %}
    
    {% if include_charts %}
    {% for chart_name, chart_html in charts.items() %}
    <div class="chart">
        <h3>{{ chart_name.replace('_', ' ').title() }}</h3>
        {{ chart_html|safe }}
    </div>
    {% endfor %}
    {% endif %}
    
    {% if include_tables %}
    {% for table_name, table_data in tables.items() %}
    <div>
        <h3>{{ table_name.replace('_', ' ').title() }}</h3>
        <table class="table">
            {% if table_data %}
            <thead>
                <tr>
                    {% for key in table_data[0].keys() %}
                    <th>{{ key.replace('_', ' ').title() }}</th>
                    {% endfor %}
                </tr>
            </thead>
            <tbody>
                {% for row in table_data %}
                <tr>
                    {% for value in row.values() %}
                    <td>{{ value }}</td>
                    {% endfor %}
                </tr>
                {% endfor %}
            </tbody>
            {% endif %}
        </table>
    </div>
    {% endfor %}
    {% endif %}
</body>
</html>
        """
        
        template_file = self.template_dir / "portfolio_summary.html"
        if not template_file.exists():
            template_file.write_text(portfolio_template.strip())
    
    def get_template(self, template_name: str) -> jinja2.Template:
        """Get template by name.
        
        Args:
            template_name: Template name
            
        Returns:
            Jinja2 template object
        """
        return self.env.get_template(template_name)
    
    def render_template(self, template_name: str, context: Dict[str, Any]) -> str:
        """Render template with context.
        
        Args:
            template_name: Template name
            context: Template context data
            
        Returns:
            Rendered template string
        """
        template = self.get_template(template_name)
        return template.render(**context)


class BaseReport:
    """Base class for all report types."""
    
    def __init__(self, config: ReportConfig):
        """Initialize base report.
        
        Args:
            config: Report configuration
        """
        self.config = config
        self.chart_generator = ChartGenerator()
        self.template_manager = ReportTemplate()
        self.data = ReportData()
    
    def generate(self, data: ReportData) -> str:
        """Generate the report.
        
        Args:
            data: Report data
            
        Returns:
            Generated report content
        """
        raise NotImplementedError("Subclasses must implement generate method")
    
    def save(self, content: str, filename: str) -> str:
        """Save report to file.
        
        Args:
            content: Report content
            filename: Output filename
            
        Returns:
            Path to saved file
        """
        output_path = Path(filename)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        if self.config.format == ReportFormat.PDF:
            # Convert HTML to PDF
            html_doc = weasyprint.HTML(string=content)
            html_doc.write_pdf(str(output_path))
        else:
            # Save as text (HTML/JSON)
            output_path.write_text(content, encoding='utf-8')
        
        logger.info(f"Report saved to {output_path}")
        return str(output_path)


class HTMLReport(BaseReport):
    """HTML report generator."""
    
    def generate(self, data: ReportData) -> str:
        """Generate HTML report.
        
        Args:
            data: Report data
            
        Returns:
            HTML report content
        """
        # Prepare chart HTML
        charts_html = {}
        if self.config.include_charts and data.charts:
            for chart_name, figure in data.charts.items():
                chart_html = plot(
                    figure,
                    output_type='div',
                    include_plotlyjs=True,
                    div_id=f"chart_{chart_name}"
                )
                charts_html[chart_name] = chart_html
        
        # Calculate summary metrics
        portfolio_value = 0
        total_return_percent = 0
        holdings_count = 0
        
        if data.portfolio_snapshots:
            latest_snapshot = data.portfolio_snapshots[-1]
            portfolio_value = float(latest_snapshot.portfolio_value)
            holdings_count = len(latest_snapshot.holdings)
            
            if len(data.portfolio_snapshots) > 1:
                initial_value = float(data.portfolio_snapshots[0].portfolio_value)
                if initial_value > 0:
                    total_return_percent = ((portfolio_value - initial_value) / initial_value) * 100
        
        # Prepare template context
        context = {
            'title': self.config.title or f"{self.config.report_type.value.replace('_', ' ').title()} Report",
            'generated_at': data.generated_at,
            'include_summary': self.config.include_summary,
            'include_charts': self.config.include_charts,
            'include_tables': self.config.include_tables,
            'charts': charts_html,
            'tables': data.tables,
            'portfolio_value': portfolio_value,
            'total_return_percent': total_return_percent,
            'holdings_count': holdings_count,
            'metadata': data.metadata
        }
        
        # Render template
        template_name = self.config.custom_template or "portfolio_summary.html"
        return self.template_manager.render_template(template_name, context)


class PDFReport(HTMLReport):
    """PDF report generator (extends HTML report)."""
    
    def __init__(self, config: ReportConfig):
        """Initialize PDF report."""
        config.format = ReportFormat.PDF
        super().__init__(config)


class JSONReport(BaseReport):
    """JSON report generator."""
    
    def generate(self, data: ReportData) -> str:
        """Generate JSON report.
        
        Args:
            data: Report data
            
        Returns:
            JSON report content
        """
        # Convert data to JSON-serializable format
        report_data = {
            'title': self.config.title or f"{self.config.report_type.value.replace('_', ' ').title()} Report",
            'generated_at': data.generated_at.isoformat(),
            'report_type': self.config.report_type.value,
            'portfolio_snapshots': [
                {
                    'timestamp': snapshot.timestamp.isoformat(),
                    'portfolio_value': float(snapshot.portfolio_value),
                    'total_cost': float(snapshot.total_cost),
                    'holdings': [
                        {
                            'symbol': holding.symbol,
                            'amount': float(holding.amount),
                            'current_value': float(holding.current_value),
                            'cost_basis': float(holding.cost_basis)
                        }
                        for holding in snapshot.holdings
                    ]
                }
                for snapshot in data.portfolio_snapshots
            ],
            'performance_metrics': data.performance_metrics.__dict__ if data.performance_metrics else None,
            'tables': data.tables,
            'metadata': data.metadata
        }
        
        return json.dumps(report_data, indent=2, default=str)


class ReportGenerator:
    """Main report generation engine."""
    
    def __init__(self):
        """Initialize report generator."""
        self.chart_generator = ChartGenerator()
        self.report_types = {
            ReportType.PORTFOLIO_SUMMARY: self._generate_portfolio_summary,
            ReportType.PERFORMANCE_ANALYSIS: self._generate_performance_analysis,
            ReportType.RISK_ASSESSMENT: self._generate_risk_assessment,
            ReportType.ALLOCATION_REPORT: self._generate_allocation_report
        }
    
    def generate_report(self, config: ReportConfig, portfolio_snapshots: List[PortfolioSnapshot]) -> str:
        """Generate report based on configuration.
        
        Args:
            config: Report configuration
            portfolio_snapshots: Portfolio data
            
        Returns:
            Path to generated report file
        """
        # Prepare report data
        data = ReportData(portfolio_snapshots=portfolio_snapshots)
        
        # Generate charts and tables based on report type
        if config.report_type in self.report_types:
            self.report_types[config.report_type](data, config)
        
        # Create appropriate report generator
        if config.format == ReportFormat.HTML:
            report = HTMLReport(config)
        elif config.format == ReportFormat.PDF:
            report = PDFReport(config)
        elif config.format == ReportFormat.JSON:
            report = JSONReport(config)
        else:
            raise ValueError(f"Unsupported report format: {config.format}")
        
        # Generate report content
        content = report.generate(data)
        
        # Save report
        if config.output_path:
            return report.save(content, config.output_path)
        else:
            # Generate default filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{config.report_type.value}_{timestamp}.{config.format.value}"
            return report.save(content, filename)
    
    def _generate_portfolio_summary(self, data: ReportData, config: ReportConfig):
        """Generate portfolio summary charts and tables."""
        if not data.portfolio_snapshots:
            return
        
        # Portfolio performance chart
        if config.include_charts:
            perf_chart = self.chart_generator.create_portfolio_performance_chart(
                data.portfolio_snapshots,
                "Portfolio Performance Over Time"
            )
            data.charts['portfolio_performance'] = perf_chart
            
            # Allocation chart (latest snapshot)
            latest_snapshot = data.portfolio_snapshots[-1]
            alloc_chart = self.chart_generator.create_allocation_pie_chart(
                latest_snapshot,
                "Current Portfolio Allocation"
            )
            data.charts['allocation'] = alloc_chart
        
        # Holdings table
        if config.include_tables:
            latest_snapshot = data.portfolio_snapshots[-1]
            holdings_table = []
            for holding in latest_snapshot.holdings:
                holdings_table.append({
                    'Symbol': holding.symbol,
                    'Amount': f"{holding.amount:.6f}",
                    'Current Value': f"${holding.current_value:.2f}",
                    'Cost Basis': f"${holding.cost_basis:.2f}",
                    'P&L': f"${holding.current_value - holding.cost_basis:.2f}"
                })
            data.tables['holdings'] = holdings_table
    
    def _generate_performance_analysis(self, data: ReportData, config: ReportConfig):
        """Generate performance analysis charts and tables."""
        # Placeholder for performance analysis
        data.metadata['analysis_type'] = 'performance'
    
    def _generate_risk_assessment(self, data: ReportData, config: ReportConfig):
        """Generate risk assessment charts and tables."""
        # Placeholder for risk assessment
        data.metadata['analysis_type'] = 'risk'
    
    def _generate_allocation_report(self, data: ReportData, config: ReportConfig):
        """Generate allocation report charts and tables."""
        # Placeholder for allocation analysis
        data.metadata['analysis_type'] = 'allocation'
