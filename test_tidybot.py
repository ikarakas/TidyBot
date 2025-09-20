#!/usr/bin/env python3
"""
TidyBot Demo - Test file processing functionality
"""

import requests
import os
from pathlib import Path

API_URL = "http://localhost:11007"

def test_health():
    """Test if the API is running"""
    response = requests.get(f"{API_URL}/health")
    if response.status_code == 200:
        print("✅ API is healthy:", response.json())
        return True
    else:
        print("❌ API is not responding")
        return False

def test_file_processing():
    """Test processing a sample file"""
    # Create a test file
    test_file = Path("test_document.txt")
    test_file.write_text("""
    Invoice #12345
    Date: 2024-01-15
    Company: Acme Corporation
    
    This is a test invoice document for TidyBot processing.
    Amount Due: $1,234.56
    """)
    
    print(f"\n📄 Testing file processing with: {test_file}")
    
    # Process the file
    with open(test_file, 'rb') as f:
        files = {'file': (test_file.name, f, 'text/plain')}
        response = requests.post(
            f"{API_URL}/api/v1/files/process",
            files=files
        )
    
    if response.status_code == 200:
        result = response.json()
        print("\n✅ File processed successfully!")
        print(f"  Original name: {result.get('original_name')}")
        print(f"  Suggested name: {result.get('suggested_name')}")
        print(f"  Confidence: {result.get('confidence_score', 0):.2%}")
        
        if 'organization' in result:
            org = result['organization']
            print(f"  Suggested folder: {org.get('suggested_folder')}")
    else:
        print(f"❌ Processing failed: {response.status_code}")
        print(response.text)
    
    # Clean up
    test_file.unlink()

def test_presets():
    """Test getting presets"""
    print("\n🎨 Fetching presets...")
    response = requests.get(f"{API_URL}/api/v1/presets/")
    
    if response.status_code == 200:
        data = response.json()
        presets = data.get('presets', [])
        print(f"✅ Found {len(presets)} presets:")
        for preset in presets[:3]:
            print(f"  - {preset.get('name')}: {preset.get('description')}")
    else:
        print(f"❌ Failed to get presets: {response.status_code}")

def main():
    print("🤖 TidyBot API Test\n" + "="*40)
    
    if not test_health():
        print("\n⚠️  Please make sure the backend is running:")
        print("cd tidybot/ai_service")
        print("python -m uvicorn app.main:app --port 11007 --reload")
        return
    
    test_file_processing()
    test_presets()
    
    print("\n" + "="*40)
    print("✅ All tests completed!")
    print("\n📱 Now you can run the SwiftUI app in Xcode")
    print("The app will connect to the backend on port 11007")

if __name__ == "__main__":
    main()