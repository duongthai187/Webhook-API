import structlog
from datetime import datetime
from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
import time

from app.models import WebhookRequest, WebhookResponse
from app.middlewares.ip_whitelist import IPWhitelistMiddleware
from app.middlewares.rate_limit import RateLimitMiddleware
from app.middlewares.signature_verification import SignatureVerificationMiddleware
from app.services.webhook_processor import WebhookProcessor
from app.config.settings import settings

# Initialize structured logger
logger = structlog.get_logger()

# Prometheus metrics
webhook_requests_total = Counter(
    'webhook_requests_total',
    'Total webhook requests',
    ['method', 'endpoint', 'status']
)

webhook_request_duration = Histogram(
    'webhook_request_duration_seconds',
    'Webhook request duration',
    ['method', 'endpoint']
)

signature_verification_total = Counter(
    'signature_verification_total',
    'Total signature verifications',
    ['status']
)

app = FastAPI(
    title="Bank Webhook API",
    description="Secure webhook endpoint for receiving bank notifications",
    version="1.0.0",
    docs_url="/docs" if settings.reload else None,  # Disable docs in production
    redoc_url=None
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://localhost"],  # Restrict to specific origins
    allow_credentials=True,
    allow_methods=["POST"],
    allow_headers=["*"],
)

# Add custom middlewares
app.add_middleware(RateLimitMiddleware)
app.add_middleware(IPWhitelistMiddleware)
app.add_middleware(SignatureVerificationMiddleware)

# Initialize webhook processor
webhook_processor = WebhookProcessor()


@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    """Add processing time and logging middleware"""
    start_time = time.time()
    
    # Log incoming request
    logger.info(
        "incoming_request",
        method=request.method,
        url=str(request.url),
        client_ip=request.client.host,
        user_agent=request.headers.get("user-agent", "")
    )
    
    response = await call_next(request)
    
    # Calculate processing time
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    
    # Update metrics
    webhook_requests_total.labels(
        method=request.method,
        endpoint=request.url.path,
        status=response.status_code
    ).inc()
    
    webhook_request_duration.labels(
        method=request.method,
        endpoint=request.url.path
    ).observe(process_time)
    
    # Log response
    logger.info(
        "request_processed",
        method=request.method,
        url=str(request.url),
        status_code=response.status_code,
        process_time=process_time
    )
    
    return response


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0"
    }


@app.get("/metrics")
async def get_metrics():
    """Prometheus metrics endpoint"""
    return JSONResponse(
        content=generate_latest().decode('utf-8'),
        media_type=CONTENT_TYPE_LATEST
    )


@app.post("/webhook/bank-notification", response_model=WebhookResponse)
async def receive_bank_notification(
    webhook_data: WebhookRequest,
    request: Request
):
    """
    Main webhook endpoint to receive bank notifications
    
    This endpoint:
    1. Receives POST requests with bank transaction data
    2. Validates digital signature (SHA512withRSA)
    3. Processes the transaction data
    4. Returns success/error response
    
    Security features applied via middleware:
    - IP whitelist validation
    - Rate limiting
    - Signature verification
    - mTLS (configured at server level)
    """
    try:
        logger.info(
            "webhook_received",
            transaction_id=webhook_data.transaction_id,
            amount=webhook_data.amount,
            account_number=webhook_data.account_number,
            transaction_type=webhook_data.transaction_type
        )
        
        # Process webhook data
        result = await webhook_processor.process_notification(webhook_data)
        
        if result["success"]:
            logger.info(
                "webhook_processed_successfully",
                transaction_id=webhook_data.transaction_id
            )
            
            return WebhookResponse(
                success=True,
                message="Notification processed successfully",
                transaction_id=webhook_data.transaction_id
            )
        else:
            logger.error(
                "webhook_processing_failed",
                transaction_id=webhook_data.transaction_id,
                error=result.get("error", "Unknown error")
            )
            
            raise HTTPException(
                status_code=422,
                detail=f"Processing failed: {result.get('error', 'Unknown error')}"
            )
            
    except Exception as e:
        logger.error(
            "webhook_error",
            transaction_id=getattr(webhook_data, 'transaction_id', 'unknown'),
            error=str(e),
            exc_info=True
        )
        
        raise HTTPException(
            status_code=500,
            detail="Internal server error"
        )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Custom HTTP exception handler"""
    logger.error(
        "http_exception",
        status_code=exc.status_code,
        detail=exc.detail,
        url=str(request.url),
        method=request.method
    )
    
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "message": exc.detail,
            "timestamp": datetime.now().isoformat()
        }
    )


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.reload,
        ssl_keyfile=settings.ssl_key_file,
        ssl_certfile=settings.ssl_cert_file,
        ssl_ca_certs=settings.client_ca_file,
        ssl_cert_reqs=2  # CERT_REQUIRED for mutual TLS
    )