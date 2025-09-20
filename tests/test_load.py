#!/usr/bin/env python3
"""
TidyBot Load Testing
Tests system performance under load
"""

import os
import requests
import tempfile
import time
import concurrent.futures
from pathlib import Path
import random
import string

BASE_URL = "http://localhost:11007/api/v1"

def generate_test_file():
    """Generate a random test file"""
    content = ''.join(random.choices(string.ascii_letters + string.digits, k=1000))
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write(f"Test Document\n{content}\nDate: 2025-09-20")
        return f.name

def process_file(file_path):
    """Process a single file"""
    try:
        with open(file_path, 'rb') as f:
            files = {'file': ('test.txt', f, 'text/plain')}
            r = requests.post(f"{BASE_URL}/files/process", files=files, timeout=10)
            return r.status_code == 200
    except:
        return False
    finally:
        os.unlink(file_path)

def rename_file(index):
    """Test rename operation"""
    test_file = Path(f"/tmp/load_test_{index}.txt")
    test_file.write_text(f"Content {index}")

    try:
        r = requests.post(f"{BASE_URL}/files/rename-on-disk", json={
            "file_path": str(test_file),
            "new_name": f"renamed_{index}.txt",
            "create_backup": False,
            "update_index": False
        }, timeout=5)

        success = r.status_code == 200
        if success:
            new_path = Path(r.json()['new_path'])
            if new_path.exists():
                new_path.unlink()
        return success
    except:
        return False
    finally:
        test_file.unlink(missing_ok=True)

def search_operation(query_num):
    """Test search operation"""
    try:
        r = requests.post(f"{BASE_URL}/search/query", json={
            "query": f"test document {query_num}",
            "search_type": "natural"
        }, timeout=5)
        return r.status_code == 200
    except:
        return False

def run_load_test():
    """Run load testing"""
    print("\n" + "="*50)
    print("🔥 TidyBot Load Testing")
    print("="*50 + "\n")

    # Test 1: Concurrent file processing
    print("📁 Test 1: Processing 50 files concurrently...")
    start = time.time()

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        files = [generate_test_file() for _ in range(50)]
        results = list(executor.map(process_file, files))

    success_rate = sum(results) / len(results) * 100
    duration = time.time() - start

    print(f"  ✅ Processed {sum(results)}/50 files in {duration:.2f}s")
    print(f"  📊 Success rate: {success_rate:.1f}%")
    print(f"  ⚡ Throughput: {50/duration:.1f} files/sec")

    # Test 2: Concurrent rename operations
    print("\n♻️ Test 2: 100 concurrent rename operations...")
    start = time.time()

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        results = list(executor.map(rename_file, range(100)))

    success_rate = sum(results) / len(results) * 100
    duration = time.time() - start

    print(f"  ✅ Renamed {sum(results)}/100 files in {duration:.2f}s")
    print(f"  📊 Success rate: {success_rate:.1f}%")
    print(f"  ⚡ Throughput: {100/duration:.1f} renames/sec")

    # Test 3: Search load test
    print("\n🔎 Test 3: 200 concurrent searches...")
    start = time.time()

    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        results = list(executor.map(search_operation, range(200)))

    success_rate = sum(results) / len(results) * 100
    duration = time.time() - start

    print(f"  ✅ Completed {sum(results)}/200 searches in {duration:.2f}s")
    print(f"  📊 Success rate: {success_rate:.1f}%")
    print(f"  ⚡ Throughput: {200/duration:.1f} searches/sec")

    # Test 4: Mixed operations
    print("\n🎯 Test 4: Mixed operations (process, rename, search)...")
    start = time.time()
    operations_completed = 0

    def mixed_operation(i):
        if i % 3 == 0:
            return process_file(generate_test_file())
        elif i % 3 == 1:
            return rename_file(i)
        else:
            return search_operation(i)

    with concurrent.futures.ThreadPoolExecutor(max_workers=15) as executor:
        results = list(executor.map(mixed_operation, range(150)))

    success_rate = sum(results) / len(results) * 100
    duration = time.time() - start

    print(f"  ✅ Completed {sum(results)}/150 operations in {duration:.2f}s")
    print(f"  📊 Success rate: {success_rate:.1f}%")
    print(f"  ⚡ Throughput: {150/duration:.1f} ops/sec")

    print("\n" + "="*50)
    print("✅ Load testing complete!")
    print("="*50)

if __name__ == "__main__":
    run_load_test()