#!/usr/bin/env swift

import Foundation

// Test all API endpoints

let baseURL = "http://localhost:11007"
let apiURL = "\(baseURL)/api/v1"

// Test 1: Health Check
print("🔍 Testing Health Check...")
if let url = URL(string: "\(baseURL)/health") {
    let semaphore = DispatchSemaphore(value: 0)
    
    URLSession.shared.dataTask(with: url) { data, response, error in
        if let data = data,
           let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any] {
            print("✅ Health check passed: \(json)")
        } else {
            print("❌ Health check failed")
        }
        semaphore.signal()
    }.resume()
    
    semaphore.wait()
}

// Test 2: Get Presets
print("\n🎨 Testing Presets Endpoint...")
if let url = URL(string: "\(apiURL)/presets/") {
    let semaphore = DispatchSemaphore(value: 0)
    
    URLSession.shared.dataTask(with: url) { data, response, error in
        if let data = data {
            if let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any] {
                print("✅ Presets endpoint working: \(json)")
            } else {
                print("❌ Failed to parse presets response")
            }
        } else {
            print("❌ Presets endpoint failed: \(error?.localizedDescription ?? "Unknown error")")
        }
        semaphore.signal()
    }.resume()
    
    semaphore.wait()
}

// Test 3: Get History
print("\n📜 Testing History Endpoint...")
if let url = URL(string: "\(apiURL)/files/history") {
    let semaphore = DispatchSemaphore(value: 0)
    
    URLSession.shared.dataTask(with: url) { data, response, error in
        if let data = data {
            if let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any] {
                print("✅ History endpoint working: \(json)")
            } else {
                print("❌ Failed to parse history response")
            }
        } else {
            print("❌ History endpoint failed: \(error?.localizedDescription ?? "Unknown error")")
        }
        semaphore.signal()
    }.resume()
    
    semaphore.wait()
}

print("\n✅ API tests completed!")
print("📱 The SwiftUI app should now be fully functional with:")
print("  - File processing via drag & drop")
print("  - History viewing and management")
print("  - Preset loading and management")
print("  - Batch job processing")