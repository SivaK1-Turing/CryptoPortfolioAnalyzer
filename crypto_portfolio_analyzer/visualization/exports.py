"""Chart export functionality for various formats."""

import os
import io
import base64
from pathlib import Path
from typing import Optional, Dict, Any, Union
import logging

import plotly.graph_objects as go
import plotly.io as pio

logger = logging.getLogger(__name__)


class ChartExporter:
    """Chart export functionality for multiple formats."""
    
    def __init__(self):
        """Initialize chart exporter."""
        self.supported_formats = ['png', 'jpg', 'jpeg', 'svg', 'pdf', 'html']
        self.default_config = {
            'width': 1200,
            'height': 800,
            'scale': 2,
            'engine': 'kaleido'  # Default engine for static exports
        }
    
    def export_chart(self, 
                    fig: go.Figure, 
                    filename: str,
                    format: str = 'png',
                    width: Optional[int] = None,
                    height: Optional[int] = None,
                    scale: Optional[int] = None) -> bool:
        """Export chart to file.
        
        Args:
            fig: Plotly figure to export
            filename: Output filename (with or without extension)
            format: Export format (png, jpg, svg, pdf, html)
            width: Image width in pixels
            height: Image height in pixels
            scale: Scale factor for image quality
            
        Returns:
            True if export successful, False otherwise
        """
        try:
            # Validate format
            format = format.lower()
            if format not in self.supported_formats:
                logger.error(f"Unsupported format: {format}")
                return False
            
            # Ensure filename has correct extension
            filename_path = Path(filename)
            if filename_path.suffix.lower() != f'.{format}':
                filename = f"{filename_path.stem}.{format}"
            
            # Set default dimensions
            export_width = width or self.default_config['width']
            export_height = height or self.default_config['height']
            export_scale = scale or self.default_config['scale']
            
            # Create output directory if it doesn't exist
            output_dir = Path(filename).parent
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # Export based on format
            if format == 'html':
                self._export_html(fig, filename)
            elif format == 'svg':
                self._export_svg(fig, filename, export_width, export_height)
            elif format == 'pdf':
                self._export_pdf(fig, filename, export_width, export_height)
            else:  # png, jpg, jpeg
                self._export_image(fig, filename, format, export_width, export_height, export_scale)
            
            logger.info(f"Chart exported successfully to {filename}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to export chart: {e}")
            return False
    
    def export_to_bytes(self, 
                       fig: go.Figure,
                       format: str = 'png',
                       width: Optional[int] = None,
                       height: Optional[int] = None,
                       scale: Optional[int] = None) -> Optional[bytes]:
        """Export chart to bytes.
        
        Args:
            fig: Plotly figure to export
            format: Export format
            width: Image width in pixels
            height: Image height in pixels
            scale: Scale factor
            
        Returns:
            Chart as bytes or None if failed
        """
        try:
            format = format.lower()
            if format not in self.supported_formats:
                logger.error(f"Unsupported format: {format}")
                return None
            
            export_width = width or self.default_config['width']
            export_height = height or self.default_config['height']
            export_scale = scale or self.default_config['scale']
            
            if format == 'html':
                html_str = fig.to_html(include_plotlyjs=True)
                return html_str.encode('utf-8')
            elif format == 'svg':
                svg_str = fig.to_image(format='svg', width=export_width, height=export_height)
                return svg_str
            elif format == 'pdf':
                pdf_bytes = fig.to_image(format='pdf', width=export_width, height=export_height)
                return pdf_bytes
            else:  # png, jpg, jpeg
                img_bytes = fig.to_image(
                    format=format,
                    width=export_width,
                    height=export_height,
                    scale=export_scale
                )
                return img_bytes
                
        except Exception as e:
            logger.error(f"Failed to export chart to bytes: {e}")
            return None
    
    def export_to_base64(self, 
                        fig: go.Figure,
                        format: str = 'png',
                        width: Optional[int] = None,
                        height: Optional[int] = None,
                        scale: Optional[int] = None) -> Optional[str]:
        """Export chart to base64 string.
        
        Args:
            fig: Plotly figure to export
            format: Export format
            width: Image width in pixels
            height: Image height in pixels
            scale: Scale factor
            
        Returns:
            Base64 encoded chart or None if failed
        """
        try:
            chart_bytes = self.export_to_bytes(fig, format, width, height, scale)
            if chart_bytes:
                return base64.b64encode(chart_bytes).decode('utf-8')
            return None
            
        except Exception as e:
            logger.error(f"Failed to export chart to base64: {e}")
            return None
    
    def _export_html(self, fig: go.Figure, filename: str) -> None:
        """Export chart as HTML file.
        
        Args:
            fig: Plotly figure
            filename: Output filename
        """
        fig.write_html(
            filename,
            include_plotlyjs=True,
            config={
                'displayModeBar': True,
                'displaylogo': False,
                'modeBarButtonsToRemove': ['pan2d', 'lasso2d']
            }
        )
    
    def _export_svg(self, fig: go.Figure, filename: str, width: int, height: int) -> None:
        """Export chart as SVG file.
        
        Args:
            fig: Plotly figure
            filename: Output filename
            width: Image width
            height: Image height
        """
        fig.write_image(filename, format='svg', width=width, height=height)
    
    def _export_pdf(self, fig: go.Figure, filename: str, width: int, height: int) -> None:
        """Export chart as PDF file.
        
        Args:
            fig: Plotly figure
            filename: Output filename
            width: Image width
            height: Image height
        """
        fig.write_image(filename, format='pdf', width=width, height=height)
    
    def _export_image(self, fig: go.Figure, filename: str, format: str, 
                     width: int, height: int, scale: int) -> None:
        """Export chart as image file.
        
        Args:
            fig: Plotly figure
            filename: Output filename
            format: Image format
            width: Image width
            height: Image height
            scale: Scale factor
        """
        fig.write_image(
            filename,
            format=format,
            width=width,
            height=height,
            scale=scale
        )
    
    def create_chart_gallery(self, 
                           charts: Dict[str, go.Figure],
                           output_dir: str = "chart_gallery",
                           format: str = 'png') -> Dict[str, str]:
        """Export multiple charts to a gallery.
        
        Args:
            charts: Dictionary mapping chart names to figures
            output_dir: Output directory for gallery
            format: Export format
            
        Returns:
            Dictionary mapping chart names to file paths
        """
        gallery_paths = {}
        
        try:
            # Create output directory
            output_path = Path(output_dir)
            output_path.mkdir(parents=True, exist_ok=True)
            
            # Export each chart
            for chart_name, fig in charts.items():
                # Sanitize filename
                safe_name = "".join(c for c in chart_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
                safe_name = safe_name.replace(' ', '_')
                
                filename = output_path / f"{safe_name}.{format}"
                
                if self.export_chart(fig, str(filename), format):
                    gallery_paths[chart_name] = str(filename)
                else:
                    logger.warning(f"Failed to export chart: {chart_name}")
            
            # Create index HTML file
            if format == 'png' or format == 'jpg':
                self._create_gallery_index(gallery_paths, output_path)
            
            logger.info(f"Chart gallery created in {output_dir}")
            
        except Exception as e:
            logger.error(f"Failed to create chart gallery: {e}")
        
        return gallery_paths
    
    def _create_gallery_index(self, gallery_paths: Dict[str, str], output_dir: Path) -> None:
        """Create HTML index for chart gallery.
        
        Args:
            gallery_paths: Dictionary of chart paths
            output_dir: Output directory
        """
        try:
            html_content = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Portfolio Chart Gallery</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            margin: 20px;
            background-color: #f5f5f5;
        }
        .header {
            text-align: center;
            margin-bottom: 30px;
        }
        .gallery {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
            gap: 20px;
        }
        .chart-item {
            background: white;
            border-radius: 8px;
            padding: 15px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .chart-title {
            font-size: 18px;
            font-weight: bold;
            margin-bottom: 10px;
            color: #333;
        }
        .chart-image {
            width: 100%;
            height: auto;
            border-radius: 4px;
        }
        .timestamp {
            text-align: center;
            color: #666;
            font-size: 14px;
            margin-top: 20px;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>Portfolio Chart Gallery</h1>
        <p>Generated portfolio analytics charts</p>
    </div>
    
    <div class="gallery">
"""
            
            # Add each chart
            for chart_name, file_path in gallery_paths.items():
                filename = Path(file_path).name
                html_content += f"""
        <div class="chart-item">
            <div class="chart-title">{chart_name}</div>
            <img src="{filename}" alt="{chart_name}" class="chart-image">
        </div>
"""
            
            html_content += f"""
    </div>
    
    <div class="timestamp">
        Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
    </div>
</body>
</html>
"""
            
            # Write index file
            index_path = output_dir / "index.html"
            with open(index_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            logger.info(f"Gallery index created: {index_path}")
            
        except Exception as e:
            logger.error(f"Failed to create gallery index: {e}")
    
    def get_export_info(self) -> Dict[str, Any]:
        """Get information about export capabilities.
        
        Returns:
            Dictionary with export information
        """
        return {
            'supported_formats': self.supported_formats,
            'default_config': self.default_config,
            'engines_available': self._check_available_engines()
        }
    
    def _check_available_engines(self) -> Dict[str, bool]:
        """Check which export engines are available.
        
        Returns:
            Dictionary of engine availability
        """
        engines = {}
        
        try:
            # Check kaleido
            import kaleido
            engines['kaleido'] = True
        except ImportError:
            engines['kaleido'] = False
        
        try:
            # Check orca (legacy)
            import plotly.io.orca
            engines['orca'] = True
        except ImportError:
            engines['orca'] = False
        
        return engines
    
    def set_default_config(self, **kwargs) -> None:
        """Update default export configuration.
        
        Args:
            **kwargs: Configuration parameters to update
        """
        self.default_config.update(kwargs)
        logger.info(f"Updated default export config: {kwargs}")


# Import datetime for gallery index
from datetime import datetime
