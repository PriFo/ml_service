"""Proxy middleware for handling X-Forwarded-* headers"""
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
import logging

logger = logging.getLogger(__name__)


class ProxyHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware to handle proxy headers for external connections"""
    
    async def dispatch(self, request: Request, call_next):
        """Process proxy headers and update request"""
        # Get client IP from X-Forwarded-For or direct connection
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # X-Forwarded-For can contain multiple IPs, take the first one
            client_ip = forwarded_for.split(",")[0].strip()
            request.state.client_ip = client_ip
        else:
            # Fallback to direct connection IP
            if hasattr(request.client, 'host'):
                request.state.client_ip = request.client.host
            else:
                request.state.client_ip = "unknown"
        
        # Handle X-Forwarded-Proto header for HTTPS detection
        forwarded_proto = request.headers.get("X-Forwarded-Proto", "http")
        request.state.scheme = forwarded_proto
        
        # Handle X-Forwarded-Host header
        forwarded_host = request.headers.get("X-Forwarded-Host")
        if forwarded_host:
            request.state.host = forwarded_host
        
        # Handle X-Real-IP header (alternative to X-Forwarded-For)
        real_ip = request.headers.get("X-Real-IP")
        if real_ip and not forwarded_for:
            request.state.client_ip = real_ip
        
        response = await call_next(request)
        return response

