import ipaddress
from typing import List, Union
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
import structlog

from app.config.settings import settings

logger = structlog.get_logger()


class IPWhitelistMiddleware(BaseHTTPMiddleware):
    """
    Middleware to check if the client IP is in the allowed IP whitelist
    Supports both individual IPs and CIDR network ranges
    """
    
    def __init__(self, app):
        super().__init__(app)
        self.allowed_networks = self._parse_allowed_ips(settings.allowed_ips)
        logger.info("ip_whitelist_initialized", allowed_networks=len(self.allowed_networks))
    
    def _parse_allowed_ips(self, allowed_ips: List[str]) -> List[Union[ipaddress.IPv4Network, ipaddress.IPv6Network]]:
        """
        Parse allowed IPs and convert to network objects
        
        Args:
            allowed_ips: List of IP addresses and CIDR ranges
            
        Returns:
            List of IPv4Network/IPv6Network objects
        """
        networks = []
        
        for ip_str in allowed_ips:
            try:
                # Try to parse as network (supports both single IPs and CIDR)
                network = ipaddress.ip_network(ip_str, strict=False)
                networks.append(network)
                logger.info("allowed_network_added", network=str(network))
            except ValueError as e:
                logger.error("invalid_ip_in_whitelist", ip=ip_str, error=str(e))
                continue
        
        return networks
    
    def _get_client_ip(self, request: Request) -> str:
        """
        Get the real client IP address, considering proxy headers
        
        Args:
            request: FastAPI Request object
            
        Returns:
            str: Client IP address
        """
        # Check common proxy headers in order of preference
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # X-Forwarded-For can contain multiple IPs, take the first one
            return forwarded_for.split(',')[0].strip()
        
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip.strip()
        
        forwarded = request.headers.get("Forwarded")
        if forwarded:
            # Parse Forwarded header (RFC 7239)
            # Format: for=192.0.2.60;proto=http;by=203.0.113.43
            for part in forwarded.split(';'):
                if part.strip().startswith('for='):
                    return part.strip().split('=')[1].strip('"')
        
        # Fall back to direct connection IP
        return request.client.host if request.client else "unknown"
    
    def _is_ip_allowed(self, client_ip: str) -> bool:
        """
        Check if the client IP is in the allowed networks
        
        Args:
            client_ip: Client IP address to check
            
        Returns:
            bool: True if IP is allowed, False otherwise
        """
        try:
            client_ip_obj = ipaddress.ip_address(client_ip)
            
            for network in self.allowed_networks:
                if client_ip_obj in network:
                    return True
            
            return False
            
        except ValueError as e:
            logger.error("invalid_client_ip", client_ip=client_ip, error=str(e))
            return False
    
    async def dispatch(self, request: Request, call_next):
        """
        Main middleware logic to check IP whitelist
        
        Args:
            request: FastAPI Request object
            call_next: Next middleware/handler in chain
            
        Returns:
            Response object
        """
        # Skip IP check for health endpoints
        if request.url.path in ["/health", "/metrics"]:
            return await call_next(request)

        try:
            # Get client IP
            client_ip = self._get_client_ip(request)
            
            # Log the request attempt
            logger.info(
                "ip_whitelist_check",
                client_ip=client_ip,
                path=request.url.path,
                method=request.method,
                user_agent=request.headers.get("user-agent", "")
            )
            
            # Check if IP is allowed
            if not self._is_ip_allowed(client_ip):
                logger.warning(
                    "ip_access_denied",
                    client_ip=client_ip,
                    path=request.url.path,
                    method=request.method
                )
                
                return JSONResponse(
                    status_code=200,
                    content={
                        "batchId": "unknown",
                        "code": "403",
                        "message": "Access denied: IP not allowed",
                        "data": []
                    }
                )
            
            logger.info("ip_access_granted", client_ip=client_ip)
            
            # IP is allowed, proceed to next middleware
            return await call_next(request)
            
        except Exception as e:
            logger.error("ip_whitelist_error", error=str(e), exc_info=True)
            return JSONResponse(
                status_code=200,
                content={
                    "batchId": "unknown", 
                    "code": "500",
                    "message": "IP whitelist check error",
                    "data": []
                }
            )