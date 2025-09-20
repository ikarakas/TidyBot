import SwiftUI
import UniformTypeIdentifiers

// Simple working version of TidyBot
@main
struct SimpleTidyBotApp: App {
    var body: some Scene {
        WindowGroup {
            SimpleContentView()
                .frame(minWidth: 800, minHeight: 600)
        }
    }
}

struct SimpleContentView: View {
    @State private var isDragging = false
    @State private var statusMessage = "Drop files here to process"
    @State private var processedFiles: [ProcessedFile] = []
    @State private var isProcessing = false
    
    var body: some View {
        VStack(spacing: 20) {
            // Header
            Text("🤖 TidyBot File Processor")
                .font(.largeTitle)
                .fontWeight(.bold)
            
            // Drop Zone
            ZStack {
                RoundedRectangle(cornerRadius: 20)
                    .strokeBorder(
                        isDragging ? Color.blue : Color.gray.opacity(0.3),
                        lineWidth: 3,
                        antialiased: true
                    )
                    .background(
                        RoundedRectangle(cornerRadius: 20)
                            .fill(isDragging ? Color.blue.opacity(0.1) : Color.clear)
                    )
                
                VStack(spacing: 15) {
                    Image(systemName: "doc.badge.plus")
                        .font(.system(size: 50))
                        .foregroundColor(isDragging ? .blue : .gray)
                    
                    Text(statusMessage)
                        .font(.title2)
                        .foregroundColor(.secondary)
                    
                    if isProcessing {
                        ProgressView()
                            .progressViewStyle(.circular)
                    }
                }
            }
            .frame(height: 200)
            .onDrop(of: [.fileURL], isTargeted: $isDragging) { providers in
                handleDrop(providers: providers)
                return true
            }
            
            // Results
            if !processedFiles.isEmpty {
                VStack(alignment: .leading) {
                    Text("Processed Files:")
                        .font(.headline)
                    
                    ScrollView {
                        VStack(alignment: .leading, spacing: 10) {
                            ForEach(processedFiles) { file in
                                HStack {
                                    Image(systemName: file.success ? "checkmark.circle.fill" : "xmark.circle.fill")
                                        .foregroundColor(file.success ? .green : .red)
                                    
                                    VStack(alignment: .leading) {
                                        Text(file.originalName)
                                            .font(.caption)
                                            .foregroundColor(.secondary)
                                        
                                        if let suggestedName = file.suggestedName {
                                            Text("→ \(suggestedName)")
                                                .font(.body)
                                                .foregroundColor(.green)
                                        }
                                        
                                        if let confidence = file.confidence {
                                            Text("Confidence: \(Int(confidence * 100))%")
                                                .font(.caption2)
                                                .foregroundColor(.blue)
                                        }
                                    }
                                    
                                    Spacer()
                                }
                                .padding(8)
                                .background(Color.gray.opacity(0.1))
                                .cornerRadius(8)
                            }
                        }
                    }
                    .frame(maxHeight: 200)
                }
            }
            
            // Clear button
            if !processedFiles.isEmpty {
                Button("Clear Results") {
                    processedFiles.removeAll()
                    statusMessage = "Drop files here to process"
                }
                .buttonStyle(.borderedProminent)
            }
            
            Spacer()
        }
        .padding()
    }
    
    private func handleDrop(providers: [NSItemProvider]) {
        for provider in providers {
            provider.loadItem(forTypeIdentifier: UTType.fileURL.identifier, options: nil) { data, error in
                guard let data = data as? Data,
                      let url = URL(dataRepresentation: data, relativeTo: nil) else { return }
                
                DispatchQueue.main.async {
                    processFile(at: url)
                }
            }
        }
    }
    
    private func processFile(at url: URL) {
        isProcessing = true
        statusMessage = "Processing \(url.lastPathComponent)..."
        
        // Create multipart form data
        var request = URLRequest(url: URL(string: "http://localhost:11007/api/v1/files/process")!)
        request.httpMethod = "POST"
        
        let boundary = UUID().uuidString
        request.setValue("multipart/form-data; boundary=\(boundary)", forHTTPHeaderField: "Content-Type")
        
        var body = Data()
        
        // Add file data
        if let fileData = try? Data(contentsOf: url) {
            body.append("--\(boundary)\r\n".data(using: .utf8)!)
            body.append("Content-Disposition: form-data; name=\"file\"; filename=\"\(url.lastPathComponent)\"\r\n".data(using: .utf8)!)
            body.append("Content-Type: application/octet-stream\r\n\r\n".data(using: .utf8)!)
            body.append(fileData)
            body.append("\r\n--\(boundary)--\r\n".data(using: .utf8)!)
        }
        
        request.httpBody = body
        
        URLSession.shared.dataTask(with: request) { data, response, error in
            DispatchQueue.main.async {
                isProcessing = false
                
                if let data = data,
                   let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any] {
                    
                    let processed = ProcessedFile(
                        originalName: url.lastPathComponent,
                        suggestedName: json["suggested_name"] as? String,
                        confidence: json["confidence_score"] as? Double,
                        success: true
                    )
                    
                    processedFiles.append(processed)
                    statusMessage = "✅ Processed successfully!"
                } else {
                    let processed = ProcessedFile(
                        originalName: url.lastPathComponent,
                        suggestedName: nil,
                        confidence: nil,
                        success: false
                    )
                    
                    processedFiles.append(processed)
                    statusMessage = "❌ Processing failed"
                }
                
                // Reset status after 2 seconds
                DispatchQueue.main.asyncAfter(deadline: .now() + 2) {
                    if !isProcessing {
                        statusMessage = "Drop more files to process"
                    }
                }
            }
        }.resume()
    }
}

struct ProcessedFile: Identifiable {
    let id = UUID()
    let originalName: String
    let suggestedName: String?
    let confidence: Double?
    let success: Bool
}