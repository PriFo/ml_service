"""Utilities for detecting request source and extracting metadata"""
from fastapi import Request
from typing import Optional, Dict, Any
import re


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


def parse_user_agent(user_agent: Optional[str]) -> Dict[str, Any]:
    """
    Parse User-Agent string to extract OS, device, and other information.
    Returns dict with: os, device, browser (if applicable)
    """
    if not user_agent:
        return {"os": None, "device": None, "browser": None}
    
    ua_lower = user_agent.lower()
    result = {"os": None, "device": None, "browser": None}
    
    # Detect OS
    if "windows" in ua_lower:
        if "phone" in ua_lower:
            result["os"] = "Windows Phone"
        else:
            # Try to extract Windows version
            win_match = re.search(r'windows nt (\d+\.\d+)', ua_lower)
            if win_match:
                version = win_match.group(1)
                if version == "10.0":
                    result["os"] = "Windows 10/11"
                elif version == "6.3":
                    result["os"] = "Windows 8.1"
                elif version == "6.2":
                    result["os"] = "Windows 8"
                elif version == "6.1":
                    result["os"] = "Windows 7"
                else:
                    result["os"] = f"Windows {version}"
            else:
                result["os"] = "Windows"
    elif "mac os x" in ua_lower or "macintosh" in ua_lower:
        mac_match = re.search(r'mac os x (\d+[._]\d+)', ua_lower)
        if mac_match:
            version = mac_match.group(1).replace("_", ".")
            result["os"] = f"macOS {version}"
        else:
            result["os"] = "macOS"
    elif "linux" in ua_lower:
        result["os"] = "Linux"
    elif "android" in ua_lower:
        android_match = re.search(r'android ([\d.]+)', ua_lower)
        if android_match:
            result["os"] = f"Android {android_match.group(1)}"
        else:
            result["os"] = "Android"
    elif "iphone" in ua_lower or "ipad" in ua_lower or "ipod" in ua_lower:
        ios_match = re.search(r'os ([\d_]+)', ua_lower)
        if ios_match:
            version = ios_match.group(1).replace("_", ".")
            result["os"] = f"iOS {version}"
        else:
            result["os"] = "iOS"
    
    # Detect device
    if "mobile" in ua_lower or "android" in ua_lower or "iphone" in ua_lower:
        if "tablet" in ua_lower or "ipad" in ua_lower:
            result["device"] = "Tablet"
        else:
            result["device"] = "Mobile"
    elif "ipad" in ua_lower:
        result["device"] = "Tablet"
    else:
        result["device"] = "Desktop"
    
    # Detect browser (optional, for logging)
    if "chrome" in ua_lower and "edg" not in ua_lower:
        result["browser"] = "Chrome"
    elif "firefox" in ua_lower:
        result["browser"] = "Firefox"
    elif "safari" in ua_lower and "chrome" not in ua_lower:
        result["browser"] = "Safari"
    elif "edg" in ua_lower:
        result["browser"] = "Edge"
    elif "opera" in ua_lower:
        result["browser"] = "Opera"
    
    return result


def get_user_system_info(request: Request) -> Dict[str, Any]:
    """
    Extract user system information from request headers.
    Returns dict with: cpu_cores, ram_gb, gpu (if available from headers)
    """
    result = {"cpu_cores": None, "ram_gb": None, "gpu": None}
    
    # Try to get from custom headers (if client sends them)
    cpu_cores = request.headers.get("X-User-CPU-Cores")
    if cpu_cores:
        try:
            result["cpu_cores"] = int(cpu_cores)
        except ValueError:
            pass
    
    ram_gb = request.headers.get("X-User-RAM-GB")
    if ram_gb:
        try:
            result["ram_gb"] = float(ram_gb)
        except ValueError:
            pass
    
    gpu = request.headers.get("X-User-GPU")
    if gpu:
        result["gpu"] = gpu
    
    return result


def calculate_data_size(data: Any) -> int:
    """
    Calculate approximate size of data in bytes.
    Supports dict, list, and JSON strings.
    """
    import json
    
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except (json.JSONDecodeError, TypeError):
            return len(data.encode('utf-8'))
    
    if isinstance(data, (dict, list)):
        json_str = json.dumps(data)
        return len(json_str.encode('utf-8'))
    
    return 0
