#!/usr/bin/env python3
"""
Test script for WhatAreYouDoing API server
"""

import requests
import json
import time
import os
from PIL import Image
from io import BytesIO

# Test configuration
SERVER_URL = "http://localhost:8000"
TEST_IMAGE_PATH = "/home/argo/projects/WhatAreYouDouing/image.png"

def create_test_image():
    """Check if test image exists"""
    if os.path.exists(TEST_IMAGE_PATH):
        return True
    else:
        print(f"Test image not found at: {TEST_IMAGE_PATH}")
        return False

def test_health_check():
    """Test the health check endpoint"""
    try:
        response = requests.get(f"{SERVER_URL}/api/health")
        return response.status_code == 200
    except Exception as e:
        print(f"Health check failed: {e}")
        return False

def test_create_event():
    """Test creating an event with mock data"""
    
    # Prepare mock sensor data
    sensor_data = {
        "temperature": 25.5,
        "humidity": 60.2,
        "illuminance": 350.0
    }
    
    # Prepare files for multipart upload
    files = {
        'image': ('image.png', open(TEST_IMAGE_PATH, 'rb'), 'image/png')
    }
    
    # Prepare form data
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
        # Close the file
        if 'image' in files:
            files['image'][1].close()

def test_get_current_status():
    """Test getting current status"""
    try:
        response = requests.get(f"{SERVER_URL}/api/now")
        return response.status_code == 200
    except Exception as e:
        print(f"Get current status failed: {e}")
        return False

def test_get_status_by_time():
    """Test getting status by specific time"""
    
    # Test with current time
    now = time.localtime()
    year, month, day, hour, minute = now.tm_year, now.tm_mon, now.tm_mday, now.tm_hour, now.tm_min
    
    try:
        response = requests.get(f"{SERVER_URL}/api/events/by-time/{year}/{month}/{day}/{hour}/{minute}")
        return response.status_code == 200
    except Exception as e:
        print(f"Get status by time failed: {e}")
        return False

def test_get_statistics():
    """Test getting statistics"""
    try:
        response = requests.get(f"{SERVER_URL}/api/stats")
        return response.status_code == 200
    except Exception as e:
        print(f"Get statistics failed: {e}")
        return False

def wait_for_processing(event_id, max_wait_time=30):
    """Wait for event processing to complete"""
    
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
    """Clean up test files"""
    pass

def main():
    """Run all tests"""
    print("WhatAreYouDoing API Server Test Suite")
    print("=" * 40)
    
    # Check test image
    if not create_test_image():
        return False
    
    # Run tests
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
    
    # Test event creation (requires functioning AI)
    event_id = test_create_event()
    
    if event_id:
        # Wait for processing
        processing_success = wait_for_processing(event_id)
        results.append(("Event Creation & Processing", processing_success))
    else:
        results.append(("Event Creation", False))
    
    # Print results
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
    
    # Cleanup
    cleanup()
    
    return passed == total

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1) 