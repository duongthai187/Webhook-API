import os
from typing import List
from pydantic import BaseSettings, field_validator
from cryptography.hazmat.primitives import serialization


class Settings(BaseSettings):
    # Server settings
    host: str = "0.0.0.0"
    port: int = 8443
    reload: bool = False
    
    # TLS/SSL settings
    ssl_cert_file: str = "certs/server.crt"
    ssl_key_file: str = "certs/server.key"
    client_ca_file: str = "certs/ca.crt"
    
    # Bank public key for signature verification
    bank_public_key_file: str = "certs/bank_public.pem"
    
    # Bank client certificate for authentication (optional - for 1-way cert validation)
    bank_certificate_file: str = "certs/bank_client.crt"
    
    # Security settings
    allowed_ips: List[str] = ["127.0.0.1", "::1"]
    
    # Rate limiting (requests per minute per IP)
    rate_limit_requests: int = 60
    rate_limit_window: int = 60  # seconds
    
    # Redis settings for rate limiting
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: str = ""
    
    # Logging
    log_level: str = "INFO"
    
    class Config:
        env_file = ".env"
        case_sensitive = False

    @field_validator('allowed_ips', mode='before')
    @classmethod
    def parse_allowed_ips(cls, v):
        if isinstance(v, str):
            return [ip.strip() for ip in v.split(',') if ip.strip()]
        return v

    def load_bank_public_key(self):
        """Load bank's public key for signature verification"""
        if not os.path.exists(self.bank_public_key_file):
            raise FileNotFoundError(f"Bank public key file not found: {self.bank_public_key_file}")
        
        with open(self.bank_public_key_file, 'rb') as f:
            public_key = serialization.load_pem_public_key(f.read())
        
        return public_key


settings = Settings()