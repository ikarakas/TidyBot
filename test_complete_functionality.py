#!/usr/bin/env python3
"""
TidyBot Complete Functionality Test
Tests all major features end-to-end
"""

import os
import requests
import tempfile
import json
from pathlib import Path
import time

BASE_URL = "http://localhost:11007/api/v1"

def test_health():
    """Test server health"""
    print("✓ Testing server health...")
    r = requests.get(f"http://localhost:11007/health")
    assert r.status_code == 200
    print("  ✅ Server is running")

def test_file_processing():
    """Test file processing with AI analysis"""
    print("✓ Testing file processing...")

    # Create test file
    test_content = "Invoice #12345\nDate: 2025-09-20\nAmount: $500.00"
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write(test_content)
        temp_path = f.name

    try:
        # Process file
        with open(temp_path, 'rb') as f:
            files = {'file': ('invoice.txt', f, 'text/plain')}
            r = requests.post(f"{BASE_URL}/files/process", files=files)

        assert r.status_code == 200
        result = r.json()
        assert 'suggested_name' in result
        assert 'confidence_score' in result
        assert result['status'] == 'completed'
        print(f"  ✅ File processed: {result['suggested_name']}")

    finally:
        os.unlink(temp_path)

def test_german_language():
    """Test German language detection"""
    print("✓ Testing German language support...")

    german_content = "Rechnung für Büromaterial\nDatum: 20.09.2025\nBetrag: 150€"
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write(german_content)
        temp_path = f.name

    try:
        with open(temp_path, 'rb') as f:
            files = {'file': ('rechnung.txt', f, 'text/plain')}
            r = requests.post(f"{BASE_URL}/files/process", files=files)

        assert r.status_code == 200
        result = r.json()
        assert 'rechnung' in result['suggested_name'].lower()
        print(f"  ✅ German detected: {result['suggested_name']}")

    finally:
        os.unlink(temp_path)

def test_file_rename():
    """Test actual file renaming on disk"""
    print("✓ Testing file rename on disk...")

    # Create test file
    test_file = Path("/tmp/test_rename_original.txt")
    test_file.write_text("Test content")

    try:
        # Rename file
        r = requests.post(f"{BASE_URL}/files/rename-on-disk", json={
            "file_path": str(test_file),
            "new_name": "test_renamed_final.txt",
            "create_backup": True,
            "update_index": False
        })

        assert r.status_code == 200
        result = r.json()
        assert result['status'] == 'success'

        # Verify file was renamed
        new_file = Path(result['new_path'])
        assert new_file.exists()
        assert not test_file.exists()
        print(f"  ✅ File renamed: {new_file.name}")

        # Cleanup
        new_file.unlink()
        if result.get('backup_path'):
            Path(result['backup_path']).unlink(missing_ok=True)

    except Exception as e:
        test_file.unlink(missing_ok=True)
        raise e

def test_batch_rename():
    """Test batch rename functionality"""
    print("✓ Testing batch rename...")

    # Create test files
    files = []
    for i in range(3):
        f = Path(f"/tmp/batch_test_{i}.txt")
        f.write_text(f"Content {i}")
        files.append(f)

    try:
        operations = [
            {"original_path": str(f), "new_name": f"renamed_{i}.txt"}
            for i, f in enumerate(files)
        ]

        r = requests.post(f"{BASE_URL}/files/batch-rename-on-disk", json={
            "operations": operations,
            "create_backup": False,
            "validate_first": True
        })

        assert r.status_code == 200
        result = r.json()
        assert result['success'] == True
        assert len(result['results']) == 3

        # Verify all renamed
        for res in result['results']:
            assert res['status'] == 'success'
            assert Path(res['new_path']).exists()
            Path(res['new_path']).unlink()

        print(f"  ✅ Batch renamed {len(result['results'])} files")

    except Exception as e:
        for f in files:
            f.unlink(missing_ok=True)
        raise e

def test_search():
    """Test search functionality"""
    print("✓ Testing search...")

    r = requests.post(f"{BASE_URL}/search/query", json={
        "query": "test document",
        "search_type": "natural"
    })

    assert r.status_code == 200
    result = r.json()
    assert 'results' in result
    assert 'total' in result
    print(f"  ✅ Search returned {len(result['results'])} results")

def test_history():
    """Test history endpoint"""
    print("✓ Testing history...")

    r = requests.get(f"{BASE_URL}/files/history")
    assert r.status_code == 200
    result = r.json()
    assert 'items' in result
    print(f"  ✅ History has {len(result['items'])} entries")

def test_validation():
    """Test filename validation"""
    print("✓ Testing filename validation...")

    r = requests.post(f"{BASE_URL}/files/validate-name?name=test<>file.txt")
    assert r.status_code == 200
    result = r.json()
    assert result['is_valid'] == False
    assert len(result['issues']) > 0
    print("  ✅ Validation detects invalid characters")

def run_all_tests():
    """Run all tests"""
    print("\n" + "="*50)
    print("🚀 TidyBot Complete Functionality Test")
    print("="*50 + "\n")

    tests = [
        test_health,
        test_file_processing,
        test_german_language,
        test_file_rename,
        test_batch_rename,
        test_search,
        test_history,
        test_validation
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            failed += 1
            print(f"  ❌ Failed: {e}")

    print("\n" + "="*50)
    print(f"📊 Results: {passed} passed, {failed} failed")

    if failed == 0:
        print("🎉 All tests passed!")
    else:
        print("⚠️ Some tests failed")

    print("="*50 + "\n")

    return failed == 0

if __name__ == "__main__":
    import sys
    success = run_all_tests()
    sys.exit(0 if success else 1)