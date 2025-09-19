import structlog
from datetime import datetime
from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST, REGISTRY
import time
import uvicorn

from app.models import WebhookRequest, WebhookResponse, TransactionResult
from app.middlewares.ip_whitelist import IPWhitelistMiddleware
from app.middlewares.rate_limit import RateLimitMiddleware
from app.middlewares.signature_verification import SignatureVerificationMiddleware
# from app.middlewares.bank_certificate import BankCertificateMiddleware  # Optional: for cert-based auth
from app.services.webhook_processor import WebhookProcessor
from app.services.metrics_collector import get_metrics_collector
from app.config.settings import settings

# Initialize structured logger
logger = structlog.get_logger()

# Clear any existing metrics to prevent duplicates
REGISTRY._collector_to_names.clear()
REGISTRY._names_to_collectors.clear()

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

# Add CORS middleware - mostly for dashboard access, not webhook security
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8501",   # Dashboard
        "http://127.0.0.1:8501"
    ],
    allow_credentials=False,      # Dashboard doesn't need credentials
    allow_methods=["GET", "POST"],  
    allow_headers=["*"],
)

# Add custom middlewares
app.add_middleware(RateLimitMiddleware)
app.add_middleware(IPWhitelistMiddleware)
app.add_middleware(SignatureVerificationMiddleware)

# Initialize webhook processor with database path
webhook_processor = WebhookProcessor(db_path="webhook_metrics.db")

# Initialize metrics collector
metrics_collector = get_metrics_collector()


# @app.middleware("http")
# async def add_proxy_headers(request: Request, call_next):
#     """Handle reverse proxy headers for production deployment"""
#     # Handle reverse proxy headers
#     forwarded_proto = request.headers.get("X-Forwarded-Proto")
#     if forwarded_proto:
#         request.scope["scheme"] = forwarded_proto
    
#     forwarded_host = request.headers.get("X-Forwarded-Host")
#     if forwarded_host:
#         port = 443 if forwarded_proto == "https" else 80
#         request.scope["server"] = (forwarded_host, port)
    
#     # Get real client IP from proxy headers
#     real_ip = (
#         request.headers.get("X-Forwarded-For", "").split(",")[0].strip() or
#         request.headers.get("X-Real-IP") or
#         request.client.host if request.client else "unknown"
#     )
    
#     # Update client info for downstream middlewares
#     if request.client:
#         # Store original client info
#         request.scope["client"] = (real_ip, request.client.port)
    
#     return await call_next(request)


@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    """Add processing time and logging middleware"""
    start_time = time.time()
    
    # Get real client IP (after proxy middleware processing)
    client_ip = request.client.host if request.client else "unknown"
    
    # Log incoming request
    logger.info(
        "Request received",
        method=request.method,
        url=str(request.url),
        client_ip=client_ip,
        user_agent=request.headers.get("user-agent", ""),
        forwarded_proto=request.headers.get("X-Forwarded-Proto"),
        forwarded_host=request.headers.get("X-Forwarded-Host")
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
        process_time=process_time,
        client_ip=client_ip
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


@app.get("/api/metrics/summary")
async def get_metrics_summary():
    """Get metrics summary for dashboard"""
    try:
        summary = metrics_collector.get_summary_stats()
        return JSONResponse(content=summary)
    except Exception as e:
        logger.error("Failed to get metrics summary", error=str(e))
        return JSONResponse(
            status_code=500,
            content={"error": "Failed to get metrics summary", "detail": str(e)}
        )


@app.get("/api/metrics/webhooks")
async def get_webhook_metrics(hours: int = 24, limit: int = 100):
    """Get recent webhook metrics for dashboard"""
    try:
        if hours <= 1:
            # For recent data, use in-memory cache
            metrics = metrics_collector.get_recent_webhooks(limit=limit)
        else:
            # For historical data, use database
            metrics = metrics_collector.get_webhook_metrics_from_db(hours=hours)[:limit]
        
        return JSONResponse(content={"metrics": metrics, "count": len(metrics)})
    except Exception as e:
        logger.error("Failed to get webhook metrics", error=str(e))
        return JSONResponse(
            status_code=500,
            content={"error": "Failed to get webhook metrics", "detail": str(e)}
        )


@app.get("/api/metrics/system")
async def get_system_metrics(hours: int = 1):
    """Get system metrics for dashboard"""
    try:
        if hours <= 1:
            # For recent data, use in-memory cache
            minutes = min(hours * 60, 60)
            metrics = metrics_collector.get_recent_system_metrics(minutes=minutes)
        else:
            # For historical data, use database
            metrics = metrics_collector.get_system_metrics_from_db(hours=hours)
        
        return JSONResponse(content={"metrics": metrics, "count": len(metrics)})
    except Exception as e:
        logger.error("Failed to get system metrics", error=str(e))
        return JSONResponse(
            status_code=500,
            content={"error": "Failed to get system metrics", "detail": str(e)}
        )


@app.get("/api/metrics/hourly")
async def get_hourly_stats(hours: int = 24):
    """Get hourly webhook statistics"""
    try:
        stats = metrics_collector.get_hourly_stats(hours=hours)
        return JSONResponse(content={"hourly_stats": stats})
    except Exception as e:
        logger.error("Failed to get hourly stats", error=str(e))
        return JSONResponse(
            status_code=500,
            content={"error": "Failed to get hourly stats", "detail": str(e)}
        )


@app.get("/api/analysis/webhook-files")
async def get_webhook_file_analysis():
    """Get analysis of webhook notification files"""
    try:
        analysis = metrics_collector.analyze_webhook_files()
        return JSONResponse(content={"analysis": analysis})
    except Exception as e:
        logger.error("Failed to analyze webhook files", error=str(e))
        return JSONResponse(
            status_code=500,
            content={"error": "Failed to analyze webhook files", "detail": str(e)}
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
        start_time = datetime.now()
        
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
        
        # Record metrics for dashboard
        process_time = (datetime.now() - start_time).total_seconds()
        metrics_collector.record_webhook_event(
            batch_id=webhook_data.batch_id,
            source_app_id=webhook_data.source_app_id,
            transaction_count=len(webhook_data.data),
            processed_count=result.get("processed_count", 0),
            failed_count=result.get("failed_count", 0),
            process_time=process_time,
            status_code=200 if overall_success else 400,
            client_ip=request.client.host if request.client else "unknown"
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


@app.get("/admin/processed-transactions/stats")
async def get_processed_transactions_stats():
    """Get statistics about processed transactions"""
    try:
        stats = webhook_processor.get_processing_stats()
        return {
            "success": True,
            "data": stats,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error("Error getting processed transactions stats", error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/admin/processed-transactions/cleanup")
async def cleanup_processed_transactions(days_to_keep: int = 30):
    """Clean up old processed transactions"""
    try:
        if days_to_keep < 1:
            raise HTTPException(status_code=400, detail="days_to_keep must be >= 1")
            
        await webhook_processor.cleanup_old_processed_transactions(days_to_keep)
        
        # Get updated stats
        stats = webhook_processor.get_processing_stats()
        
        return {
            "success": True,
            "message": f"Cleaned up transactions older than {days_to_keep} days",
            "updated_stats": stats,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error("Error cleaning up processed transactions", error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")


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