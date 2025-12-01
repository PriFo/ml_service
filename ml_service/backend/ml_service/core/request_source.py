"""Utilities for detecting request source and extracting metadata"""
from fastapi import Request
from typing import Optional


def get_client_ip(request: Request) -> Optional[str]:
    """
    Get client IP address, considering proxy headers.
    Checks X-Forwarded-For, X-Real-IP, and direct client host.
    """
    # Check X-Forwarded-For header (most common proxy header)
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # X-Forwarded-For can contain multiple IPs, take the first one
        ip = forwarded_for.split(",")[0].strip()
        if ip:
            return ip
    
    # Check X-Real-IP header (nginx proxy)
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()
    
    # Fallback to direct client host
    if request.client:
        return request.client.host
    
    return None


def get_user_agent(request: Request) -> Optional[str]:
    """Get User-Agent from request headers"""
    return request.headers.get("User-Agent")


def detect_request_source(request: Request) -> str:
    """
    Detect request source based on User-Agent.
    Returns: 'gui', 'api', or 'system'
    """
    user_agent = get_user_agent(request)
    
    if not user_agent:
        return "api"  # Default to API if no User-Agent
    
    user_agent_lower = user_agent.lower()
    
    # Check for browser User-Agents (GUI)
    browser_indicators = [
        "mozilla", "chrome", "firefox", "safari", "edge", 
        "opera", "webkit", "gecko", "msie", "trident"
    ]
    
    for indicator in browser_indicators:
        if indicator in user_agent_lower:
            return "gui"
    
    # Check for common API clients
    api_indicators = [
        "python-requests", "curl", "postman", "httpie", 
        "go-http-client", "java", "okhttp"
    ]
    
    for indicator in api_indicators:
        if indicator in user_agent_lower:
            return "api"
    
    # Default to API for unknown User-Agents
    return "api"
