#!/usr/bin/env python3
"""
Quick Test - Test nhanh webhook API
Chỉ cần chạy và xem kết quả
"""

import requests
import json
from datetime import datetime


def quick_test():
    """Test nhanh health endpoint"""
    print("🚀 QUICK WEBHOOK API TEST")
    print("=" * 40)
    
    base_url = "http://localhost:8000"
    
    # Test 1: Health check
    print("\n1️⃣ Testing Health Endpoint...")
    try:
        response = requests.get(f"{base_url}/health", timeout=5)
        if response.status_code == 200:
            print("✅ API is running!")
            data = response.json()
            print(f"   Status: {data.get('status')}")
            print(f"   Version: {data.get('version')}")
        else:
            print(f"❌ Health check failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Cannot connect to API: {e}")
        print("💡 Đảm bảo API đang chạy: python main.py")
        return False
    
    # Test 2: Metrics endpoint
    print("\n2️⃣ Testing Metrics Endpoint...")
    try:
        response = requests.get(f"{base_url}/metrics", timeout=5)
        if response.status_code == 200:
            print("✅ Metrics endpoint working!")
            # Count number of metrics
            metrics_text = response.text
            metric_lines = [line for line in metrics_text.split('\n') if line and not line.startswith('#')]
            print(f"   Found {len(metric_lines)} metrics")
        else:
            print(f"⚠️  Metrics endpoint issue: {response.status_code}")
    except Exception as e:
        print(f"⚠️  Metrics test error: {e}")
    
    # Test 3: Test invalid webhook (without signature)
    print("\n3️⃣ Testing Webhook Security...")
    invalid_payload = {
        "sourceAppId": "TEST",
        "batchId": "QUICK_TEST",
        "timestamp": str(int(datetime.now().timestamp())),
        "data": [{
            "transactionId": "QUICK_TEST_TXN",
            "tranRefNo": "QUICK_REF",
            "srcAccountNumber": "1234567890",
            "amount": 1000.0,
            "transType": "C"
        }]
        # No signature - should fail
    }
    
    try:
        response = requests.post(
            f"{base_url}/webhook/bank-notification",
            json=invalid_payload,
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get('code') == '401':
                print("✅ Security working - unsigned request rejected!")
            else:
                print(f"⚠️  Unexpected response: {data}")
        else:
            print(f"⚠️  Unexpected status: {response.status_code}")
            
    except Exception as e:
        print(f"⚠️  Security test error: {e}")
    
    print("\n" + "="*40)
    print("✅ Quick test completed!")
    print("\n💡 For full testing with signatures:")
    print("   python test_webhook.py")
    
    return True


if __name__ == "__main__":
    quick_test()