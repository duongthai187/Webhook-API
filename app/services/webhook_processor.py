from typing import Dict, Any
import structlog
from datetime import datetime

from app.models import WebhookRequest

logger = structlog.get_logger()


class WebhookProcessor:
    """
    Service to process incoming webhook notifications from bank
    """
    
    def __init__(self):
        self.processed_transactions = set()  # Simple duplicate detection
        logger.info("webhook_processor_initialized")
    
    async def process_notification(self, webhook_data: WebhookRequest) -> Dict[str, Any]:
        """
        Process bank notification webhook
        
        Args:
            webhook_data: Validated webhook data from bank
            
        Returns:
            Dict containing processing result
        """
        try:
            # Log incoming notification
            logger.info(
                "processing_webhook_notification",
                transaction_id=webhook_data.transaction_id,
                account_number=webhook_data.account_number,
                amount=webhook_data.amount,
                transaction_type=webhook_data.transaction_type,
                timestamp=webhook_data.timestamp.isoformat()
            )
            
            # Check for duplicate transaction
            if await self._is_duplicate_transaction(webhook_data.transaction_id):
                logger.warning(
                    "duplicate_transaction_detected",
                    transaction_id=webhook_data.transaction_id
                )
                return {
                    "success": False,
                    "error": "Duplicate transaction",
                    "error_code": "DUPLICATE_TRANSACTION"
                }
            
            # Validate transaction data
            validation_result = await self._validate_transaction_data(webhook_data)
            if not validation_result["valid"]:
                logger.error(
                    "transaction_validation_failed",
                    transaction_id=webhook_data.transaction_id,
                    errors=validation_result["errors"]
                )
                return {
                    "success": False,
                    "error": f"Validation failed: {', '.join(validation_result['errors'])}",
                    "error_code": "VALIDATION_FAILED"
                }
            
            # Process the transaction
            processing_result = await self._process_transaction(webhook_data)
            if not processing_result["success"]:
                logger.error(
                    "transaction_processing_failed",
                    transaction_id=webhook_data.transaction_id,
                    error=processing_result["error"]
                )
                return processing_result
            
            # Mark transaction as processed
            self.processed_transactions.add(webhook_data.transaction_id)
            
            logger.info(
                "webhook_notification_processed_successfully",
                transaction_id=webhook_data.transaction_id,
                processing_time=processing_result.get("processing_time", 0)
            )
            
            return {
                "success": True,
                "transaction_id": webhook_data.transaction_id,
                "processing_time": processing_result.get("processing_time", 0),
                "message": "Transaction processed successfully"
            }
            
        except Exception as e:
            logger.error(
                "webhook_processing_exception",
                transaction_id=getattr(webhook_data, 'transaction_id', 'unknown'),
                error=str(e),
                exc_info=True
            )
            return {
                "success": False,
                "error": "Internal processing error",
                "error_code": "PROCESSING_ERROR"
            }
    
    async def _is_duplicate_transaction(self, transaction_id: str) -> bool:
        """
        Check if transaction has already been processed
        
        In a production environment, this should check against a database
        or distributed cache instead of in-memory set
        
        Args:
            transaction_id: Transaction ID to check
            
        Returns:
            bool: True if transaction is duplicate
        """
        return transaction_id in self.processed_transactions
    
    async def _validate_transaction_data(self, webhook_data: WebhookRequest) -> Dict[str, Any]:
        """
        Validate incoming transaction data
        
        Args:
            webhook_data: Webhook data to validate
            
        Returns:
            Dict with validation result
        """
        errors = []
        
        # Validate transaction ID format
        if not webhook_data.transaction_id or len(webhook_data.transaction_id) < 10:
            errors.append("Invalid transaction ID format")
        
        # Validate amount
        if webhook_data.amount <= 0:
            errors.append("Transaction amount must be positive")
        
        # Validate account number format (basic validation)
        if not webhook_data.account_number or len(webhook_data.account_number) < 8:
            errors.append("Invalid account number format")
        
        # Validate transaction type
        valid_types = ["debit", "credit", "transfer"]
        if webhook_data.transaction_type.lower() not in valid_types:
            errors.append(f"Invalid transaction type. Must be one of: {', '.join(valid_types)}")
        
        # Validate currency
        valid_currencies = ["VND", "USD", "EUR"]
        if webhook_data.currency and webhook_data.currency not in valid_currencies:
            errors.append(f"Invalid currency. Must be one of: {', '.join(valid_currencies)}")
        
        # Validate timestamp (not too old or in future)
        now = datetime.now()
        time_diff = abs((webhook_data.timestamp - now).total_seconds())
        if time_diff > 300:  # 5 minutes tolerance
            errors.append("Transaction timestamp is too old or in the future")
        
        return {
            "valid": len(errors) == 0,
            "errors": errors
        }
    
    async def _process_transaction(self, webhook_data: WebhookRequest) -> Dict[str, Any]:
        """
        Process the validated transaction
        
        This is where you would implement your business logic:
        - Update account balances
        - Create transaction records
        - Send notifications
        - Update external systems
        - etc.
        
        Args:
            webhook_data: Validated webhook data
            
        Returns:
            Dict with processing result
        """
        start_time = datetime.now()
        
        try:
            # Simulate processing time
            import asyncio
            await asyncio.sleep(0.1)  # Simulate database operations
            
            # Here you would implement actual business logic
            # For example:
            # - Update database records
            # - Call external APIs
            # - Send notifications
            # - Update account balances
            # - Create transaction logs
            
            processing_result = await self._simulate_business_logic(webhook_data)
            
            processing_time = (datetime.now() - start_time).total_seconds()
            
            logger.info(
                "transaction_business_logic_completed",
                transaction_id=webhook_data.transaction_id,
                processing_time=processing_time,
                result=processing_result["status"]
            )
            
            return {
                "success": True,
                "processing_time": processing_time,
                "business_result": processing_result
            }
            
        except Exception as e:
            processing_time = (datetime.now() - start_time).total_seconds()
            logger.error(
                "transaction_processing_error",
                transaction_id=webhook_data.transaction_id,
                error=str(e),
                processing_time=processing_time
            )
            
            return {
                "success": False,
                "error": f"Processing failed: {str(e)}",
                "processing_time": processing_time
            }
    
    async def _simulate_business_logic(self, webhook_data: WebhookRequest) -> Dict[str, Any]:
        """
        Simulate business logic processing
        
        In a real implementation, this would contain your actual business logic
        
        Args:
            webhook_data: Transaction data
            
        Returns:
            Dict with business processing result
        """
        # Simulate different processing based on transaction type
        if webhook_data.transaction_type.lower() == "credit":
            # Handle credit transaction
            return {
                "status": "credit_processed",
                "account_balance_updated": True,
                "notification_sent": True
            }
        elif webhook_data.transaction_type.lower() == "debit":
            # Handle debit transaction
            return {
                "status": "debit_processed",
                "account_balance_updated": True,
                "notification_sent": True
            }
        else:
            # Handle other transaction types
            return {
                "status": "transfer_processed",
                "account_balance_updated": True,
                "notification_sent": True
            }
    
    def get_processing_stats(self) -> Dict[str, Any]:
        """
        Get processing statistics
        
        Returns:
            Dict with processing statistics
        """
        return {
            "total_processed": len(self.processed_transactions),
            "service_status": "healthy"
        }