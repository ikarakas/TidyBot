#!/usr/bin/env swift

import Foundation

// Test API connection
let url = URL(string: "http://localhost:11007/health")!
let task = URLSession.shared.dataTask(with: url) { data, response, error in
    if let error = error {
        print("Error: \(error)")
        exit(1)
    }
    
    if let data = data,
       let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any] {
        print("API Response: \(json)")
        print("✅ Backend is working!")
    } else {
        print("❌ Failed to parse response")
    }
    exit(0)
}

task.resume()
RunLoop.main.run()