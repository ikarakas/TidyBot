import Foundation
import SwiftUI
import Combine

enum ConnectionStatus {
    case online
    case offline
    case syncing
}

@MainActor
class AppState: ObservableObject {
    @Published var pendingFiles: [FileItem] = []
    @Published var processedFiles: [FileItem] = []
    @Published var activeJobs: [BatchJob] = []
    @Published var presets: [Preset] = []
    @Published var isProcessing = false
    @Published var showFileImporter = false
    @Published var selectedPreset: String = "default"
    @Published var errorMessage: String?
    @Published var showError = false
    @Published var connectionStatus: ConnectionStatus = .offline
    
    private let apiClient = APIClient()
    private var cancellables = Set<AnyCancellable>()
    
    init() {
        setupBindings()
        loadPresets()
    }
    
    private func setupBindings() {
        apiClient.$isConnected
            .receive(on: DispatchQueue.main)
            .sink { [weak self] isConnected in
                self?.connectionStatus = isConnected ? .online : .offline
                if !isConnected {
                    self?.showConnectionError()
                }
            }
            .store(in: &cancellables)
    }
    
    func addFile(url: URL) {
        guard !pendingFiles.contains(where: { $0.url == url }) else { return }
        
        do {
            let attributes = try FileManager.default.attributesOfItem(atPath: url.path)
            let size = attributes[.size] as? Int64 ?? 0
            
            let fileItem = FileItem(
                url: url,
                name: url.lastPathComponent,
                size: size
            )
            
            pendingFiles.append(fileItem)
        } catch {
            showError(message: "Failed to add file: \(error.localizedDescription)")
        }
    }
    
    func removeFile(id: UUID) {
        pendingFiles.removeAll { $0.id == id }
    }
    
    func clearQueue() {
        pendingFiles.removeAll()
    }
    
    func processFiles(fileIds: [UUID]) {
        Task {
            await MainActor.run {
                isProcessing = true
            }
            
            for id in fileIds {
                guard let index = await MainActor.run(body: { 
                    pendingFiles.firstIndex(where: { $0.id == id })
                }) else { continue }
                
                await MainActor.run {
                    pendingFiles[index].status = .processing
                }
                
                do {
                    let fileUrl = await MainActor.run { pendingFiles[index].url }
                    let result = try await apiClient.processFile(url: fileUrl)
                    
                    await MainActor.run {
                        pendingFiles[index].status = .completed
                        pendingFiles[index].suggestedName = result.suggestedName
                        pendingFiles[index].confidence = result.confidenceScore
                        pendingFiles[index].organizationPath = result.organization?.suggestedPath
                        
                        // Move to processed files
                        let processedFile = pendingFiles[index]
                        processedFiles.append(processedFile)
                        pendingFiles.remove(at: index)
                    }
                    
                } catch {
                    await MainActor.run {
                        if index < pendingFiles.count {
                            pendingFiles[index].status = .failed
                            pendingFiles[index].error = error.localizedDescription
                        }
                        showError(message: "Processing failed: \(error.localizedDescription)")
                    }
                }
            }
            
            await MainActor.run {
                isProcessing = false
            }
        }
    }
    
    func startBatchProcessing() {
        guard !pendingFiles.isEmpty else { return }
        
        Task {
            isProcessing = true
            
            do {
                let urls = pendingFiles.map { $0.url }
                let job = try await apiClient.createBatchJob(files: urls)
                activeJobs.append(job)
                
                // Start monitoring job progress
                monitorJob(jobId: job.id)
                
                // Clear pending files as they're now being processed
                pendingFiles.removeAll()
                
            } catch {
                showError(message: "Failed to start batch processing: \(error.localizedDescription)")
            }
            
            isProcessing = false
        }
    }
    
    private func monitorJob(jobId: String) {
        Task {
            while true {
                do {
                    let jobStatus = try await apiClient.getBatchJobStatus(jobId: jobId)
                    
                    if let index = activeJobs.firstIndex(where: { $0.id == jobId }) {
                        activeJobs[index] = jobStatus
                    }
                    
                    if jobStatus.status == "completed" || jobStatus.status == "failed" {
                        break
                    }
                    
                    try await Task.sleep(nanoseconds: 2_000_000_000) // 2 seconds
                    
                } catch {
                    print("Failed to monitor job: \(error)")
                    break
                }
            }
        }
    }
    
    func loadPresets() {
        Task {
            do {
                presets = try await apiClient.getPresets()
            } catch {
                print("Failed to load presets: \(error)")
            }
        }
    }
    
    private func showError(message: String) {
        errorMessage = message
        showError = true
    }
    
    private func showConnectionError() {
        showError(message: "Cannot connect to TidyBot service. Please ensure the backend is running on port 11007.")
    }
}