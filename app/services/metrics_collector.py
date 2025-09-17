import json
import sqlite3
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional
import structlog
from dataclasses import dataclass, asdict
from collections import defaultdict, deque
import threading
import time
import psutil

logger = structlog.get_logger()

@dataclass
class WebhookMetric:
    timestamp: str
    batch_id: str
    source_app_id: str
    transaction_count: int
    processed_count: int
    failed_count: int
    process_time: float
    status_code: int
    client_ip: str
    error_message: Optional[str] = None

@dataclass
class SystemMetric:
    timestamp: str
    cpu_percent: float
    memory_percent: float
    disk_usage_percent: float
    network_bytes_sent: int
    network_bytes_recv: int


class MetricsCollector:
    
    def __init__(self, db_path: str = "webhook_metrics.db"):
        self.db_path = db_path
        self.webhook_notifications_dir = Path("webhook_notifications")
        self.webhook_notifications_dir.mkdir(exist_ok=True)
        
        # In-memory caches for recent data
        self.recent_webhooks = deque(maxlen=1000)  # Last 1000 webhooks
        self.recent_system_metrics = deque(maxlen=1440)  # 24 hours of minute data
        self.hourly_stats = defaultdict(lambda: {"total": 0, "success": 0, "failed": 0, "avg_process_time": 0})
        
        # Thread safety
        self._lock = threading.Lock()
        
        # Initialize database
        self._init_database()
        
        # Start system metrics collection thread
        self._start_system_monitoring()
        
        logger.info("MetricsCollector initialized", db_path=db_path)
    
    def _init_database(self):
        """Initialize SQLite database with required tables"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Webhook metrics table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS webhook_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    batch_id TEXT,
                    source_app_id TEXT,
                    transaction_count INTEGER,
                    processed_count INTEGER,
                    failed_count INTEGER,
                    process_time REAL,
                    status_code INTEGER,
                    client_ip TEXT,
                    error_message TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # System metrics table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS system_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    cpu_percent REAL,
                    memory_percent REAL,
                    disk_usage_percent REAL,
                    network_bytes_sent INTEGER,
                    network_bytes_recv INTEGER,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Create indexes for better query performance
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_webhook_timestamp ON webhook_metrics(timestamp)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_system_timestamp ON system_metrics(timestamp)')
            
            conn.commit()
            conn.close()
            
            logger.info("Database initialized successfully")
            
        except Exception as e:
            logger.error("Failed to initialize database", error=str(e))
    
    def record_webhook_event(self, 
                           batch_id: str,
                           source_app_id: str,
                           transaction_count: int,
                           processed_count: int,
                           failed_count: int,
                           process_time: float,
                           status_code: int,
                           client_ip: str,
                           error_message: str = None):
        """Record a webhook processing event"""
        
        metric = WebhookMetric(
            timestamp=datetime.now().isoformat(),
            batch_id=batch_id,
            source_app_id=source_app_id,
            transaction_count=transaction_count,
            processed_count=processed_count,
            failed_count=failed_count,
            process_time=process_time,
            status_code=status_code,
            client_ip=client_ip,
            error_message=error_message
        )
        
        with self._lock:
            # Add to recent cache
            self.recent_webhooks.append(metric)
            
            # Update hourly stats
            hour_key = datetime.now().strftime("%Y-%m-%d %H")
            stats = self.hourly_stats[hour_key]
            stats["total"] += 1
            if status_code == 200 and failed_count == 0:
                stats["success"] += 1
            else:
                stats["failed"] += 1
            
            # Calculate rolling average process time
            if stats["total"] == 1:
                stats["avg_process_time"] = process_time
            else:
                stats["avg_process_time"] = (stats["avg_process_time"] * (stats["total"] - 1) + process_time) / stats["total"]
        
        # Store in database (async)
        threading.Thread(target=self._store_webhook_metric, args=(metric,), daemon=True).start()
        
        logger.info("Webhook metric recorded", 
                   batch_id=batch_id, 
                   status_code=status_code,
                   process_time=process_time)
    
    def _store_webhook_metric(self, metric: WebhookMetric):
        """Store webhook metric in database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO webhook_metrics 
                (timestamp, batch_id, source_app_id, transaction_count, 
                 processed_count, failed_count, process_time, status_code, 
                 client_ip, error_message)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                metric.timestamp, metric.batch_id, metric.source_app_id,
                metric.transaction_count, metric.processed_count, metric.failed_count,
                metric.process_time, metric.status_code, metric.client_ip,
                metric.error_message
            ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error("Failed to store webhook metric", error=str(e))
    
    def _start_system_monitoring(self):
        """Start background system metrics collection"""
        def collect_system_metrics():
            while True:
                try:
                    # Collect system metrics
                    cpu_percent = psutil.cpu_percent(interval=1)
                    memory = psutil.virtual_memory()
                    disk = psutil.disk_usage('/')
                    net_io = psutil.net_io_counters()
                    
                    metric = SystemMetric(
                        timestamp=datetime.now().isoformat(),
                        cpu_percent=cpu_percent,
                        memory_percent=memory.percent,
                        disk_usage_percent=disk.percent,
                        network_bytes_sent=net_io.bytes_sent,
                        network_bytes_recv=net_io.bytes_recv
                    )
                    
                    with self._lock:
                        self.recent_system_metrics.append(metric)
                    
                    # Store in database
                    self._store_system_metric(metric)
                    
                    # Sleep for 60 seconds (collect every minute)
                    time.sleep(60)
                    
                except Exception as e:
                    logger.error("Error collecting system metrics", error=str(e))
                    time.sleep(60)
        
        thread = threading.Thread(target=collect_system_metrics, daemon=True)
        thread.start()
        logger.info("System monitoring thread started")
    
    def _store_system_metric(self, metric: SystemMetric):
        """Store system metric in database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO system_metrics 
                (timestamp, cpu_percent, memory_percent, disk_usage_percent,
                 network_bytes_sent, network_bytes_recv)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                metric.timestamp, metric.cpu_percent, metric.memory_percent,
                metric.disk_usage_percent, metric.network_bytes_sent,
                metric.network_bytes_recv
            ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error("Failed to store system metric", error=str(e))
    
    def get_recent_webhooks(self, limit: int = 50) -> List[Dict]:
        """Get recent webhook events"""
        with self._lock:
            recent = list(self.recent_webhooks)[-limit:]
            return [asdict(webhook) for webhook in recent]
    
    def get_recent_system_metrics(self, minutes: int = 60) -> List[Dict]:
        """Get recent system metrics"""
        with self._lock:
            recent = list(self.recent_system_metrics)[-minutes:]
            return [asdict(metric) for metric in recent]
    
    def get_hourly_stats(self, hours: int = 24) -> Dict[str, Dict]:
        """Get hourly webhook statistics"""
        with self._lock:
            # Get recent hours
            now = datetime.now()
            recent_hours = {}
            
            for i in range(hours):
                hour = (now - timedelta(hours=i)).strftime("%Y-%m-%d %H")
                stats = self.hourly_stats.get(hour, {"total": 0, "success": 0, "failed": 0, "avg_process_time": 0})
                recent_hours[hour] = stats
            
            return recent_hours
    
    def get_webhook_metrics_from_db(self, hours: int = 24) -> List[Dict]:
        """Get webhook metrics from database for specified hours"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cutoff_time = (datetime.now() - timedelta(hours=hours)).isoformat()
            
            cursor.execute('''
                SELECT * FROM webhook_metrics 
                WHERE timestamp >= ?
                ORDER BY timestamp DESC
                LIMIT 1000
            ''', (cutoff_time,))
            
            rows = cursor.fetchall()
            columns = [desc[0] for desc in cursor.description]
            
            conn.close()
            
            return [dict(zip(columns, row)) for row in rows]
            
        except Exception as e:
            logger.error("Failed to fetch webhook metrics from database", error=str(e))
            return []
    
    def get_system_metrics_from_db(self, hours: int = 24) -> List[Dict]:
        """Get system metrics from database for specified hours"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cutoff_time = (datetime.now() - timedelta(hours=hours)).isoformat()
            
            cursor.execute('''
                SELECT * FROM system_metrics 
                WHERE timestamp >= ?
                ORDER BY timestamp DESC
                LIMIT 1440
            ''', (cutoff_time,))
            
            rows = cursor.fetchall()
            columns = [desc[0] for desc in cursor.description]
            
            conn.close()
            
            return [dict(zip(columns, row)) for row in rows]
            
        except Exception as e:
            logger.error("Failed to fetch system metrics from database", error=str(e))
            return []
    
    def get_summary_stats(self) -> Dict[str, Any]:
        """Get overall summary statistics"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get stats for last 24 hours
            cutoff_time = (datetime.now() - timedelta(hours=24)).isoformat()
            
            # Webhook stats
            cursor.execute('''
                SELECT 
                    COUNT(*) as total_requests,
                    SUM(CASE WHEN status_code = 200 AND failed_count = 0 THEN 1 ELSE 0 END) as successful_requests,
                    SUM(transaction_count) as total_transactions,
                    SUM(processed_count) as processed_transactions,
                    SUM(failed_count) as failed_transactions,
                    AVG(process_time) as avg_process_time,
                    MAX(process_time) as max_process_time
                FROM webhook_metrics 
                WHERE timestamp >= ?
            ''', (cutoff_time,))
            
            webhook_stats = cursor.fetchone()
            
            # System stats (average for last hour)
            one_hour_ago = (datetime.now() - timedelta(hours=1)).isoformat()
            cursor.execute('''
                SELECT 
                    AVG(cpu_percent) as avg_cpu,
                    AVG(memory_percent) as avg_memory,
                    AVG(disk_usage_percent) as avg_disk
                FROM system_metrics 
                WHERE timestamp >= ?
            ''', (one_hour_ago,))
            
            system_stats = cursor.fetchone()
            
            conn.close()
            
            return {
                "webhook": {
                    "total_requests": webhook_stats[0] or 0,
                    "successful_requests": webhook_stats[1] or 0,
                    "total_transactions": webhook_stats[2] or 0,
                    "processed_transactions": webhook_stats[3] or 0,
                    "failed_transactions": webhook_stats[4] or 0,
                    "avg_process_time": round(webhook_stats[5] or 0, 3),
                    "max_process_time": round(webhook_stats[6] or 0, 3),
                    "success_rate": round((webhook_stats[1] or 0) / max(webhook_stats[0], 1) * 100, 2)
                },
                "system": {
                    "avg_cpu_percent": round(system_stats[0] or 0, 1),
                    "avg_memory_percent": round(system_stats[1] or 0, 1),
                    "avg_disk_percent": round(system_stats[2] or 0, 1)
                },
                "last_updated": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error("Failed to get summary stats", error=str(e))
            return {
                "webhook": {},
                "system": {},
                "last_updated": datetime.now().isoformat(),
                "error": str(e)
            }
    
    def analyze_webhook_files(self) -> Dict[str, Any]:
        """Analyze webhook notification files for additional insights"""
        try:
            stats = {
                "total_files": 0,
                "total_transactions": 0,
                "transactions_by_type": defaultdict(int),
                "transactions_by_bank": defaultdict(int),
                "largest_batch": 0,
                "oldest_file": None,
                "newest_file": None
            }
            
            for date_dir in self.webhook_notifications_dir.glob("*"):
                if not date_dir.is_dir():
                    continue
                
                for webhook_file in date_dir.glob("*.json"):
                    try:
                        with open(webhook_file, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                        
                        stats["total_files"] += 1
                        transaction_count = data.get("transaction_count", 0)
                        stats["total_transactions"] += transaction_count
                        
                        if transaction_count > stats["largest_batch"]:
                            stats["largest_batch"] = transaction_count
                        
                        # Analyze transaction types and banks
                        for tx in data.get("data", []):
                            tx_type = tx.get("trans_type", "unknown")
                            stats["transactions_by_type"][tx_type] += 1
                            
                            bank_name = tx.get("ofs_bank_name", "unknown")
                            if bank_name != "unknown":
                                stats["transactions_by_bank"][bank_name] += 1
                        
                        # Track file timestamps
                        file_timestamp = data.get("received_at")
                        if file_timestamp:
                            if not stats["oldest_file"] or file_timestamp < stats["oldest_file"]:
                                stats["oldest_file"] = file_timestamp
                            if not stats["newest_file"] or file_timestamp > stats["newest_file"]:
                                stats["newest_file"] = file_timestamp
                    
                    except Exception as file_error:
                        logger.warning("Failed to analyze webhook file", 
                                     file=str(webhook_file), error=str(file_error))
            
            # Convert defaultdicts to regular dicts
            stats["transactions_by_type"] = dict(stats["transactions_by_type"])
            stats["transactions_by_bank"] = dict(stats["transactions_by_bank"])
            
            return stats
            
        except Exception as e:
            logger.error("Failed to analyze webhook files", error=str(e))
            return {}
    
    def cleanup_old_data(self, days: int = 30):
        """Clean up old data from database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cutoff_time = (datetime.now() - timedelta(days=days)).isoformat()
            
            # Clean webhook metrics
            cursor.execute('DELETE FROM webhook_metrics WHERE timestamp < ?', (cutoff_time,))
            webhook_deleted = cursor.rowcount
            
            # Clean system metrics
            cursor.execute('DELETE FROM system_metrics WHERE timestamp < ?', (cutoff_time,))
            system_deleted = cursor.rowcount
            
            conn.commit()
            conn.close()
            
            logger.info("Cleaned up old data", 
                       webhook_records_deleted=webhook_deleted,
                       system_records_deleted=system_deleted)
            
        except Exception as e:
            logger.error("Failed to cleanup old data", error=str(e))


# Singleton instance
_metrics_collector = None

def get_metrics_collector() -> MetricsCollector:
    """Get singleton metrics collector instance"""
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = MetricsCollector()
    return _metrics_collector