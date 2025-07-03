"""Tests for visualization reports module."""

import pytest
import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch
from datetime import datetime, timezone
from decimal import Decimal

from crypto_portfolio_analyzer.visualization.reports import (
    ReportType, ReportFormat, ReportConfig, ReportData, ReportTemplate,
    BaseReport, HTMLReport, PDFReport, JSONReport, ReportGenerator
)
from crypto_portfolio_analyzer.analytics.models import PortfolioSnapshot, PortfolioHolding


class TestReportConfig:
    """Test ReportConfig class."""
    
    def test_report_config_creation(self):
        """Test creating report configuration."""
        config = ReportConfig(
            report_type=ReportType.PORTFOLIO_SUMMARY,
            format=ReportFormat.HTML,
            title="Test Report",
            include_charts=True,
            include_tables=True
        )
        
        assert config.report_type == ReportType.PORTFOLIO_SUMMARY
        assert config.format == ReportFormat.HTML
        assert config.title == "Test Report"
        assert config.include_charts is True
        assert config.include_tables is True
        assert config.include_summary is True
    
    def test_report_config_defaults(self):
        """Test report configuration defaults."""
        config = ReportConfig(report_type=ReportType.PORTFOLIO_SUMMARY)
        
        assert config.format == ReportFormat.HTML
        assert config.include_charts is True
        assert config.include_tables is True
        assert config.include_summary is True
        assert config.theme == "default"


class TestReportData:
    """Test ReportData class."""
    
    def test_report_data_creation(self):
        """Test creating report data."""
        data = ReportData()
        
        assert data.portfolio_snapshots == []
        assert data.performance_metrics is None
        assert data.charts == {}
        assert data.tables == {}
        assert data.metadata == {}
        assert isinstance(data.generated_at, datetime)
    
    def test_report_data_with_content(self):
        """Test report data with content."""
        snapshots = [Mock()]
        charts = {"test_chart": Mock()}
        tables = {"test_table": []}
        metadata = {"test": "value"}
        
        data = ReportData(
            portfolio_snapshots=snapshots,
            charts=charts,
            tables=tables,
            metadata=metadata
        )
        
        assert data.portfolio_snapshots == snapshots
        assert data.charts == charts
        assert data.tables == tables
        assert data.metadata == metadata


class TestReportTemplate:
    """Test ReportTemplate class."""
    
    @pytest.fixture
    def temp_template_dir(self):
        """Create temporary template directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir
    
    def test_report_template_creation(self, temp_template_dir):
        """Test creating report template manager."""
        template_manager = ReportTemplate(temp_template_dir)
        
        assert template_manager.template_dir == Path(temp_template_dir)
        assert template_manager.env is not None
    
    def test_create_default_templates(self, temp_template_dir):
        """Test creating default templates."""
        template_manager = ReportTemplate(temp_template_dir)
        
        # Should create default template
        template_file = Path(temp_template_dir) / "portfolio_summary.html"
        assert template_file.exists()
        
        content = template_file.read_text()
        assert "Portfolio Summary" in content
        assert "{{ title }}" in content
    
    def test_get_template(self, temp_template_dir):
        """Test getting template."""
        template_manager = ReportTemplate(temp_template_dir)
        
        template = template_manager.get_template("portfolio_summary.html")
        assert template is not None
    
    def test_render_template(self, temp_template_dir):
        """Test rendering template."""
        template_manager = ReportTemplate(temp_template_dir)
        
        context = {
            "title": "Test Report",
            "generated_at": datetime.now(timezone.utc),
            "portfolio_value": 100000,
            "total_return_percent": 10.5,
            "holdings_count": 5,
            "include_summary": True,
            "include_charts": False,
            "include_tables": False,
            "charts": {},
            "tables": {},
            "metadata": {}
        }
        
        rendered = template_manager.render_template("portfolio_summary.html", context)
        
        assert "Test Report" in rendered
        assert "Portfolio Summary" in rendered
        assert "$100000.00" in rendered
        assert "10.50%" in rendered


class TestBaseReport:
    """Test BaseReport class."""
    
    def test_base_report_creation(self):
        """Test creating base report."""
        config = ReportConfig(report_type=ReportType.PORTFOLIO_SUMMARY)
        report = BaseReport(config)
        
        assert report.config == config
        assert report.chart_generator is not None
        assert report.template_manager is not None
        assert report.data is not None
    
    def test_generate_not_implemented(self):
        """Test that generate method raises NotImplementedError."""
        config = ReportConfig(report_type=ReportType.PORTFOLIO_SUMMARY)
        report = BaseReport(config)
        
        with pytest.raises(NotImplementedError):
            report.generate(ReportData())
    
    def test_save_html(self):
        """Test saving HTML report."""
        config = ReportConfig(report_type=ReportType.PORTFOLIO_SUMMARY, format=ReportFormat.HTML)
        report = BaseReport(config)
        
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as temp_file:
            temp_path = temp_file.name
        
        try:
            content = "<html><body>Test Report</body></html>"
            saved_path = report.save(content, temp_path)
            
            assert saved_path == temp_path
            assert Path(temp_path).exists()
            assert Path(temp_path).read_text() == content
        finally:
            Path(temp_path).unlink(missing_ok=True)


class TestHTMLReport:
    """Test HTMLReport class."""
    
    @pytest.fixture
    def sample_portfolio_data(self):
        """Create sample portfolio data."""
        holdings = [
            PortfolioHolding(
                symbol="BTC",
                amount=Decimal("1.0"),
                current_value=Decimal("50000"),
                cost_basis=Decimal("45000")
            ),
            PortfolioHolding(
                symbol="ETH",
                amount=Decimal("10.0"),
                current_value=Decimal("30000"),
                cost_basis=Decimal("25000")
            )
        ]
        
        snapshot = PortfolioSnapshot(
            timestamp=datetime.now(timezone.utc),
            portfolio_value=Decimal("80000"),
            total_cost=Decimal("70000"),
            holdings=holdings
        )
        
        return ReportData(portfolio_snapshots=[snapshot])
    
    def test_html_report_creation(self):
        """Test creating HTML report."""
        config = ReportConfig(report_type=ReportType.PORTFOLIO_SUMMARY, format=ReportFormat.HTML)
        report = HTMLReport(config)
        
        assert isinstance(report, BaseReport)
        assert report.config.format == ReportFormat.HTML
    
    @patch('crypto_portfolio_analyzer.visualization.reports.plot')
    def test_html_report_generation(self, mock_plot, sample_portfolio_data):
        """Test generating HTML report."""
        config = ReportConfig(
            report_type=ReportType.PORTFOLIO_SUMMARY,
            format=ReportFormat.HTML,
            title="Test Portfolio Report",
            include_charts=True,
            include_tables=True
        )
        report = HTMLReport(config)
        
        # Mock chart generation
        mock_plot.return_value = "<div>Mock Chart</div>"
        sample_portfolio_data.charts = {"portfolio_performance": Mock()}
        
        content = report.generate(sample_portfolio_data)
        
        assert isinstance(content, str)
        assert "Test Portfolio Report" in content
        assert "Portfolio Summary" in content
        assert "$80000.00" in content  # Portfolio value
    
    def test_html_report_without_charts(self, sample_portfolio_data):
        """Test HTML report without charts."""
        config = ReportConfig(
            report_type=ReportType.PORTFOLIO_SUMMARY,
            format=ReportFormat.HTML,
            include_charts=False
        )
        report = HTMLReport(config)
        
        content = report.generate(sample_portfolio_data)
        
        assert isinstance(content, str)
        assert "Portfolio Summary" in content


class TestJSONReport:
    """Test JSONReport class."""
    
    @pytest.fixture
    def sample_portfolio_data(self):
        """Create sample portfolio data."""
        holdings = [
            PortfolioHolding(
                symbol="BTC",
                amount=Decimal("1.0"),
                current_value=Decimal("50000"),
                cost_basis=Decimal("45000")
            )
        ]
        
        snapshot = PortfolioSnapshot(
            timestamp=datetime.now(timezone.utc),
            portfolio_value=Decimal("50000"),
            total_cost=Decimal("45000"),
            holdings=holdings
        )
        
        return ReportData(portfolio_snapshots=[snapshot])
    
    def test_json_report_creation(self):
        """Test creating JSON report."""
        config = ReportConfig(report_type=ReportType.PORTFOLIO_SUMMARY, format=ReportFormat.JSON)
        report = JSONReport(config)
        
        assert isinstance(report, BaseReport)
        assert report.config.format == ReportFormat.JSON
    
    def test_json_report_generation(self, sample_portfolio_data):
        """Test generating JSON report."""
        config = ReportConfig(
            report_type=ReportType.PORTFOLIO_SUMMARY,
            format=ReportFormat.JSON,
            title="Test Portfolio Report"
        )
        report = JSONReport(config)
        
        content = report.generate(sample_portfolio_data)
        
        assert isinstance(content, str)
        
        # Parse JSON to verify structure
        data = json.loads(content)
        assert data["title"] == "Test Portfolio Report"
        assert "generated_at" in data
        assert "portfolio_snapshots" in data
        assert data["data_type"] == "portfolio_snapshots"
        assert len(data["portfolio_snapshots"]) == 1
        
        # Check portfolio snapshot structure
        snapshot = data["portfolio_snapshots"][0]
        assert "timestamp" in snapshot
        assert snapshot["portfolio_value"] == 50000.0
        assert snapshot["total_cost"] == 45000.0
        assert len(snapshot["holdings"]) == 1
        
        # Check holding structure
        holding = snapshot["holdings"][0]
        assert holding["symbol"] == "BTC"
        assert holding["amount"] == 1.0
        assert holding["current_value"] == 50000.0
        assert holding["cost_basis"] == 45000.0


class TestReportGenerator:
    """Test ReportGenerator class."""
    
    @pytest.fixture
    def sample_snapshots(self):
        """Create sample portfolio snapshots."""
        holdings = [
            PortfolioHolding(
                symbol="BTC",
                amount=Decimal("1.0"),
                current_value=Decimal("50000"),
                cost_basis=Decimal("45000")
            )
        ]
        
        return [
            PortfolioSnapshot(
                timestamp=datetime.now(timezone.utc),
                portfolio_value=Decimal("50000"),
                total_cost=Decimal("45000"),
                holdings=holdings
            )
        ]
    
    def test_report_generator_creation(self):
        """Test creating report generator."""
        generator = ReportGenerator()
        
        assert generator.chart_generator is not None
        assert generator.report_types is not None
        assert ReportType.PORTFOLIO_SUMMARY in generator.report_types
    
    @patch('crypto_portfolio_analyzer.visualization.reports.HTMLReport')
    def test_generate_html_report(self, mock_html_report, sample_snapshots):
        """Test generating HTML report."""
        generator = ReportGenerator()
        
        mock_report_instance = Mock()
        mock_report_instance.generate.return_value = "<html>Test Report</html>"
        mock_report_instance.save.return_value = "/path/to/report.html"
        mock_html_report.return_value = mock_report_instance
        
        config = ReportConfig(
            report_type=ReportType.PORTFOLIO_SUMMARY,
            format=ReportFormat.HTML,
            output_path="test_report.html"
        )
        
        result_path = generator.generate_report(config, sample_snapshots)
        
        assert result_path == "/path/to/report.html"
        mock_html_report.assert_called_once_with(config)
        mock_report_instance.generate.assert_called_once()
        mock_report_instance.save.assert_called_once()
    
    @patch('crypto_portfolio_analyzer.visualization.reports.JSONReport')
    def test_generate_json_report(self, mock_json_report, sample_snapshots):
        """Test generating JSON report."""
        generator = ReportGenerator()
        
        mock_report_instance = Mock()
        mock_report_instance.generate.return_value = '{"test": "data"}'
        mock_report_instance.save.return_value = "/path/to/report.json"
        mock_json_report.return_value = mock_report_instance
        
        config = ReportConfig(
            report_type=ReportType.PORTFOLIO_SUMMARY,
            format=ReportFormat.JSON
        )
        
        result_path = generator.generate_report(config, sample_snapshots)
        
        assert result_path == "/path/to/report.json"
        mock_json_report.assert_called_once_with(config)
    
    def test_generate_report_unsupported_format(self, sample_snapshots):
        """Test generating report with unsupported format."""
        generator = ReportGenerator()
        
        # Create config with invalid format (this would need to be done by bypassing enum validation)
        config = ReportConfig(report_type=ReportType.PORTFOLIO_SUMMARY)
        config.format = "invalid_format"  # Bypass enum validation
        
        with pytest.raises(ValueError, match="Unsupported report format"):
            generator.generate_report(config, sample_snapshots)
    
    @patch.object(ReportGenerator, '_generate_portfolio_summary')
    def test_generate_portfolio_summary_report(self, mock_generate_summary, sample_snapshots):
        """Test generating portfolio summary report."""
        generator = ReportGenerator()
        
        config = ReportConfig(
            report_type=ReportType.PORTFOLIO_SUMMARY,
            format=ReportFormat.JSON
        )
        
        with patch('crypto_portfolio_analyzer.visualization.reports.JSONReport') as mock_json_report:
            mock_report_instance = Mock()
            mock_report_instance.generate.return_value = '{"test": "data"}'
            mock_report_instance.save.return_value = "/path/to/report.json"
            mock_json_report.return_value = mock_report_instance
            
            generator.generate_report(config, sample_snapshots)
            
            mock_generate_summary.assert_called_once()
    
    def test_generate_portfolio_summary_data(self, sample_snapshots):
        """Test generating portfolio summary data."""
        generator = ReportGenerator()
        
        data = ReportData(portfolio_snapshots=sample_snapshots)
        config = ReportConfig(
            report_type=ReportType.PORTFOLIO_SUMMARY,
            include_charts=True,
            include_tables=True
        )
        
        with patch.object(generator.chart_generator, 'create_portfolio_performance_chart') as mock_perf_chart, \
             patch.object(generator.chart_generator, 'create_allocation_pie_chart') as mock_alloc_chart:
            
            mock_perf_chart.return_value = Mock()
            mock_alloc_chart.return_value = Mock()
            
            generator._generate_portfolio_summary(data, config)
            
            # Should create charts
            assert 'portfolio_performance' in data.charts
            assert 'allocation' in data.charts
            
            # Should create tables
            assert 'holdings' in data.tables
            assert len(data.tables['holdings']) == 1
            
            holdings_table = data.tables['holdings'][0]
            assert holdings_table['Symbol'] == 'BTC'
            assert holdings_table['Amount'] == '1.000000'
            assert '$50000.00' in holdings_table['Current Value']
