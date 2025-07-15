#!/usr/bin/env python3
"""
API鯖のテストコード
"""

import requests
import json
import time
import os
from PIL import Image
from io import BytesIO

# テスト設定
SERVER_URL = "http://localhost:8000"
TEST_IMAGE_PATH = "/home/argo/projects/WhatAreYouDouing/image.png"

def create_test_image():
    """テスト用画像があるかチェック"""
    if os.path.exists(TEST_IMAGE_PATH):
        return True
    else:
        print(f"Test image not found at: {TEST_IMAGE_PATH}")
        return False

def test_health_check():
    """ヘルスチェックのエンドポイントテスト"""
    try:
        response = requests.get(f"{SERVER_URL}/api/health")
        return response.status_code == 200
    except Exception as e:
        print(f"Health check failed: {e}")
        return False

def test_create_event():
    """モックデータでイベント作成をテストする"""
    
    
    sensor_data = {
        "temperature": 25.5,
        "humidity": 60.2,
        "illuminance": 350.0
    }
    
    
    files = {
        'image': ('image.png', open(TEST_IMAGE_PATH, 'rb'), 'image/png')
    }
    
    
    data = {
        'metadata': json.dumps(sensor_data)
    }
    
    try:
        response = requests.post(f"{SERVER_URL}/api/events", files=files, data=data)
        
        if response.status_code == 200:
            event_data = response.json()
            return event_data['event_id']
        else:
            print(f"Event creation failed: {response.status_code}")
            return None
    except Exception as e:
        print(f"Event creation failed: {e}")
        return None
    finally:
        
        if 'image' in files:
            files['image'][1].close()

def test_get_current_status():
    """現在のステータス取得テスト"""
    try:
        response = requests.get(f"{SERVER_URL}/api/now")
        return response.status_code == 200
    except Exception as e:
        print(f"Get current status failed: {e}")
        return False

def test_get_status_by_time():
    """指定時刻のステータス取得テスト"""
    
    # 現在時刻でテスト
    now = time.localtime()
    year, month, day, hour, minute = now.tm_year, now.tm_mon, now.tm_mday, now.tm_hour, now.tm_min
    
    try:
        response = requests.get(f"{SERVER_URL}/api/events/by-time/{year}/{month}/{day}/{hour}/{minute}")
        return response.status_code == 200
    except Exception as e:
        print(f"Get status by time failed: {e}")
        return False

def test_get_statistics():
    """統計情報取得テスト"""
    try:
        response = requests.get(f"{SERVER_URL}/api/stats")
        return response.status_code == 200
    except Exception as e:
        print(f"Get statistics failed: {e}")
        return False

def wait_for_processing(event_id, max_wait_time=30):
    """イベント処理完了まで待機"""
    
    start_time = time.time()
    while time.time() - start_time < max_wait_time:
        try:
            response = requests.get(f"{SERVER_URL}/api/now")
            if response.status_code == 200:
                data = response.json()
                if data.get('confidence') == 'completed':
                    return True
            
            time.sleep(2)
        except Exception as e:
            print(f"Error checking processing status: {e}")
            break
    
    print(f"Processing timeout after {max_wait_time} seconds")
    return False

def cleanup():
    """テストファイルのおかたづけ♡"""
    pass

def main():
    """全テスト実行"""
    print("WhatAreYouDoing API Server Test Suite")
    print("=" * 40)
    
    # テスト用画像をチェック
    if not create_test_image():
        return False
    
    # 実行
    tests = [
        ("Health Check", test_health_check),
        ("Current Status", test_get_current_status),
        ("Status by Time", test_get_status_by_time),
        ("Statistics", test_get_statistics),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"Test '{test_name}' failed with exception: {e}")
            results.append((test_name, False))
    
    # イベント作成テスト（AI機能が必要）
    event_id = test_create_event()
    
    if event_id:
        # 処理完了まで待機
        processing_success = wait_for_processing(event_id)
        results.append(("Event Creation & Processing", processing_success))
    else:
        results.append(("Event Creation", False))
    
    # 結果
    print("\nTEST RESULTS")
    print("=" * 40)
    
    passed = 0
    total = len(results)
    
    for test_name, success in results:
        status = "PASS" if success else "FAIL"
        print(f"{test_name}: {status}")
        if success:
            passed += 1
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    # 後片付け
    cleanup()
    
    return passed == total

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1) 