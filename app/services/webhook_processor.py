from typing import Dict, Any
import structlog
from datetime import datetime, timedelta
import asyncio
import json
import os
import sqlite3
from pathlib import Path

from app.models import WebhookRequest, TransactionData

logger = structlog.get_logger()


class WebhookProcessor:

    def __init__(self, db_path: str = "webhook_metrics.db"):
        self.db_path = db_path
        self.processed_transactions = set()  # In-memory cache for fast lookup
        # Setup webhook storage directory
        self.webhook_storage_dir = Path("webhook_notifications")
        self.webhook_storage_dir.mkdir(exist_ok=True)
        
        # Initialize persistent storage for processed transactions
        self._init_processed_transactions_db()
        
        # Load processed transactions from database into memory
        self._load_processed_transactions()
        
        logger.info("Khởi tạo WebhookProcessor thành công", 
                   storage_dir=str(self.webhook_storage_dir),
                   loaded_transactions=len(self.processed_transactions))
    
    def _init_processed_transactions_db(self):
        """Initialize database table for storing processed transaction IDs"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Table to track processed transactions with cleanup capability
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS processed_transactions (
                    transaction_id TEXT PRIMARY KEY,
                    processed_at TEXT NOT NULL,
                    batch_id TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Index for performance
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_processed_transactions_processed_at 
                ON processed_transactions(processed_at)
            ''')
            
            conn.commit()
            conn.close()
            logger.info("Database table 'processed_transactions' đã được khởi tạo")
            
        except Exception as e:
            logger.error("Lỗi khởi tạo database table processed_transactions", error=str(e))
            raise
    
    def _load_processed_transactions(self):
        """Load processed transaction IDs from database into memory cache"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Load transactions processed in last 30 days (configurable)
            cutoff_date = (datetime.now() - timedelta(days=30)).isoformat()
            
            cursor.execute('''
                SELECT transaction_id FROM processed_transactions 
                WHERE processed_at >= ? 
                ORDER BY processed_at DESC
            ''', (cutoff_date,))
            
            rows = cursor.fetchall()
            self.processed_transactions = {row[0] for row in rows}
            
            conn.close()
            logger.info(f"Đã load {len(self.processed_transactions)} processed transactions từ database")
            
        except Exception as e:
            logger.error("Lỗi load processed transactions từ database", error=str(e))
            self.processed_transactions = set()  # Fallback to empty set
    
    async def _save_processed_transaction(self, transaction_id: str, batch_id: str):
        """Save processed transaction ID to database for persistence"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT OR REPLACE INTO processed_transactions 
                (transaction_id, processed_at, batch_id) 
                VALUES (?, ?, ?)
            ''', (transaction_id, datetime.now().isoformat(), batch_id))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error("Lỗi lưu processed transaction vào database", 
                        transaction_id=transaction_id, 
                        batch_id=batch_id,
                        error=str(e))
            # Don't raise exception to avoid breaking the main process
    
    async def process_notification(self, webhook_data: WebhookRequest) -> Dict[str, Any]:
        try:
            # Save webhook notification to file first
            await self._save_webhook_to_file(webhook_data)
            
            # Log incoming notification batch
            logger.info(
                "Xử lý webhook batch",
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
                            "Phát hiện giao dịch trùng lặp, bỏ qua",
                            transaction_id=transaction.transaction_id,
                            batch_id=webhook_data.batch_id
                        )
                        failed_transactions.append({
                            "transaction_id": transaction.transaction_id,
                            "error": "Giao dịch trùng lặp"
                        })
                        continue
                    
                    # Validate transaction data
                    validation_result = await self._validate_transaction_data(transaction)
                    if not validation_result["valid"]:
                        logger.error(
                            "Failed_transaction_validation (process_notification)",
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
                            "Lỗi xử lý transaction (process_notification trace1)",
                            transaction_id=transaction.transaction_id,
                            batch_id=webhook_data.batch_id,
                            error=processing_result["error"]
                        )
                        failed_transactions.append({
                            "transaction_id": transaction.transaction_id,
                            "error": processing_result["error"]
                        })
                        continue
                    
                    # Mark transaction as processed - save to both memory and database
                    self.processed_transactions.add(transaction.transaction_id)
                    await self._save_processed_transaction(transaction.transaction_id, webhook_data.batch_id)
                    processed_count += 1
                    
                except Exception as e:
                    logger.error(
                        "Lỗi xử lý transaction (process_notification trace2)",
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
        return transaction_id in self.processed_transactions
    
    async def cleanup_old_processed_transactions(self, days_to_keep: int = 30):
        """Clean up old processed transaction records to prevent database bloat"""
        try:
            cutoff_date = (datetime.now() - timedelta(days=days_to_keep)).isoformat()
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Count records to be deleted
            cursor.execute('''
                SELECT COUNT(*) FROM processed_transactions 
                WHERE processed_at < ?
            ''', (cutoff_date,))
            
            count_to_delete = cursor.fetchone()[0]
            
            # Delete old records
            cursor.execute('''
                DELETE FROM processed_transactions 
                WHERE processed_at < ?
            ''', (cutoff_date,))
            
            conn.commit()
            conn.close()
            
            # Also clean up in-memory cache
            self._load_processed_transactions()
            
            logger.info(f"Đã cleanup {count_to_delete} processed transactions cũ hơn {days_to_keep} ngày")
            
        except Exception as e:
            logger.error("Lỗi cleanup processed transactions", error=str(e))
    
    def get_processed_transactions_stats(self) -> Dict[str, Any]:
        """Get statistics about processed transactions"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Count total records in database
            cursor.execute('SELECT COUNT(*) FROM processed_transactions')
            total_in_db = cursor.fetchone()[0]
            
            # Count by date ranges
            now = datetime.now()
            today = now.date().isoformat()
            last_7_days = (now - timedelta(days=7)).isoformat()
            last_30_days = (now - timedelta(days=30)).isoformat()
            
            cursor.execute('SELECT COUNT(*) FROM processed_transactions WHERE processed_at >= ?', (today,))
            today_count = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM processed_transactions WHERE processed_at >= ?', (last_7_days,))
            week_count = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM processed_transactions WHERE processed_at >= ?', (last_30_days,))
            month_count = cursor.fetchone()[0]
            
            conn.close()
            
            return {
                "total_in_memory": len(self.processed_transactions),
                "total_in_database": total_in_db,
                "processed_today": today_count,
                "processed_last_7_days": week_count,
                "processed_last_30_days": month_count
            }
            
        except Exception as e:
            logger.error("Lỗi lấy stats processed transactions", error=str(e))
            return {
                "total_in_memory": len(self.processed_transactions),
                "total_in_database": 0,
                "error": str(e)
            }
    
    async def _validate_transaction_data(self, transaction_data: TransactionData) -> Dict[str, Any]:

        errors = []
        
        # Validate transaction ID format
        if not transaction_data.transaction_id or len(transaction_data.transaction_id) < 10:
            errors.append("Transaction ID không hợp lệ")
        
        # Validate amount
        if transaction_data.amount <= 0:
            errors.append("Số tiền giao dịch phải dương")
        
        # Validate account number format (basic validation)
        if not transaction_data.src_account_number or len(transaction_data.src_account_number) < 8:
            errors.append("Định dạng số tài khoản nguồn không hợp lệ")

        # Validate transaction type
        valid_types = ["D", "C"]  # Debit, Credit
        if transaction_data.trans_type not in valid_types:
            errors.append(f"Loại giao dịch không hợp lệ. Phải là một trong số: {', '.join(valid_types)}")
        
        # Validate balance if provided
        if transaction_data.balance_available is not None and transaction_data.balance_available < 0:
            errors.append("Số dư khả dụng không được âm")

        return {
            "valid": len(errors) == 0,
            "errors": errors
        }
    
    async def _process_transaction(self, transaction_data: TransactionData, batch_id: str) -> Dict[str, Any]:
        start_time = datetime.now()
        
        try:            
            # Here you would implement actual business logic
            processing_result = await self._simulate_business_logic(transaction_data, batch_id)
            
            processing_time = (datetime.now() - start_time).total_seconds()
            
            logger.info(
                "Xử lý logic hoàn tất (process_transaction)",
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
                "Lỗi xử lý logic (process_transaction)",
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
        basic_stats = {
            "total_processed": len(self.processed_transactions),
            "service_status": "healthy"
        }
        
        # Add detailed stats
        detailed_stats = self.get_processed_transactions_stats()
        basic_stats.update(detailed_stats)
        
        return basic_stats
    
    async def _save_webhook_to_file(self, webhook_data: WebhookRequest):
        try:
            # Create filename with timestamp and batch_id
            timestamp = datetime.now()
            date_folder = self.webhook_storage_dir / timestamp.strftime("%Y%m%d")
            date_folder.mkdir(exist_ok=True)
            
            # Filename format: YYYYMMDD_HHMMSS_batchId.json
            filename = f"{timestamp.strftime('%Y%m%d_%H%M%S')}_{webhook_data.batch_id}.json"
            file_path = date_folder / filename
            
            # Convert webhook data to dict for JSON serialization
            webhook_dict = {
                "received_at": timestamp.isoformat(),
                "batch_id": webhook_data.batch_id,
                "source_app_id": webhook_data.source_app_id,
                "timestamp": webhook_data.timestamp,
                "data": [
                    {
                        "transaction_id": tx.transaction_id,
                        "tran_refno": tx.tran_refno,
                        "src_account_number": tx.src_account_number,
                        "amount": tx.amount,
                        "balance_available": tx.balance_available,
                        "trans_type": tx.trans_type,
                        "notice_date_time": tx.notice_date_time,
                        "trans_time": tx.trans_time,
                        "trans_desc": tx.trans_desc,
                        "ofs_account_number": tx.ofs_account_number,
                        "ofs_account_name": tx.ofs_account_name,
                        "ofs_bank_id": tx.ofs_bank_id,
                        "ofs_bank_name": tx.ofs_bank_name,
                        "is_virtual_trans": tx.is_virtual_trans,
                        "virtual_acc": tx.virtual_acc
                    }
                    for tx in webhook_data.data
                ],
                "transaction_count": len(webhook_data.data)
            }
            
            # Write to file with pretty formatting
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(webhook_dict, f, indent=2, ensure_ascii=False)
            
            logger.info(
                "Đã lưu backup webhook notification",
                batch_id=webhook_data.batch_id,
                file_path=str(file_path),
                transaction_count=len(webhook_data.data)
            )
            
        except Exception as e:
            # Don't fail the entire process if file saving fails
            logger.error(
                "Lỗi khi lưu backup webhook notification",
                batch_id=getattr(webhook_data, 'batch_id', 'unknown'),
                error=str(e),
                exc_info=True
            )