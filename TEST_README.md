# 🧪 WEBHOOK API TESTING

Các file test để kiểm tra Webhook API hoạt động đúng.

## 📁 Test Files

### 1. `quick_test.py` - Test Nhanh
```bash
python quick_test.py
```
- ✅ Test health endpoint
- ✅ Test metrics endpoint  
- ✅ Test security (webhook without signature)
- ⚡ Chạy nhanh, không cần keys

### 2. `test_webhook.py` - Test Đầy Đủ
```bash
python test_webhook.py
```
- ✅ Test health endpoint
- ✅ Test webhook với signature hợp lệ
- ✅ Test multiple transactions
- ✅ Test signature không hợp lệ
- 🔑 Tự động tạo keys nếu chưa có

## 🚀 Cách Sử dụng

### Bước 1: Chạy API
```bash
# Terminal 1: Start API
python main.py
```

### Bước 2: Chạy Test
```bash
# Terminal 2: Quick test
python quick_test.py

# Hoặc full test
python test_webhook.py
```

## 📊 Kết Quả Mong Đợi

### Quick Test
```
🚀 QUICK WEBHOOK API TEST
========================================

1️⃣ Testing Health Endpoint...
✅ API is running!
   Status: healthy
   Version: 1.0.0

2️⃣ Testing Metrics Endpoint...
✅ Metrics endpoint working!
   Found 15 metrics

3️⃣ Testing Webhook Security...
✅ Security working - unsigned request rejected!

========================================
✅ Quick test completed!
```

### Full Test
```
🚀 WEBHOOK API TEST SUITE
============================================================
🎯 Target API: http://localhost:8000

==================== Health Check ====================
✅ Health Check: PASSED

==================== Simple Webhook ====================
📦 Test Data:
   Batch ID: TEST_BATCH_20250917_140530
   Transactions: 1
   Signature: k8J2xvN9...

📡 Response:
   Status Code: 200
   Process Time: 0.045s
   Response Body: {
       "batchId": "TEST_BATCH_20250917_140530",
       "code": "200",
       "message": "Success",
       "data": [...]
   }
✅ Simple Webhook: PASSED

🎯 Results: 4/4 tests passed
🎉 All tests passed! Webhook API is working correctly.
```

## 🔧 Troubleshooting

### Lỗi thường gặp:

1. **Connection Error**
```
❌ Cannot connect to API: Connection refused
💡 Đảm bảo API đang chạy: python main.py
```

2. **Signature Error** 
```
❌ Signature verification failed
💡 Check bank_public.pem trong folder certs/
```

3. **Rate Limited**
```
⚠️ Rate limit exceeded
💡 Đợi 1 phút hoặc restart Redis
```

## 📝 Test Data

### Transaction Types
- **C**: Credit (tiền vào)
- **D**: Debit (tiền ra)

### Sample Transaction
```json
{
    "transactionId": "TXN_20250917140530_001",
    "tranRefNo": "REF_140530",
    "srcAccountNumber": "1234567890123",
    "amount": 500000.0,
    "balanceAvailable": 2000000.0,
    "transType": "C",
    "transDesc": "Test credit transaction"
}
```

## 🔐 Security Tests

1. **Valid Signature**: RSA SHA512 signature
2. **Invalid Signature**: Random string
3. **No Signature**: Missing signature field
4. **Rate Limiting**: Multiple requests from same IP

## 📈 Performance Tests

- Process time tracking
- Rate limit monitoring
- Memory usage (via metrics endpoint)
- Error rate monitoring

## 💡 Tips

- Chạy `quick_test.py` trước để check API cơ bản
- Sử dụng `test_webhook.py` để test đầy đủ chức năng
- Check logs trong terminal API để debug
- Xem metrics tại: http://localhost:8000/metrics