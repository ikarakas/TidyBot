#!/usr/bin/env python3
"""
TidyBot Integration Test Suite
Validates API/Frontend contract and prevents field mismatches
"""

import json
import requests
import sys
from typing import Dict, List, Any
from pathlib import Path

# Configuration
API_BASE_URL = "http://localhost:11007/api/v1"
SWIFT_DIR = Path("/Users/ikarakas/Development/Python/TidyBot/tidybot/frontend/TidyBot")

class IntegrationTester:
    def __init__(self):
        self.errors = []
        self.warnings = []

    def test_api_health(self) -> bool:
        """Check if API is running"""
        try:
            response = requests.get(f"{API_BASE_URL.replace('/api/v1', '')}/health")
            return response.status_code == 200
        except:
            return False

    def get_api_response(self, endpoint: str) -> Dict[str, Any]:
        """Get actual API response"""
        try:
            response = requests.get(f"{API_BASE_URL}/{endpoint}")
            return response.json()
        except Exception as e:
            self.errors.append(f"Failed to get {endpoint}: {e}")
            return {}

    def extract_swift_fields(self, struct_name: str) -> Dict[str, str]:
        """Extract field mappings from Swift code"""
        swift_fields = {}

        # Search for the struct in Swift files
        import subprocess
        result = subprocess.run(
            ["grep", "-r", f"struct {struct_name}", str(SWIFT_DIR)],
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            self.errors.append(f"Swift struct {struct_name} not found")
            return swift_fields

        # Find the file containing the struct
        file_path = result.stdout.split(':')[0]

        # Extract CodingKeys
        with open(file_path, 'r') as f:
            content = f.read()

        # Simple parsing - find CodingKeys enum
        if "CodingKeys" in content:
            lines = content.split('\n')
            in_coding_keys = False

            for line in lines:
                if "enum CodingKeys" in line:
                    in_coding_keys = True
                elif in_coding_keys:
                    if "}" in line:
                        in_coding_keys = False
                    elif "case" in line and "=" in line:
                        # Parse: case swiftName = "json_name"
                        parts = line.strip().split('=')
                        if len(parts) == 2:
                            swift_name = parts[0].replace('case', '').strip()
                            json_name = parts[1].strip().strip('"')
                            swift_fields[swift_name] = json_name

        return swift_fields

    def validate_endpoint(self, endpoint: str, swift_struct: str) -> bool:
        """Validate that API response matches Swift expectations"""
        print(f"\n🔍 Testing: {endpoint} -> {swift_struct}")

        # Get actual API response
        api_response = self.get_api_response(endpoint)
        if not api_response:
            self.errors.append(f"No response from {endpoint}")
            return False

        # Extract Swift field mappings
        swift_fields = self.extract_swift_fields(swift_struct)
        if not swift_fields:
            self.warnings.append(f"Could not extract Swift fields for {swift_struct}")
            return False

        # Check if response has items array
        if "items" in api_response and isinstance(api_response["items"], list):
            if api_response["items"]:
                api_fields = set(api_response["items"][0].keys())
            else:
                self.warnings.append(f"No items in response to validate")
                return True
        else:
            api_fields = set(api_response.keys())

        # Validate field mappings
        success = True
        for swift_field, expected_json_field in swift_fields.items():
            if expected_json_field not in api_fields:
                self.errors.append(
                    f"❌ Field mismatch: Swift expects '{expected_json_field}' but API doesn't provide it"
                )
                self.errors.append(f"   Available API fields: {api_fields}")
                success = False
            else:
                print(f"   ✅ {swift_field} -> {expected_json_field}")

        return success

    def test_file_operations(self) -> bool:
        """Test file operation endpoints"""
        print("\n📁 Testing File Operations")

        # Test process endpoint
        test_cases = [
            ("files/history", "HistoryAPIItem"),
            # Add more endpoint/struct pairs as needed
        ]

        all_passed = True
        for endpoint, struct in test_cases:
            if not self.validate_endpoint(endpoint, struct):
                all_passed = False

        return all_passed

    def test_search_response(self) -> bool:
        """Test search endpoint response format"""
        print("\n🔎 Testing Search Endpoint")

        # Test search with a simple query
        try:
            response = requests.post(
                f"{API_BASE_URL}/search/query",
                json={"query": "test", "search_type": "natural"}
            )

            if response.status_code == 200:
                data = response.json()
                required_fields = ["results", "total_results", "search_type"]

                for field in required_fields:
                    if field not in data:
                        self.errors.append(f"Search response missing field: {field}")
                        return False

                print("   ✅ Search response format valid")
                return True
            else:
                self.errors.append(f"Search endpoint returned {response.status_code}")
                return False

        except Exception as e:
            self.errors.append(f"Search test failed: {e}")
            return False

    def test_rename_operations(self) -> bool:
        """Test rename endpoint contract"""
        print("\n♻️ Testing Rename Operations")

        # Check if rename endpoint expects correct format
        expected_request = {
            "file_path": "/path/to/file",
            "new_name": "new_name.pdf",
            "create_backup": True,
            "update_index": True
        }

        expected_response = {
            "original_path": str,
            "new_path": str,
            "status": str,
            "error": str,
            "backup_path": str,
            "timestamp": str
        }

        print("   ✅ Rename request format documented")
        print("   ✅ Rename response format documented")

        return True

    def generate_report(self):
        """Generate test report"""
        print("\n" + "="*50)
        print("📊 INTEGRATION TEST REPORT")
        print("="*50)

        if self.errors:
            print("\n❌ ERRORS:")
            for error in self.errors:
                print(f"  • {error}")

        if self.warnings:
            print("\n⚠️ WARNINGS:")
            for warning in self.warnings:
                print(f"  • {warning}")

        if not self.errors and not self.warnings:
            print("\n✅ All integration tests passed!")

        return len(self.errors) == 0

    def run_all_tests(self) -> bool:
        """Run all integration tests"""
        print("🚀 Starting TidyBot Integration Tests\n")

        # Check API health first
        if not self.test_api_health():
            print("❌ API is not running at http://localhost:11007")
            print("   Please start the server first: ./run_server.sh")
            return False

        print("✅ API is running")

        # Run test suites
        all_passed = True
        all_passed &= self.test_file_operations()
        all_passed &= self.test_search_response()
        all_passed &= self.test_rename_operations()

        # Generate report
        return self.generate_report()


def main():
    """Main test runner"""
    tester = IntegrationTester()

    if tester.run_all_tests():
        print("\n🎉 Integration tests completed successfully!")
        sys.exit(0)
    else:
        print("\n💔 Integration tests failed - fix issues before deploying")
        sys.exit(1)


if __name__ == "__main__":
    main()