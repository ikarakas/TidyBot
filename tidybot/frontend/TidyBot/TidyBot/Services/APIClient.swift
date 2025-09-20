import Foundation
import Combine

class APIClient: ObservableObject {
    private let baseURL = "http://localhost:11007/api/v1"
    private var cancellables = Set<AnyCancellable>()
    
    @Published var isConnected = false
    @Published var currentJobs: [BatchJob] = []
    
    init() {
        checkConnection()
    }
    
    func checkConnection() {
        guard let url = URL(string: "http://localhost:11007/health") else { return }
        
        URLSession.shared.dataTaskPublisher(for: url)
            .map { _ in true }
            .catch { _ in Just(false) }
            .receive(on: DispatchQueue.main)
            .assign(to: &$isConnected)
    }
    
    func processFile(url: URL) async throws -> ProcessingResult {
        let endpoint = "\(baseURL)/files/process"
        
        var request = URLRequest(url: URL(string: endpoint)!)
        request.httpMethod = "POST"
        
        let boundary = UUID().uuidString
        request.setValue("multipart/form-data; boundary=\(boundary)", forHTTPHeaderField: "Content-Type")
        
        let fileData = try Data(contentsOf: url)
        let fileName = url.lastPathComponent
        
        var body = Data()
        body.append("--\(boundary)\r\n".data(using: .utf8)!)
        body.append("Content-Disposition: form-data; name=\"file\"; filename=\"\(fileName)\"\r\n".data(using: .utf8)!)
        body.append("Content-Type: application/octet-stream\r\n\r\n".data(using: .utf8)!)
        body.append(fileData)
        body.append("\r\n--\(boundary)--\r\n".data(using: .utf8)!)
        
        request.httpBody = body
        
        let (data, response) = try await URLSession.shared.data(for: request)
        
        guard let httpResponse = response as? HTTPURLResponse,
              httpResponse.statusCode == 200 else {
            throw APIError.serverError
        }
        
        return try JSONDecoder().decode(ProcessingResult.self, from: data)
    }
    
    func createBatchJob(files: [URL]) async throws -> BatchJob {
        let endpoint = "\(baseURL)/batch/process"
        
        var request = URLRequest(url: URL(string: endpoint)!)
        request.httpMethod = "POST"
        
        let boundary = UUID().uuidString
        request.setValue("multipart/form-data; boundary=\(boundary)", forHTTPHeaderField: "Content-Type")
        
        var body = Data()
        
        for file in files {
            let fileData = try Data(contentsOf: file)
            let fileName = file.lastPathComponent
            
            body.append("--\(boundary)\r\n".data(using: .utf8)!)
            body.append("Content-Disposition: form-data; name=\"files\"; filename=\"\(fileName)\"\r\n".data(using: .utf8)!)
            body.append("Content-Type: application/octet-stream\r\n\r\n".data(using: .utf8)!)
            body.append(fileData)
            body.append("\r\n".data(using: .utf8)!)
        }
        
        body.append("--\(boundary)--\r\n".data(using: .utf8)!)
        request.httpBody = body
        
        let (data, response) = try await URLSession.shared.data(for: request)
        
        guard let httpResponse = response as? HTTPURLResponse,
              httpResponse.statusCode == 200 else {
            throw APIError.serverError
        }
        
        return try JSONDecoder().decode(BatchJob.self, from: data)
    }
    
    func getBatchJobStatus(jobId: String) async throws -> BatchJob {
        let endpoint = "\(baseURL)/batch/status/\(jobId)"
        
        guard let url = URL(string: endpoint) else {
            throw APIError.invalidURL
        }
        
        let (data, response) = try await URLSession.shared.data(from: url)
        
        guard let httpResponse = response as? HTTPURLResponse,
              httpResponse.statusCode == 200 else {
            throw APIError.serverError
        }
        
        return try JSONDecoder().decode(BatchJob.self, from: data)
    }
    
    func getPresets() async throws -> [Preset] {
        let endpoint = "\(baseURL)/presets/"
        
        guard let url = URL(string: endpoint) else {
            throw APIError.invalidURL
        }
        
        let (data, response) = try await URLSession.shared.data(from: url)
        
        guard let httpResponse = response as? HTTPURLResponse,
              httpResponse.statusCode == 200 else {
            throw APIError.serverError
        }
        
        struct PresetsResponse: Codable {
            let presets: [Preset]
        }
        
        let presetsResponse = try JSONDecoder().decode(PresetsResponse.self, from: data)
        return presetsResponse.presets
    }
    
    func getProcessingHistory(limit: Int = 100) async throws -> [ProcessingResult] {
        let endpoint = "\(baseURL)/files/history?limit=\(limit)"
        
        guard let url = URL(string: endpoint) else {
            throw APIError.invalidURL
        }
        
        let (data, response) = try await URLSession.shared.data(from: url)
        
        guard let httpResponse = response as? HTTPURLResponse,
              httpResponse.statusCode == 200 else {
            throw APIError.serverError
        }
        
        struct HistoryResponse: Codable {
            let items: [ProcessingResult]
        }
        
        let historyResponse = try JSONDecoder().decode(HistoryResponse.self, from: data)
        return historyResponse.items
    }
    
    func getHistory(timeRange: String = "all") async throws -> [HistoryAPIItem] {
        var endpoint = "\(baseURL)/files/history"
        if timeRange != "all" {
            endpoint += "?time_range=\(timeRange)"
        }
        
        guard let url = URL(string: endpoint) else {
            throw APIError.invalidURL
        }
        
        let (data, response) = try await URLSession.shared.data(from: url)
        
        guard let httpResponse = response as? HTTPURLResponse,
              httpResponse.statusCode == 200 else {
            throw APIError.serverError
        }
        
        struct HistoryResponse: Codable {
            let items: [HistoryAPIItem]
        }
        
        let historyResponse = try JSONDecoder().decode(HistoryResponse.self, from: data)
        return historyResponse.items
    }
    
    func clearHistory() async throws {
        let endpoint = "\(baseURL)/files/history/clear"

        guard let url = URL(string: endpoint) else {
            throw APIError.invalidURL
        }

        var request = URLRequest(url: url)
        request.httpMethod = "DELETE"
        request.setValue("application/json", forHTTPHeaderField: "Accept")

        let (data, response) = try await URLSession.shared.data(for: request)

        guard let httpResponse = response as? HTTPURLResponse else {
            throw APIError.networkError
        }

        if httpResponse.statusCode != 200 {
            if let errorData = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
               let detail = errorData["detail"] as? String {
                throw APIError.serverError
            }
            throw APIError.serverError
        }
    }

    // MARK: - New File Operation Endpoints

    func renameFileOnDisk(filePath: String, newName: String, createBackup: Bool = true) async throws -> RenameResult {
        let endpoint = "\(baseURL)/files/rename-on-disk"

        guard let url = URL(string: endpoint) else {
            throw APIError.invalidURL
        }

        let body = [
            "file_path": filePath,
            "new_name": newName,
            "create_backup": createBackup,
            "update_index": true
        ] as [String : Any]

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONSerialization.data(withJSONObject: body)

        let (data, response) = try await URLSession.shared.data(for: request)

        guard let httpResponse = response as? HTTPURLResponse,
              httpResponse.statusCode == 200 else {
            throw APIError.serverError
        }

        return try JSONDecoder().decode(RenameResult.self, from: data)
    }

    func batchRenameOnDisk(operations: [[String: String]], createBackup: Bool = true) async throws -> [String: Any] {
        let endpoint = "\(baseURL)/files/batch-rename-on-disk"

        guard let url = URL(string: endpoint) else {
            throw APIError.invalidURL
        }

        let body = [
            "operations": operations,
            "create_backup": createBackup,
            "validate_first": true
        ] as [String : Any]

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONSerialization.data(withJSONObject: body)

        let (data, response) = try await URLSession.shared.data(for: request)

        guard let httpResponse = response as? HTTPURLResponse,
              httpResponse.statusCode == 200 else {
            throw APIError.serverError
        }

        return try JSONSerialization.jsonObject(with: data) as? [String: Any] ?? [:]
    }

    func searchFiles(params: [String: Any]) async throws -> [[String: Any]] {
        let endpoint = "\(baseURL)/search/query"

        guard let url = URL(string: endpoint) else {
            throw APIError.invalidURL
        }

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONSerialization.data(withJSONObject: params)

        let (data, response) = try await URLSession.shared.data(for: request)

        guard let httpResponse = response as? HTTPURLResponse,
              httpResponse.statusCode == 200 else {
            throw APIError.serverError
        }

        let result = try JSONSerialization.jsonObject(with: data) as? [String: Any] ?? [:]
        return result["results"] as? [[String: Any]] ?? []
    }

    func processFile(at fileURL: URL) async throws -> [String: Any] {
        let endpoint = "\(baseURL)/files/process"

        guard let url = URL(string: endpoint) else {
            throw APIError.invalidURL
        }

        var request = URLRequest(url: url)
        request.httpMethod = "POST"

        let boundary = UUID().uuidString
        request.setValue("multipart/form-data; boundary=\(boundary)", forHTTPHeaderField: "Content-Type")

        let fileData = try Data(contentsOf: fileURL)
        let fileName = fileURL.lastPathComponent

        var body = Data()
        body.append("--\(boundary)\r\n".data(using: .utf8)!)
        body.append("Content-Disposition: form-data; name=\"file\"; filename=\"\(fileName)\"\r\n".data(using: .utf8)!)
        body.append("Content-Type: application/octet-stream\r\n\r\n".data(using: .utf8)!)
        body.append(fileData)
        body.append("\r\n--\(boundary)--\r\n".data(using: .utf8)!)

        request.httpBody = body

        let (data, response) = try await URLSession.shared.data(for: request)

        guard let httpResponse = response as? HTTPURLResponse,
              httpResponse.statusCode == 200 else {
            throw APIError.serverError
        }

        return try JSONSerialization.jsonObject(with: data) as? [String: Any] ?? [:]
    }

    func undoLastOperation() async throws -> [String: Any] {
        let endpoint = "\(baseURL)/files/undo-last-operation"

        guard let url = URL(string: endpoint) else {
            throw APIError.invalidURL
        }

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")

        let (data, response) = try await URLSession.shared.data(for: request)

        guard let httpResponse = response as? HTTPURLResponse,
              httpResponse.statusCode == 200 else {
            throw APIError.serverError
        }

        return try JSONSerialization.jsonObject(with: data) as? [String: Any] ?? [:]
    }
}

struct RenameResult: Codable {
    let originalPath: String
    let newPath: String?
    let status: String
    let error: String?
    let backupPath: String?
    let timestamp: String

    enum CodingKeys: String, CodingKey {
        case originalPath = "original_path"
        case newPath = "new_path"
        case status
        case error
        case backupPath = "backup_path"
        case timestamp
    }
}

struct HistoryAPIItem: Codable {
    let originalName: String
    let suggestedName: String?
    let confidence: Double?
    let processedAt: String
    let fileType: String?
    let filePath: String?
    
    enum CodingKeys: String, CodingKey {
        case originalName = "original_name"
        case suggestedName = "new_name"
        case confidence = "confidence_score"
        case processedAt = "processed_at"
        case fileType = "file_type"
        case filePath = "file_path"
    }
}

enum APIError: LocalizedError {
    case invalidURL
    case serverError
    case decodingError
    case networkError
    
    var errorDescription: String? {
        switch self {
        case .invalidURL:
            return "Invalid URL"
        case .serverError:
            return "Server error occurred"
        case .decodingError:
            return "Failed to decode response"
        case .networkError:
            return "Network connection error"
        }
    }
}