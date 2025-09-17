# Secure Bank Webhook API

## Tổng quan

Đây là một hệ thống API webhook bảo mật cao để nhận thông báo từ ngân hàng với các tính năng bảo mật enterprise-grade:

- **Digital Signature Verification**: Xác thực chữ ký điện tử SHA512withRSA với key 2048-bit
- **Mutual TLS (mTLS)**: Xác thực hai chiều với HTTPS/TLS1.2+
- **IP Whitelist**: Kiểm soát truy cập dựa trên IP
- **Rate Limiting**: Giới hạn số lượng request per IP/time window
- **Monitoring Stack**: LGTM stack (Loki, Grafana, Tempo, Mimir/Prometheus)
- **Structured Logging**: JSON structured logs để phân tích và monitoring

## Kiến trúc hệ thống

```
┌─────────────────┐    HTTPS/mTLS    ┌──────────────────┐
│     Bank        │ ────────────────→ │   Webhook API    │
│                 │   + Digital Sign  │                  │
└─────────────────┘   + IP Whitelist  └──────────────────┘
                      + Rate Limiting           │
                                               │
┌─────────────────┐                           │
│     Redis       │ ←─────────────────────────┘
│  (Rate Limit)   │
└─────────────────┘
                      
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Prometheus    │    │     Grafana     │    │      Loki       │
│   (Metrics)     │    │ (Visualization) │    │     (Logs)      │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                 │
                      ┌─────────────────┐
                      │     Tempo       │
                      │   (Tracing)     │
                      └─────────────────┘
```

## Cấu trúc dự án

```
Webhook-API/
├── app/
│   ├── config/
│   │   ├── __init__.py
│   │   ├── settings.py          # Cấu hình ứng dụng
│   │   └── logging.py           # Cấu hình structured logging
│   ├── middlewares/
│   │   ├── __init__.py
│   │   ├── ip_whitelist.py      # Middleware kiểm tra IP whitelist
│   │   ├── rate_limit.py        # Middleware rate limiting
│   │   └── signature_verification.py  # Middleware xác thực chữ ký
│   ├── services/
│   │   ├── __init__.py
│   │   └── webhook_processor.py # Service xử lý webhook
│   ├── __init__.py
│   ├── main.py                  # FastAPI application
│   └── models.py                # Pydantic models
├── certs/                       # SSL certificates
├── monitoring/                  # Monitoring stack configs
│   ├── grafana/
│   ├── loki/
│   ├── prometheus/
│   └── tempo/
├── docker-compose.yml           # Docker stack
├── Dockerfile                   # API container
├── requirements.txt             # Python dependencies
├── generate_certs.ps1           # Windows certificate generation
├── generate_certs.sh            # Linux certificate generation
└── README.md                    # Documentation
```

## Yêu cầu hệ thống

- Python 3.11+
- Docker & Docker Compose
- OpenSSL (để tạo certificates)
- Redis (cho rate limiting)

## Cài đặt và chạy

### 1. Clone repository và setup environment

```bash
git clone <repository-url>
cd Webhook-API
cp .env.example .env
```

### 2. Chỉnh sửa file .env theo môi trường của bạn

```env
# Server configuration
HOST=0.0.0.0
PORT=8443

# IP Whitelist (IP của bank)
ALLOWED_IPS=192.168.1.100,10.0.0.0/8

# Rate limiting
RATE_LIMIT_REQUESTS=60
RATE_LIMIT_WINDOW=60

# Logging
LOG_LEVEL=INFO
```

### 3. Tạo SSL certificates

**Windows:**
```powershell
.\generate_certs.ps1
```

**Linux/Mac:**
```bash
chmod +x generate_certs.sh
./generate_certs.sh
```

### 4. Cập nhật bank public key

Thay thế file `certs/bank_public.pem` bằng public key thực tế từ ngân hàng.

### 5. Chạy hệ thống với Docker

```bash
# Build và start tất cả services
docker-compose up -d

# Kiểm tra logs
docker-compose logs -f webhook-api

# Kiểm tra health
curl -k https://localhost:8443/health
```

## API Endpoints

### POST /webhook/bank-notification

Endpoint chính để nhận thông báo từ ngân hàng.

**Request Body:**
```json
{
    "timestamp": "2024-01-15T10:30:00Z",
    "transaction_id": "TXN123456789",
    "account_number": "1234567890",
    "amount": 1000000.0,
    "currency": "VND",
    "transaction_type": "credit",
    "reference": "REF123456",
    "description": "Payment notification",
    "signature": "base64-encoded-signature"
}
```

**Response:**
```json
{
    "success": true,
    "message": "Notification processed successfully",
    "transaction_id": "TXN123456789",
    "timestamp": "2024-01-15T10:30:01Z"
}
```

### GET /health

Health check endpoint.

### GET /metrics

Prometheus metrics endpoint (yêu cầu client certificate).

## Bảo mật

### 1. Digital Signature Verification

- Thuật toán: SHA512withRSA
- Key size: 2048-bit
- Canonical string format: `key1=value1&key2=value2&...`
- Signature format: Base64 encoded

### 2. Mutual TLS (mTLS)

- TLS version: 1.2+
- Client certificate required
- CA certificate validation
- Certificate revocation checking

### 3. IP Whitelist

- Supports individual IPs: `192.168.1.100`
- Supports CIDR ranges: `10.0.0.0/8`
- Proxy header support: `X-Forwarded-For`, `X-Real-IP`

### 4. Rate Limiting

- Redis-based distributed rate limiting
- Configurable requests per time window
- Per-IP rate limiting
- Automatic cleanup of expired entries

## Monitoring và Logging

### Accessing Monitoring Services

- **Grafana**: http://localhost:3000 (admin/admin123)
- **Prometheus**: http://localhost:9090
- **Loki**: http://localhost:3100

### Key Metrics

- `webhook_requests_total`: Total số lượng requests
- `webhook_request_duration_seconds`: Thời gian xử lý request
- `signature_verification_total`: Kết quả xác thực signature
- `rate_limit_exceeded_total`: Số lần bị rate limit

### Log Structure

```json
{
    "timestamp": "2024-01-15T10:30:00.123456",
    "level": "info",
    "event": "webhook_received",
    "service": "webhook-api",
    "version": "1.0.0",
    "transaction_id": "TXN123456789",
    "client_ip": "192.168.1.100",
    "amount": 1000000.0,
    "account_number": "1234567890"
}
```

## Testing

### Test với curl

```bash
# Test health endpoint
curl -k https://localhost:8443/health

# Test webhook endpoint (cần client certificate)
curl -k -X POST \
  --cert certs/client.crt \
  --key certs/client.key \
  --cacert certs/ca.crt \
  -H "Content-Type: application/json" \
  -d '{
    "timestamp": "2024-01-15T10:30:00Z",
    "transaction_id": "TEST123456789",
    "account_number": "1234567890",
    "amount": 1000000.0,
    "currency": "VND",
    "transaction_type": "credit",
    "signature": "test-signature"
  }' \
  https://localhost:8443/webhook/bank-notification
```

### Tạo test signature

```python
# Script để tạo test signature với private key
import base64
import json
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import serialization

# Load private key
with open('certs/bank_private.key', 'rb') as f:
    private_key = serialization.load_pem_private_key(f.read(), password=None)

# Payload (without signature)
payload = {
    "timestamp": "2024-01-15T10:30:00Z",
    "transaction_id": "TEST123456789",
    "account_number": "1234567890",
    "amount": 1000000.0,
    "currency": "VND",
    "transaction_type": "credit"
}

# Create canonical string
canonical_string = "&".join([f"{k}={v}" for k, v in sorted(payload.items())])

# Sign
signature = private_key.sign(
    canonical_string.encode('utf-8'),
    padding.PKCS1v15(),
    hashes.SHA512()
)

# Base64 encode
signature_b64 = base64.b64encode(signature).decode('utf-8')
print(f"Signature: {signature_b64}")
```

## Troubleshooting

### Common Issues

1. **Certificate Issues**
   - Đảm bảo certificates được tạo đúng cách
   - Kiểm tra permissions của certificate files
   - Verify certificate chain

2. **Redis Connection**
   - Kiểm tra Redis service đang chạy
   - Verify network connectivity
   - Check Redis authentication

3. **Signature Verification Fails**
   - Verify bank public key format
   - Check canonical string creation
   - Ensure signature encoding is correct

### Debug Mode

```bash
# Chạy ở debug mode
LOG_LEVEL=DEBUG docker-compose up webhook-api
```

### Logs Analysis

```bash
# View specific service logs
docker-compose logs -f webhook-api
docker-compose logs -f prometheus
docker-compose logs -f grafana

# Search logs với pattern
docker-compose logs webhook-api | grep "signature_verification"
```

## Production Deployment

### Security Considerations

1. **Change default passwords** trong docker-compose.yml
2. **Use production certificates** từ trusted CA
3. **Configure firewall** để restrict access
4. **Enable log rotation** để manage disk space
5. **Set up backup** cho Redis data và certificates
6. **Monitor resource usage** và set up alerts

## Updates & Changes

### Response Format Update (Latest)

API response format đã được cập nhật để tuân thủ yêu cầu từ ngân hàng:

**Previous Format:**
```json
{
  "success": true,
  "message": "Transactions processed successfully",
  "batch_id": "BATCH001",
  "processed_transactions": [...]
}
```

**New Bank-Compliant Format:**
```json
{
  "batchId": "BATCH001", 
  "code": "200",
  "message": "Success",
  "data": [...]
}
```

**Error Response Format:**
```json
{
  "batchId": "BATCH001",
  "code": "401", 
  "message": "Signature is not valid",
  "data": []
}
```

Tất cả error responses từ middlewares (signature verification, IP whitelist, rate limiting) đã được cập nhật theo format này.

### Environment Variables

```env
# Production settings
LOG_LEVEL=WARNING
RELOAD=false

# Security
ALLOWED_IPS=bank.ip.address.range

# Monitoring
PROMETHEUS_RETENTION=7d
GRAFANA_SECURITY_ADMIN_PASSWORD=secure-password
```

### High Availability

Để deploy với high availability:

1. **Load balancer** với multiple API instances
2. **Redis Cluster** cho distributed rate limiting
3. **External monitoring** với Prometheus federation
4. **Database backup** và disaster recovery plan

## Liên hệ và hỗ trợ

- **Email**: webhook-api-support@company.com
- **Documentation**: [Internal Wiki Link]
- **Monitoring Dashboard**: https://monitoring.company.com

## License

Internal use only - Company Proprietary