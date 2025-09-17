import base64
import json
import hashlib
from typing import Optional
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.exceptions import InvalidSignature
import structlog

from app.config.settings import settings

logger = structlog.get_logger()


class SignatureVerificationMiddleware(BaseHTTPMiddleware):
    """
    Middleware to verify SHA512withRSA digital signature from bank
    """
    
    def __init__(self, app):
        super().__init__(app)
        self.bank_public_key = None
        self._load_bank_public_key()
    
    def _load_bank_public_key(self):
        """Load bank's public key for signature verification"""
        try:
            self.bank_public_key = settings.load_bank_public_key()
            logger.info("bank_public_key_loaded", key_size=self.bank_public_key.key_size)
        except FileNotFoundError as e:
            logger.error("bank_public_key_not_found", error=str(e))
            self.bank_public_key = None
        except Exception as e:
            logger.error("bank_public_key_load_error", error=str(e))
            self.bank_public_key = None
    
    async def dispatch(self, request: Request, call_next):
        # Only verify signature for webhook endpoints
        if not request.url.path.startswith("/webhook/"):
            return await call_next(request)
        
        # Skip verification for non-POST requests
        if request.method != "POST":
            return await call_next(request)
        
        try:
            # Read request body
            body = await request.body()
            
            if not body:
                logger.error("empty_request_body")
                return JSONResponse(
                    status_code=200,
                    content={
                        "batchId": "unknown",
                        "code": "400",
                        "message": "Empty request body",
                        "data": []
                    }
                )
            
            # Parse JSON to get signature
            try:
                payload = json.loads(body.decode('utf-8'))
            except json.JSONDecodeError as e:
                logger.error("invalid_json", error=str(e))
                return JSONResponse(
                    status_code=200,
                    content={
                        "batchId": "unknown",
                        "code": "400", 
                        "message": "Invalid JSON format",
                        "data": []
                    }
                )
            
            # Get batch_id for error responses
            batch_id = payload.get('batchId', 'unknown')
            
            # Extract signature
            signature = payload.get('signature')
            if not signature:
                logger.error("missing_signature")
                return JSONResponse(
                    status_code=200,
                    content={
                        "batchId": batch_id,
                        "code": "401",
                        "message": "Missing signature", 
                        "data": []
                    }
                )
            # Create payload for signature verification (exclude signature field)
            payload_for_verification = {k: v for k, v in payload.items() if k != 'signature'}
            
            # Verify signature
            if not await self._verify_signature(payload_for_verification, signature):
                logger.error(
                    "signature_verification_failed",
                    batch_id=batch_id
                )
                return JSONResponse(
                    status_code=200,
                    content={
                        "batchId": batch_id,
                        "code": "401",
                        "message": "Signature is not valid",
                        "data": []
                    }
                )
            
            logger.info(
                "signature_verified",
                transaction_id=payload.get('transaction_id', 'unknown')
            )
            
            # Create new request with body for downstream processing
            async def receive():
                return {
                    "type": "http.request",
                    "body": body,
                    "more_body": False
                }
            
            request._receive = receive
            
            return await call_next(request)
            
        except Exception as e:
            logger.error("signature_verification_error", error=str(e), exc_info=True)
            return JSONResponse(
                status_code=200,
                content={
                    "batchId": payload.get("batchId", "unknown") if payload else "unknown",
                    "code": "500",
                    "message": "Signature verification error",
                    "data": []
                }
            )
    
    async def _verify_signature(self, payload: dict, signature: str) -> bool:
        """
        Verify SHA512withRSA signature
        
        Args:
            payload: Dictionary containing the data to verify
            signature: Base64 encoded signature string
            
        Returns:
            bool: True if signature is valid, False otherwise
        """
        if not self.bank_public_key:
            logger.error("no_public_key_available")
            return False
        
        try:
            # Create canonical string representation for signing
            # Sort keys to ensure consistent ordering
            canonical_string = self._create_canonical_string(payload)
            
            # Decode base64 signature
            signature_bytes = base64.b64decode(signature)
            
            # Verify signature using SHA512withRSA
            self.bank_public_key.verify(
                signature_bytes,
                canonical_string.encode('utf-8'),
                padding.PKCS1v15(),
                hashes.SHA512()
            )
            
            logger.info("signature_verification_success")
            return True
            
        except InvalidSignature:
            logger.error("invalid_signature")
            return False
        except Exception as e:
            logger.error("signature_verification_exception", error=str(e))
            return False
    
    def _create_canonical_string(self, payload: dict) -> str:
        """
        Create canonical string representation for signature verification
        
        This method creates a consistent string representation of the payload
        by sorting keys and formatting values in a standardized way.
        
        Args:
            payload: Dictionary to create canonical string from
            
        Returns:
            str: Canonical string representation
        """
        # Sort keys alphabetically for consistent ordering
        sorted_items = sorted(payload.items())
        
        # Create key=value pairs
        pairs = []
        for key, value in sorted_items:
            # Convert value to string representation
            if isinstance(value, (dict, list)):
                value_str = json.dumps(value, sort_keys=True, separators=(',', ':'))
            else:
                value_str = str(value)
            
            pairs.append(f"{key}={value_str}")
        
        # Join with & separator
        canonical_string = "&".join(pairs)
        
        logger.debug("canonical_string_created", length=len(canonical_string))
        return canonical_string