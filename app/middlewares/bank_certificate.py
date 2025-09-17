import ssl
from typing import Optional
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from cryptography import x509
from cryptography.hazmat.primitives import hashes
import structlog

from app.config.settings import settings

logger = structlog.get_logger()


class BankCertificateMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        self.trusted_bank_cert = None
        self._load_bank_certificate()
    
    def _load_bank_certificate(self):
        """Load trusted bank certificate"""
        try:
            # Load bank certificate (you should get this from bank)
            bank_cert_path = getattr(settings, 'bank_certificate_file', 'certs/bank_client.crt')
            
            with open(bank_cert_path, 'rb') as f:
                cert_data = f.read()
                self.trusted_bank_cert = x509.load_pem_x509_certificate(cert_data)
            
            logger.info("Tải chứng chỉ ngân hàng thành công", 
                       subject=str(self.trusted_bank_cert.subject),
                       issuer=str(self.trusted_bank_cert.issuer))
        except FileNotFoundError:
            logger.warning("Chứng chỉ ngân hàng không tìm thấy", path=bank_cert_path)
            self.trusted_bank_cert = None
        except Exception as e:
            logger.error("Lỗi tải chứng chỉ ngân hàng", error=str(e))
            self.trusted_bank_cert = None
    
    async def dispatch(self, request: Request, call_next):
        # Only check certificate for webhook endpoints
        if not request.url.path.startswith("/webhook/"):
            return await call_next(request)
        
        try:
            client_cert = self._get_client_certificate(request)
            
            if not client_cert:
                logger.warning("Không có chứng chỉ khách hàng (dispatch)",
                             path=request.url.path,
                             client_ip=request.client.host)
                
                return JSONResponse(
                    status_code=200,
                    content={
                        "batchId": "unknown",
                        "code": "401",
                        "message": "Chứng chỉ khách hàng là bắt buộc",
                        "data": []
                    }
                )
            
            # Verify certificate is from trusted bank
            if not await self._verify_bank_certificate(client_cert):
                logger.warning("Chứng chỉ ngân hàng không hợp lệ",
                             path=request.url.path,
                             client_ip=request.client.host)
                
                return JSONResponse(
                    status_code=200,
                    content={
                        "batchId": "unknown",
                        "code": "401",
                        "message": "Invalid bank certificate",
                        "data": []
                    }
                )
            
            logger.info("bank_certificate_verified", 
                       client_ip=request.client.host)
            
            return await call_next(request)
            
        except Exception as e:
            logger.error("certificate_verification_error", error=str(e), exc_info=True)
            return JSONResponse(
                status_code=200,
                content={
                    "batchId": "unknown",
                    "code": "500",
                    "message": "Certificate verification error",
                    "data": []
                }
            )
    
    def _get_client_certificate(self, request: Request) -> Optional[x509.Certificate]:
        """
        Extract client certificate from request
        
        Note: This is a simplified implementation.
        In production, you would extract the certificate from the TLS connection
        """
        try:
            # Check for certificate in headers (if passed by reverse proxy)
            cert_header = request.headers.get("X-Client-Certificate")
            if cert_header:
                # Decode from base64 or PEM format
                import base64
                try:
                    cert_data = base64.b64decode(cert_header)
                    return x509.load_der_x509_certificate(cert_data)
                except:
                    # Try PEM format
                    cert_pem = cert_header.encode('utf-8')
                    return x509.load_pem_x509_certificate(cert_pem)
            
            # In a real implementation, you would extract from SSL context:
            # peer_cert = request.scope.get('transport', {}).get('peer_cert')
            # This requires uvicorn/server configuration
            
            return None
            
        except Exception as e:
            logger.error("certificate_extraction_error", error=str(e))
            return None
    
    async def _verify_bank_certificate(self, client_cert: x509.Certificate) -> bool:
        try:
            if not self.trusted_bank_cert:
                logger.error("Không có chứng chỉ ngân hàng tin cậy (_verify_bank_certificate)")
                return False
            
            # Check if certificates match (subject, issuer, public key)
            client_subject = client_cert.subject
            trusted_subject = self.trusted_bank_cert.subject
            
            # Compare certificate fingerprints (most secure)
            client_fingerprint = client_cert.fingerprint(hashes.SHA256())
            trusted_fingerprint = self.trusted_bank_cert.fingerprint(hashes.SHA256())
            
            if client_fingerprint == trusted_fingerprint:
                logger.info("certificate_fingerprint_match")
                return True
            
            # Alternative: Compare subject and issuer
            if (client_subject == trusted_subject and 
                client_cert.issuer == self.trusted_bank_cert.issuer):
                logger.info("certificate_subject_issuer_match")
                return True
            
            logger.warning("certificate_mismatch",
                         client_subject=str(client_subject),
                         trusted_subject=str(trusted_subject))
            return False
            
        except Exception as e:
            logger.error("certificate_verification_exception", error=str(e))
            return False