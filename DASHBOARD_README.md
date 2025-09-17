# 📊 WEBHOOK API MONITORING DASHBOARD

Dashboard monitor cho Webhook API trên Windows Server - thay thế cho Redis/Prometheus/Grafana stack.

## 🌟 Tính Năng

### 📈 Real-time Monitoring
- **Request Metrics**: Total requests, success rate, response time
- **System Metrics**: CPU, Memory, Disk usage  
- **Transaction Analysis**: Theo loại giao dịch và ngân hàng
- **Error Tracking**: Chi tiết lỗi và thống kê failed requests

### 💾 Data Storage
- **SQLite Database**: Lưu trữ metrics lâu dài
- **In-memory Cache**: Dữ liệu real-time
- **File Analysis**: Phân tích webhook backup files

### 🎯 Dashboard Options
1. **Streamlit Dashboard**: Giao diện tương tác với charts
2. **HTML Dashboard**: Đơn giản, chạy trực tiếp trong browser

## 🚀 Quick Start

### Option 1: Streamlit Dashboard (Recommended)

#### Windows Command Prompt:
```cmd
# Clone repo và vào thư mục
cd e:\Webhook-API

# Chạy dashboard (tự động cài đặt dependencies)
run_dashboard.bat
```

#### Windows PowerShell:
```powershell
# Vào thư mục project
cd e:\Webhook-API

# Cho phép execution policy (nếu cần)
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

# Chạy dashboard
.\run_dashboard.ps1
```

Dashboard sẽ mở tại: **http://localhost:8501**

### Option 2: HTML Dashboard (Lightweight)

1. Đảm bảo Webhook API đang chạy tại `http://localhost:8443`
2. Mở file `dashboard.html` trong browser
3. Dashboard sẽ tự động kết nối và hiển thị metrics

## 📋 Prerequisites

### 1. Webhook API phải đang chạy
```cmd
python main.py
```

### 2. Python Dependencies (tự động cài đặt)
- streamlit
- plotly
- pandas
- requests
- psutil

## 🎯 Dashboard Features

### 📊 Main Metrics
- **Total Requests (24h)**: Tổng số requests trong 24h
- **Success Rate**: Tỷ lệ thành công (%)  
- **Average Response Time**: Thời gian phản hồi trung bình
- **Total Transactions**: Tổng số giao dịch xử lý

### 📈 Charts
- **Request Volume**: Theo thời gian (hourly)
- **System Resources**: CPU, Memory usage
- **Response Time Distribution**: Histogram
- **Transaction Types**: Pie chart (Credit/Debit)

### 📋 Tables
- **Recent Webhooks**: 20 webhook events gần nhất
- **Error Details**: Chi tiết lỗi và failed transactions

### ⚙️ Controls
- **API URL**: Cấu hình endpoint (mặc định: localhost:8443)
- **Time Range**: 1h, 6h, 24h, 7 days
- **Auto Refresh**: Tự động cập nhật (30s interval)

## 🔧 Configuration

### API Endpoints
Dashboard sử dụng các endpoints sau:
- `GET /health` - Health check
- `GET /api/metrics/summary` - Tổng quan metrics
- `GET /api/metrics/webhooks` - Webhook metrics  
- `GET /api/metrics/system` - System metrics
- `GET /api/metrics/hourly` - Hourly statistics

### Data Storage
- **SQLite Database**: `webhook_metrics.db`
- **Webhook Files**: `webhook_notifications/YYYYMMDD/*.json`
- **Memory Cache**: Recent data cho performance

### System Monitoring
- Tự động thu thập system metrics mỗi phút
- Lưu trữ 24h system data
- Cleanup dữ liệu cũ sau 30 ngày

## 📱 Screenshots

### Streamlit Dashboard
```
🚀 Webhook API Monitoring Dashboard
├── 📊 Real-time Metrics Cards
├── 📈 Interactive Charts (Plotly)
├── 📋 Data Tables  
├── ⚙️ Configuration Sidebar
└── 🔄 Auto-refresh Controls
```

### HTML Dashboard  
```
🚀 Webhook API Monitor
├── 💾 Lightweight (no dependencies)
├── 📊 Chart.js visualizations
├── 🎨 Modern glass-morphism design
├── 📱 Mobile responsive
└── ⚡ Fast loading
```

## 🐛 Troubleshooting

### Dashboard không hiển thị data
1. **Check API connection**:
   ```cmd
   curl http://localhost:8443/health
   ```

2. **Check API logs**:
   ```cmd
   # Terminal chạy main.py sẽ hiện logs
   ```

3. **Check metrics endpoints**:
   ```cmd
   curl http://localhost:8443/api/metrics/summary
   ```

### Streamlit errors
1. **Module not found**:
   ```cmd
   pip install -r requirements.txt
   ```

2. **Port conflict**:
   ```cmd
   streamlit run dashboard.py --server.port 8502
   ```

### Performance issues
- **Cleanup old data**: Dashboard tự động cleanup sau 30 ngày
- **Reduce time range**: Dùng 1h-6h thay vì 7 days
- **Check system resources**: Task Manager -> Performance

## 📈 Metrics Collected

### Webhook Metrics
```json
{
    "timestamp": "2024-01-01T12:00:00",
    "batch_id": "BATCH_001",
    "transaction_count": 5,
    "processed_count": 5,
    "failed_count": 0,
    "process_time": 0.045,
    "status_code": 200,
    "client_ip": "192.168.1.100"
}
```

### System Metrics
```json
{
    "timestamp": "2024-01-01T12:00:00",
    "cpu_percent": 25.5,
    "memory_percent": 45.2,
    "disk_usage_percent": 60.1,
    "network_bytes_sent": 1024000,
    "network_bytes_recv": 2048000
}
```

## 🔄 API Integration

Dashboard tự động tích hợp với webhook API thông qua:

1. **Enhanced Metrics Collection**: `metrics_collector.py`
2. **New API Endpoints**: Thêm vào `main.py`
3. **Real-time Data**: WebSocket hoặc polling
4. **File Analysis**: Đọc webhook backup files

## 📊 Dashboard Comparison

| Feature | Streamlit | HTML |
|---------|-----------|------|
| **Setup** | Cần Python + pip install | Chỉ cần browser |
| **Interactivity** | Cao (widgets, filters) | Trung bình (controls) |
| **Performance** | Trung bình | Cao |
| **Customization** | Cao | Trung bình |
| **Dependencies** | Nhiều | Không |
| **Mobile** | Tốt | Excellent |

## 🎯 Recommendations

### Production Use
- **Streamlit Dashboard** cho dev/internal monitoring
- **HTML Dashboard** cho production/external access
- Setup reverse proxy (nginx) cho HTTPS
- Enable auto-cleanup cho database

### Development  
- Use auto-refresh với interval 30s
- Monitor cả webhook metrics và system metrics
- Regularly backup SQLite database

## 💡 Tips

1. **Performance Optimization**:
   - Dùng time range ngắn cho real-time monitoring
   - Enable auto-cleanup để tránh database quá lớn

2. **Monitoring Strategy**:
   - Monitor success rate (>95%)
   - Watch response time (<100ms)
   - Track system resources (<80%)

3. **Troubleshooting**:
   - Check API health trước khi debug dashboard
   - Xem logs trong terminal chạy main.py
   - Test individual API endpoints

## 📞 Support

Nếu có vấn đề:
1. Check API logs trong terminal
2. Test individual endpoints với curl/browser
3. Check system resources (Task Manager)
4. Restart both API và dashboard

---

🎉 **Dashboard đã sẵn sàng cho Windows Server monitoring!**