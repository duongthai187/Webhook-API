from typing import Dict, Any
import structlog
from datetime import datetime

from app.models import WebhookRequest, TransactionData

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
        Process bank notification webhook batch
        
        Args:
            webhook_data: Validated webhook data from bank
            
        Returns:
            Dict containing processing result
        """
        try:
            # Log incoming notification batch
            logger.info(
                "processing_webhook_batch",
                batch_id=webhook_data.batch_id,
                source_app_id=webhook_data.source_app_id,
                transaction_count=len(webhook_data.data),
                timestamp=webhook_data.timestamp
            )
            
            processed_count = 0
            failed_transactions = []
            
            # Process each transaction in the batch
            for transaction in webhook_data.data:
                try:
                    # Check for duplicate transaction
                    if await self._is_duplicate_transaction(transaction.transaction_id):
                        logger.warning(
                            "duplicate_transaction_detected",
                            transaction_id=transaction.transaction_id,
                            batch_id=webhook_data.batch_id
                        )
                        failed_transactions.append({
                            "transaction_id": transaction.transaction_id,
                            "error": "Duplicate transaction"
                        })
                        continue
                    
                    # Validate transaction data
                    validation_result = await self._validate_transaction_data(transaction)
                    if not validation_result["valid"]:
                        logger.error(
                            "transaction_validation_failed",
                            transaction_id=transaction.transaction_id,
                            batch_id=webhook_data.batch_id,
                            errors=validation_result["errors"]
                        )
                        failed_transactions.append({
                            "transaction_id": transaction.transaction_id,
                            "error": f"Validation failed: {', '.join(validation_result['errors'])}"
                        })
                        continue
                    
                    # Process the individual transaction
                    processing_result = await self._process_transaction(transaction, webhook_data.batch_id)
                    if not processing_result["success"]:
                        logger.error(
                            "transaction_processing_failed",
                            transaction_id=transaction.transaction_id,
                            batch_id=webhook_data.batch_id,
                            error=processing_result["error"]
                        )
                        failed_transactions.append({
                            "transaction_id": transaction.transaction_id,
                            "error": processing_result["error"]
                        })
                        continue
                    
                    # Mark transaction as processed
                    self.processed_transactions.add(transaction.transaction_id)
                    processed_count += 1
                    
                except Exception as e:
                    logger.error(
                        "transaction_processing_exception",
                        transaction_id=transaction.transaction_id,
                        batch_id=webhook_data.batch_id,
                        error=str(e),
                        exc_info=True
                    )
                    failed_transactions.append({
                        "transaction_id": transaction.transaction_id,
                        "error": f"Processing exception: {str(e)}"
                    })
            
            # Determine overall success
            total_transactions = len(webhook_data.data)
            success_rate = processed_count / total_transactions if total_transactions > 0 else 0
            
            logger.info(
                "webhook_batch_processed",
                batch_id=webhook_data.batch_id,
                total_transactions=total_transactions,
                processed_count=processed_count,
                failed_count=len(failed_transactions),
                success_rate=success_rate
            )
            
            return {
                "success": len(failed_transactions) == 0,  # Success only if all transactions processed
                "processed_count": processed_count,
                "failed_count": len(failed_transactions),
                "failed_transactions": failed_transactions,
                "batch_id": webhook_data.batch_id
            }
            
        except Exception as e:
            logger.error(
                "webhook_batch_processing_exception",
                batch_id=getattr(webhook_data, 'batch_id', 'unknown'),
                error=str(e),
                exc_info=True
            )
            return {
                "success": False,
                "error": "Batch processing error",
                "error_code": "BATCH_PROCESSING_ERROR",
                "processed_count": 0
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
    
    async def _validate_transaction_data(self, transaction_data: TransactionData) -> Dict[str, Any]:
        """
        Validate incoming transaction data
        
        Args:
            transaction_data: Individual transaction data to validate
            
        Returns:
            Dict with validation result
        """
        errors = []
        
        # Validate transaction ID format
        if not transaction_data.transaction_id or len(transaction_data.transaction_id) < 10:
            errors.append("Invalid transaction ID format")
        
        # Validate amount
        if transaction_data.amount <= 0:
            errors.append("Transaction amount must be positive")
        
        # Validate account number format (basic validation)
        if not transaction_data.src_account_number or len(transaction_data.src_account_number) < 8:
            errors.append("Invalid source account number format")
        
        # Validate transaction type
        valid_types = ["D", "C"]  # Debit, Credit
        if transaction_data.trans_type not in valid_types:
            errors.append(f"Invalid transaction type. Must be one of: {', '.join(valid_types)}")
        
        # Validate balance if provided
        if transaction_data.balance_available is not None and transaction_data.balance_available < 0:
            errors.append("Balance available cannot be negative")
        
        return {
            "valid": len(errors) == 0,
            "errors": errors
        }
    
    async def _process_transaction(self, transaction_data: TransactionData, batch_id: str) -> Dict[str, Any]:
        """
        Process the validated transaction
        
        This is where you would implement your business logic:
        - Update account balances
        - Create transaction records
        - Send notifications
        - Update external systems
        - etc.
        
        Args:
            transaction_data: Validated transaction data
            batch_id: Batch ID for reference
            
        Returns:
            Dict with processing result
        """
        start_time = datetime.now()
        
        try:
            # Simulate processing time
            import asyncio
            await asyncio.sleep(0.1)  # Simulate database operations
            
            # Here you would implement actual business logic
            processing_result = await self._simulate_business_logic(transaction_data, batch_id)
            
            processing_time = (datetime.now() - start_time).total_seconds()
            
            logger.info(
                "transaction_business_logic_completed",
                transaction_id=transaction_data.transaction_id,
                batch_id=batch_id,
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
                transaction_id=transaction_data.transaction_id,
                batch_id=batch_id,
                error=str(e),
                processing_time=processing_time
            )
            
            return {
                "success": False,
                "error": f"Processing failed: {str(e)}",
                "processing_time": processing_time
            }
    
    async def _simulate_business_logic(self, transaction_data: TransactionData, batch_id: str) -> Dict[str, Any]:
        """
        Simulate business logic processing
        
        In a real implementation, this would contain your actual business logic
        
        Args:
            transaction_data: Transaction data
            batch_id: Batch ID for reference
            
        Returns:
            Dict with business processing result
        """
        # Simulate different processing based on transaction type
        if transaction_data.trans_type == "C":  # Credit
            return {
                "status": "credit_processed",
                "account_balance_updated": True,
                "notification_sent": True,
                "batch_id": batch_id
            }
        elif transaction_data.trans_type == "D":  # Debit
            return {
                "status": "debit_processed",
                "account_balance_updated": True,
                "notification_sent": True,
                "batch_id": batch_id
            }
        else:
            return {
                "status": "unknown_type_processed",
                "account_balance_updated": False,
                "notification_sent": False,
                "batch_id": batch_id
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