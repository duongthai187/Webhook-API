#!/usr/bin/env python3
"""
Test client cho webhook API
Script này tạo test requests với digital signature hợp lệ
"""

import base64
import json
import requests
from datetime import datetime
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import serialization


def load_private_key(key_path: str):
    """Load private key từ file"""
    with open(key_path, 'rb') as f:
        private_key = serialization.load_pem_private_key(f.read(), password=None)
    return private_key


def create_canonical_string(payload: dict) -> str:
    """Tạo canonical string để ký"""
    sorted_items = sorted(payload.items())
    pairs = []
    for key, value in sorted_items:
        if isinstance(value, (dict, list)):
            value_str = json.dumps(value, sort_keys=True, separators=(',', ':'))
        else:
            value_str = str(value)
        pairs.append(f"{key}={value_str}")
    return "&".join(pairs)


def create_signature(payload: dict, private_key) -> str:
    """Tạo digital signature cho payload"""
    canonical_string = create_canonical_string(payload)
    print(f"Canonical string: {canonical_string}")
    
    signature = private_key.sign(
        canonical_string.encode('utf-8'),
        padding.PKCS1v15(),
        hashes.SHA512()
    )
    
    return base64.b64encode(signature).decode('utf-8')


def test_webhook():
    """Test webhook endpoint"""
    # Load private key
    private_key = load_private_key('certs/bank_private.key')
    
    # Tạo test payload
    payload = {
        "timestamp": datetime.now().isoformat(),
        "transaction_id": "TEST123456789",
        "account_number": "1234567890",
        "amount": 1000000.0,
        "currency": "VND",
        "transaction_type": "credit",
        "reference": "TEST-REF-123",
        "description": "Test transaction from client"
    }
    
    # Tạo signature
    signature = create_signature(payload, private_key)
    payload["signature"] = signature
    
    print(f"Test payload:")
    print(json.dumps(payload, indent=2))
    print(f"\nSignature: {signature}")
    
    # Send request
    try:
        response = requests.post(
            "https://localhost:8443/webhook/bank-notification",
            json=payload,
            cert=('certs/client.crt', 'certs/client.key'),
            verify='certs/ca.crt',
            timeout=10
        )
        
        print(f"\nResponse Status: {response.status_code}")
        print(f"Response Headers: {dict(response.headers)}")
        print(f"Response Body:")
        print(json.dumps(response.json(), indent=2))
        
    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}")


def test_health():
    """Test health endpoint"""
    try:
        response = requests.get(
            "https://localhost:8443/health",
            verify='certs/ca.crt',
            timeout=5
        )
        
        print(f"Health Check Status: {response.status_code}")
        print(f"Response: {response.json()}")
        
    except requests.exceptions.RequestException as e:
        print(f"Health check failed: {e}")


if __name__ == "__main__":
    print("Testing Webhook API...")
    print("=" * 50)
    
    print("\n1. Testing health endpoint...")
    test_health()
    
    print("\n2. Testing webhook endpoint...")
    test_webhook()
    
    print("\nTest completed!")