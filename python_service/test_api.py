#!/usr/bin/env python3
"""
Test script for the REST API
Tests all endpoints
"""
import requests
import json
import time

BASE_URL = 'http://localhost:5001'


def print_separator(title=""):
    print("\n" + "=" * 80)
    if title:
        print(f" {title}")
        print("=" * 80)
    print()


def test_health():
    """Test health endpoint"""
    print("Testing /health...")
    try:
        response = requests.get(f'{BASE_URL}/health', timeout=5)
        print(f"Status: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def test_status():
    """Test status endpoint"""
    print("Testing /status...")
    try:
        response = requests.get(f'{BASE_URL}/status', timeout=10)
        print(f"Status: {response.status_code}")
        data = response.json()
        print(f"Service: {data.get('service')}")
        print(f"Version: {data.get('version')}")
        if 'embedder' in data:
            print(f"Embedder: {data['embedder']['model_name']}")
            print(f"Embedding dim: {data['embedder']['embedding_dimension']}")
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def test_trackers():
    """Test trackers endpoint"""
    print("Testing /api/trackers...")
    try:
        response = requests.get(f'{BASE_URL}/api/trackers?limit=3', timeout=30)
        print(f"Status: {response.status_code}")
        data = response.json()
        if data.get('success'):
            print(f"✓ Found {data['count']} trackers")
            if data['trackers']:
                tracker = data['trackers'][0]
                print(f"  Example: #{tracker['tracker_id']} - {tracker['subject'][:50]}...")
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def test_prs():
    """Test PRs endpoint"""
    print("Testing /api/prs...")
    try:
        response = requests.get(f'{BASE_URL}/api/prs?limit=3', timeout=30)
        print(f"Status: {response.status_code}")
        data = response.json()
        if data.get('success'):
            print(f"✓ Found {data['count']} PRs")
            if data['prs']:
                pr = data['prs'][0]
                print(f"  Example: #{pr['pr_number']} - {pr['title'][:50]}...")
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def test_embeddings():
    """Test embeddings endpoint"""
    print("Testing /api/embeddings/generate...")
    try:
        payload = {
            'texts': [
                'Fix memory leak in OSD',
                'Update documentation for RGW'
            ]
        }
        response = requests.post(
            f'{BASE_URL}/api/embeddings/generate',
            json=payload,
            timeout=30
        )
        print(f"Status: {response.status_code}")
        data = response.json()
        if data.get('success'):
            print(f"✓ Generated {data['count']} embeddings")
            print(f"  Dimension: {data['dimension']}")
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def test_recommendations():
    """Test recommendations endpoint"""
    print("Testing /api/recommendations...")
    print("(This may take 30-60 seconds on first run...)")
    try:
        response = requests.get(
            f'{BASE_URL}/api/recommendations?tracker_limit=2&pr_limit=10&top_k=3',
            timeout=120
        )
        print(f"Status: {response.status_code}")
        data = response.json()
        if data.get('success'):
            print(f"✓ Generated {data['count']} recommendations")
            if data.get('recommendations'):
                rec = data['recommendations'][0]
                print(f"  Example:")
                print(f"    Tracker: #{rec['tracker']['tracker_id']} - {rec['tracker']['subject'][:40]}...")
                print(f"    PR: #{rec['pr']['pr_number']} - {rec['pr']['title'][:40]}...")
                print(f"    Similarity: {rec['similarity']:.3f} ({rec['confidence']})")
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def main():
    """Main test function"""
    print_separator("Ceph Tracker Linker API Test")
    print(f"Testing API at: {BASE_URL}")
    print("Make sure the API is running: python api/app.py")
    
    # Wait a moment for user to start the API
    print("\nStarting tests in 2 seconds...")
    time.sleep(2)
    
    results = {}
    
    # Test health
    print_separator("1. Health Check")
    results['health'] = test_health()
    
    # Test status
    print_separator("2. Status Check")
    results['status'] = test_status()
    
    # Test trackers
    print_separator("3. Trackers Endpoint")
    results['trackers'] = test_trackers()
    
    # Test PRs
    print_separator("4. PRs Endpoint")
    results['prs'] = test_prs()
    
    # Test embeddings
    print_separator("5. Embeddings Endpoint")
    results['embeddings'] = test_embeddings()
    
    # Test recommendations
    print_separator("6. Recommendations Endpoint")
    results['recommendations'] = test_recommendations()
    
    # Summary
    print_separator("Test Summary")
    for test_name, passed in results.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{test_name:20s}: {status}")
    
    total = len(results)
    passed = sum(results.values())
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n✓ All tests passed!")
    else:
        print(f"\n✗ {total - passed} test(s) failed")
    
    print_separator()


if __name__ == '__main__':
    main()

# Made with Bob
