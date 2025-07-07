"""Distributed tracing and request tracking."""

import time
import uuid
from typing import Dict, Any, Optional, Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import wraps


@dataclass
class TracingConfig:
    """Tracing configuration."""
    enabled: bool = True
    service_name: str = "crypto-portfolio-analyzer"
    sample_rate: float = 1.0
    max_spans: int = 1000


class RequestTracer:
    """Simple request tracer."""
    
    def __init__(self, config: TracingConfig):
        self.config = config
        self.spans: Dict[str, Dict[str, Any]] = {}
    
    def start_span(self, operation_name: str, parent_span_id: Optional[str] = None) -> str:
        """Start a new span."""
        span_id = str(uuid.uuid4())
        
        self.spans[span_id] = {
            "span_id": span_id,
            "operation_name": operation_name,
            "parent_span_id": parent_span_id,
            "start_time": time.time(),
            "end_time": None,
            "tags": {},
            "logs": []
        }
        
        return span_id
    
    def finish_span(self, span_id: str):
        """Finish a span."""
        if span_id in self.spans:
            self.spans[span_id]["end_time"] = time.time()
    
    def add_tag(self, span_id: str, key: str, value: Any):
        """Add tag to span."""
        if span_id in self.spans:
            self.spans[span_id]["tags"][key] = value
    
    def log(self, span_id: str, message: str, **kwargs):
        """Add log to span."""
        if span_id in self.spans:
            self.spans[span_id]["logs"].append({
                "timestamp": time.time(),
                "message": message,
                **kwargs
            })


class DistributedTracer:
    """Distributed tracing manager."""
    
    def __init__(self, config: TracingConfig):
        self.config = config
        self.tracer = RequestTracer(config)
    
    def trace_request(self, operation_name: str):
        """Trace a request operation."""
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                if not self.config.enabled:
                    return func(*args, **kwargs)
                
                span_id = self.tracer.start_span(operation_name)
                try:
                    result = func(*args, **kwargs)
                    self.tracer.add_tag(span_id, "success", True)
                    return result
                except Exception as e:
                    self.tracer.add_tag(span_id, "error", True)
                    self.tracer.add_tag(span_id, "error_message", str(e))
                    raise
                finally:
                    self.tracer.finish_span(span_id)
            return wrapper
        return decorator


def trace_function(operation_name: str):
    """Decorator to trace function execution."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time
                print(f"TRACE: {operation_name} completed in {duration:.3f}s")
                return result
            except Exception as e:
                duration = time.time() - start_time
                print(f"TRACE: {operation_name} failed in {duration:.3f}s: {e}")
                raise
        return wrapper
    return decorator


def trace_async_function(operation_name: str):
    """Decorator to trace async function execution."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                duration = time.time() - start_time
                print(f"TRACE: {operation_name} completed in {duration:.3f}s")
                return result
            except Exception as e:
                duration = time.time() - start_time
                print(f"TRACE: {operation_name} failed in {duration:.3f}s: {e}")
                raise
        return wrapper
    return decorator
