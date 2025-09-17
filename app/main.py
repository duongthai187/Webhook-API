import structlog
from datetime import datetime
from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
import time
import uvicorn

from app.models import WebhookRequest, WebhookResponse, TransactionResult
from app.middlewares.ip_whitelist import IPWhitelistMiddleware
from app.middlewares.rate_limit import RateLimitMiddleware
from app.middlewares.signature_verification import SignatureVerificationMiddleware
# from app.middlewares.bank_certificate import BankCertificateMiddleware  # Optional: for cert-based auth
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
    title="Bank Webhook Notify",
    description="Secure webhook endpoint for receiving bank notifications",
    version="1.0.0",
    docs_url="/docs" if settings.reload else None,  # Disable docs in production
    # redoc_url=None
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
        "Request received",
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
            batch_id=webhook_data.batch_id,
            source_app_id=webhook_data.source_app_id,
            transaction_count=len(webhook_data.data),
            timestamp=webhook_data.timestamp
        )
        
        # Process webhook data
        result = await webhook_processor.process_notification(webhook_data)
        
        # Create response data array với kết quả từng transaction
        response_data = []
        
        # Xử lý các transaction thành công
        for transaction in webhook_data.data:
            transaction_found = False
            
            # Kiểm tra nếu transaction bị failed
            for failed_tx in result.get("failed_transactions", []):
                if failed_tx["transaction_id"] == transaction.transaction_id:
                    # Determine error code based on error type
                    error_code = "04"  # Default: thất bại có lý do
                    additional_info = {"error_detail": failed_tx["error"]}
                    
                    if "Duplicate transaction" in failed_tx["error"]:
                        error_code = "02"  # Thất bại không chi tiết
                        additional_info = {"reason": "duplicate_transaction"}
                    elif "Validation failed" in failed_tx["error"]:
                        error_code = "04"  # Thất bại có lý do
                        additional_info = {"validation_errors": failed_tx["error"]}
                    
                    response_data.append({
                        "transactionId": transaction.transaction_id,
                        "errorCode": error_code,
                        "description": failed_tx["error"],
                        "additionalInfo": additional_info
                    })
                    transaction_found = True
                    break
            
            # Nếu không có trong failed list, nghĩa là thành công
            if not transaction_found:
                response_data.append({
                    "transactionId": transaction.transaction_id,
                    "errorCode": "01",  # Thành công
                    "description": "Transaction processed successfully",
                    "additionalInfo": {}
                })
        
        # Determine overall response code
        overall_success = result["success"]
        response_code = "200" if overall_success else "400"
        response_message = "Success" if overall_success else "Some transactions failed"
        
        logger.info(
            "webhook_processed",
            batch_id=webhook_data.batch_id,
            processed_count=result.get("processed_count", 0),
            failed_count=result.get("failed_count", 0),
            overall_success=overall_success
        )
        
        return WebhookResponse(
            batch_id=webhook_data.batch_id,
            code=response_code,
            message=response_message,
            data=response_data
        )
            
    except Exception as e:
        logger.error(
            "webhook_error",
            batch_id=getattr(webhook_data, 'batch_id', 'unknown'),
            error=str(e),
            exc_info=True
        )
        
        # Return error response in required format
        error_data = []
        if hasattr(webhook_data, 'data'):
            for transaction in webhook_data.data:
                error_data.append({
                    "transactionId": transaction.transaction_id,
                    "errorCode": "02",  # Thất bại không chi tiết
                    "description": "Internal server error",
                    "additionalInfo": {"error": "system_error"}
                })
        
        return WebhookResponse(
            batch_id=getattr(webhook_data, 'batch_id', 'unknown'),
            code="500",
            message="Internal server error",
            data=error_data
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
    
    # For webhook endpoints, return in required format
    if request.url.path.startswith("/webhook/"):
        # Try to get batch_id from request if possible
        batch_id = "unknown"
        try:
            if request.method == "POST":
                # This is a simplified approach - in real scenario you might need to parse body
                batch_id = "error_batch"
        except:
            pass
            
        return JSONResponse(
            status_code=200,  # Always return 200 for webhook responses as per bank requirement
            content={
                "batchId": batch_id,
                "code": str(exc.status_code),
                "message": exc.detail,
                "data": []
            }
        )
    
    # For other endpoints, return standard format
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "message": exc.detail,
            "timestamp": datetime.now().isoformat()
        }
    )


if __name__ == "__main__":
    
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.reload,
    )