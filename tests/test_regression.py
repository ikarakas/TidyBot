#!/usr/bin/env python3
"""
TidyBot Regression Testing
Tests for backward compatibility and feature stability
"""

import os
import requests
import json
import tempfile
from pathlib import Path

BASE_URL = "http://localhost:11007/api/v1"

class RegressionTests:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.tests = []

    def test(self, name, condition, details=""):
        """Record test result"""
        if condition:
            self.passed += 1
            print(f"  ✅ {name}")
            self.tests.append((name, True, details))
        else:
            self.failed += 1
            print(f"  ❌ {name}: {details}")
            self.tests.append((name, False, details))

    def run_all_tests(self):
        print("\n" + "="*50)
        print("🔍 TidyBot Regression Testing")
        print("="*50 + "\n")

        # Test 1: API Endpoint Availability
        print("📡 Testing API endpoints...")
        endpoints = [
            ("GET", "/health"),
            ("POST", "/files/process"),
            ("POST", "/files/rename-on-disk"),
            ("POST", "/files/batch-rename-on-disk"),
            ("GET", "/files/history"),
            ("POST", "/search/query"),
        ]

        for method, endpoint in endpoints:
            try:
                url = f"http://localhost:11007{endpoint}" if endpoint == "/health" else f"{BASE_URL}{endpoint}"
                if method == "GET":
                    r = requests.get(url)
                else:
                    r = requests.post(url, json={})
                self.test(f"{method} {endpoint}", r.status_code in [200, 400, 422])
            except Exception as e:
                self.test(f"{method} {endpoint}", False, str(e))

        # Test 2: File Processing Response Format
        print("\n📄 Testing file processing response format...")
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("Test content for regression")
            temp_path = f.name

        try:
            with open(temp_path, 'rb') as f:
                files = {'file': ('test.txt', f, 'text/plain')}
                r = requests.post(f"{BASE_URL}/files/process", files=files)

            if r.status_code == 200:
                data = r.json()
                required_fields = ['suggested_name', 'confidence_score', 'status', 'analysis', 'organization']
                for field in required_fields:
                    self.test(f"Response has '{field}'", field in data)
            else:
                self.test("File processing", False, f"Status {r.status_code}")
        finally:
            os.unlink(temp_path)

        # Test 3: Rename Operation Fields
        print("\n✏️ Testing rename operation...")
        test_file = Path("/tmp/regression_rename.txt")
        test_file.write_text("Regression test")

        try:
            r = requests.post(f"{BASE_URL}/files/rename-on-disk", json={
                "file_path": str(test_file),
                "new_name": "regression_renamed.txt",
                "create_backup": True,
                "update_index": False
            })

            if r.status_code == 200:
                data = r.json()
                required_fields = ['original_path', 'new_path', 'status', 'backup_path']
                for field in required_fields:
                    self.test(f"Rename has '{field}'", field in data)

                # Verify file actually renamed
                if 'new_path' in data:
                    new_file = Path(data['new_path'])
                    self.test("File actually renamed", new_file.exists())
                    if new_file.exists():
                        new_file.unlink()

                # Verify backup created
                if 'backup_path' in data and data['backup_path']:
                    backup_file = Path(data['backup_path'])
                    self.test("Backup created", backup_file.exists())
                    if backup_file.exists():
                        backup_file.unlink()
        except Exception as e:
            self.test("Rename operation", False, str(e))
        finally:
            test_file.unlink(missing_ok=True)

        # Test 4: Search Response Format
        print("\n🔎 Testing search response format...")
        try:
            r = requests.post(f"{BASE_URL}/search/query", json={
                "query": "test",
                "search_type": "natural"
            })

            if r.status_code == 200:
                data = r.json()
                self.test("Search has 'results'", 'results' in data)
                self.test("Search has 'total'", 'total' in data)
                self.test("Results is list", isinstance(data.get('results', None), list))
        except Exception as e:
            self.test("Search endpoint", False, str(e))

        # Test 5: History Format
        print("\n📚 Testing history format...")
        try:
            r = requests.get(f"{BASE_URL}/files/history")
            if r.status_code == 200:
                data = r.json()
                self.test("History has 'items'", 'items' in data)
                self.test("Items is list", isinstance(data.get('items', None), list))

                if data.get('items'):
                    item = data['items'][0]
                    required_fields = ['id', 'original_name', 'new_name', 'processing_type']
                    for field in required_fields:
                        self.test(f"History item has '{field}'", field in item)
        except Exception as e:
            self.test("History endpoint", False, str(e))

        # Test 6: German Language Support
        print("\n🇩🇪 Testing German language support...")
        german_content = "Rechnung Nummer 12345\nDatum: 20.09.2025"
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write(german_content)
            temp_path = f.name

        try:
            with open(temp_path, 'rb') as f:
                files = {'file': ('rechnung.txt', f, 'text/plain')}
                r = requests.post(f"{BASE_URL}/files/process", files=files)

            if r.status_code == 200:
                data = r.json()
                name = data.get('suggested_name', '').lower()
                self.test("German document detected", 'rechnung' in name)
        finally:
            os.unlink(temp_path)

        # Test 7: Batch Operations
        print("\n📦 Testing batch operations...")
        files = []
        for i in range(3):
            f = Path(f"/tmp/batch_regression_{i}.txt")
            f.write_text(f"Batch test {i}")
            files.append(f)

        try:
            operations = [
                {"original_path": str(f), "new_name": f"batch_renamed_{i}.txt"}
                for i, f in enumerate(files)
            ]

            r = requests.post(f"{BASE_URL}/files/batch-rename-on-disk", json={
                "operations": operations,
                "create_backup": False,
                "validate_first": True
            })

            if r.status_code == 200:
                data = r.json()
                self.test("Batch has 'success'", 'success' in data)
                self.test("Batch has 'results'", 'results' in data)

                if 'results' in data:
                    self.test("All batch operations succeeded",
                             all(r['status'] == 'success' for r in data['results']))

                    # Clean up renamed files
                    for result in data['results']:
                        if 'new_path' in result:
                            Path(result['new_path']).unlink(missing_ok=True)
        finally:
            for f in files:
                f.unlink(missing_ok=True)

        # Print summary
        print("\n" + "="*50)
        print(f"📊 Regression Test Results")
        print(f"   ✅ Passed: {self.passed}")
        print(f"   ❌ Failed: {self.failed}")
        print(f"   📈 Success Rate: {self.passed/(self.passed+self.failed)*100:.1f}%")
        print("="*50)

        return self.failed == 0

if __name__ == "__main__":
    import sys
    tester = RegressionTests()
    success = tester.run_all_tests()
    sys.exit(0 if success else 1)