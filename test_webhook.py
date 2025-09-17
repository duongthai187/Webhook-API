#!/usr/bin/env python3
"""
Test script để kiểm tra webhook API
"""
import json
import requests
import base64
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
import hashlib

def create_test_signature(payload_dict: dict, private_key_pem: str) -> str:
    """
    Tạo signature để test
    """
    # Convert dict to canonical string (same logic as server)
    canonical_string = ""
    def serialize_value(obj):
        if isinstance(obj, dict):
            items = sorted(obj.items())
            return "{" + ",".join(f'"{k}":{serialize_value(v)}' for k, v in items) + "}"
        elif isinstance(obj, list):
            return "[" + ",".join(serialize_value(item) for item in obj) + "]"
        elif isinstance(obj, str):
            return f'"{obj}"'
        elif isinstance(obj, bool):
            return "true" if obj else "false"
        elif obj is None:
            return "null"
        else:
            return str(obj)
    
    canonical_string = serialize_value(payload_dict)
    
    # Load private key
    private_key = serialization.load_pem_private_key(
        private_key_pem.encode('utf-8'),
        password=None,
    )
    
    # Sign with SHA512withRSA
    signature = private_key.sign(
        canonical_string.encode('utf-8'),
        padding.PKCS1v15(),
        hashes.SHA512()
    )
    
    # Return base64 encoded signature
    return base64.b64encode(signature).decode('utf-8')

def test_webhook_api():
    """
    Test webhook API với signature hợp lệ
    """
    # Test payload
    test_data = {
        "batchId": "BATCH001",
        "transactions": [
            {
                "transaction_id": "TXN001",
                "transaction_time": "2024-01-10T10:30:00Z",
                "amount": 1000000,
                "currency": "VND",
                "account_number": "1234567890",
                "account_name": "NGUYEN VAN A",
                "description": "Transfer from bank",
                "reference_number": "REF001",
                "bank_code": "MB"
            }
        ]
    }
    
    # Để test, bạn cần tạo private key thực tế
    # Đây chỉ là ví dụ - trong thực tế bạn cần dùng private key tương ứng với public key trong server
    private_key_example = """-----BEGIN PRIVATE KEY-----
# BẠN CẦN THAY THẾ BẰNG PRIVATE KEY THỰC TẾ
-----END PRIVATE KEY-----"""
    
    try:
        # Tạo signature (tạm thời skip vì cần private key thật)
        # signature = create_test_signature(test_data, private_key_example)
        
        # Test payload với signature
        test_payload = {
            **test_data,
            "signature": "test_signature_placeholder"
        }
        
        # Call API
        response = requests.post(
            "http://localhost:8000/api/v1/webhook/notify",
            json=test_payload,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "Bank-Webhook-Test/1.0"
            }
        )
        
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.json()}")
        
    except Exception as e:
        print(f"Test failed: {str(e)}")

if __name__ == "__main__":
    print("Testing webhook API...")
    test_webhook_api()