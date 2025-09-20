import SwiftUI
import UniformTypeIdentifiers
import AppKit

struct HistoryView: View {
    @EnvironmentObject var appState: AppState
    @EnvironmentObject var apiClient: APIClient
    @State private var searchText = ""
    @State private var selectedTimeRange = "all"
    @State private var history: [HistoryItem] = []
    @State private var isLoading = false
    @State private var showError = false
    @State private var errorMessage = ""
    
    var filteredHistory: [HistoryItem] {
        history.filter { item in
            searchText.isEmpty || 
            item.originalName.localizedCaseInsensitiveContains(searchText) ||
            item.newName.localizedCaseInsensitiveContains(searchText)
        }
    }
    
    var body: some View {
        VStack(spacing: 0) {
            // Toolbar
            HStack {
                Label("History", systemImage: "clock.arrow.circlepath")
                    .font(.title2)
                    .fontWeight(.semibold)
                
                Spacer()
                
                Picker("Time Range", selection: $selectedTimeRange) {
                    Text("All Time").tag("all")
                    Text("Today").tag("today")
                    Text("This Week").tag("week")
                    Text("This Month").tag("month")
                }
                .pickerStyle(.segmented)
                .frame(width: 300)
                
                HStack {
                    Image(systemName: "magnifyingglass")
                        .foregroundColor(.secondary)
                    TextField("Search files...", text: $searchText)
                        .textFieldStyle(.plain)
                }
                .padding(8)
                .background(Color(NSColor.controlBackgroundColor))
                .cornerRadius(8)
                .frame(width: 200)
            }
            .padding()
            
            Divider()
            
            // History table
            Table(filteredHistory) {
                TableColumn("Original Name") { item in
                    HStack {
                        Image(systemName: item.icon)
                            .foregroundColor(.secondary)
                        Text(item.originalName)
                            .lineLimit(1)
                    }
                }
                
                TableColumn("New Name") { item in
                    Text(item.newName)
                        .foregroundColor(.green)
                        .lineLimit(1)
                }
                
                TableColumn("Confidence") { item in
                    HStack {
                        ProgressView(value: item.confidence, total: 1.0)
                            .progressViewStyle(.linear)
                            .frame(width: 60)
                        Text("\(Int(item.confidence * 100))%")
                            .font(.caption)
                            .monospacedDigit()
                    }
                }
                .width(120)
                
                TableColumn("Date") { item in
                    Text(item.processedAt, style: .date)
                        .font(.caption)
                }
                .width(100)
                
                TableColumn("Actions") { item in
                    HStack {
                        Button(action: { revertName(item: item) }) {
                            Image(systemName: "arrow.counterclockwise")
                        }
                        .buttonStyle(.plain)
                        .help("Revert name")
                        
                        Button(action: { showInFinder(item: item) }) {
                            Image(systemName: "folder")
                        }
                        .buttonStyle(.plain)
                        .help("Show in Finder")
                    }
                }
                .width(80)
            }
            
            // Summary bar
            HStack {
                Text("\(filteredHistory.count) items")
                    .font(.caption)
                    .foregroundColor(.secondary)
                
                Spacer()
                
                Button("Export History") {
                    exportHistory()
                }
                .buttonStyle(.plain)
                
                Button("Clear History") {
                    clearHistory()
                }
                .buttonStyle(.plain)
                .foregroundColor(.red)
            }
            .padding()
            .background(Color(NSColor.controlBackgroundColor))
        }
        .onAppear {
            loadHistory()
        }
        .onChange(of: selectedTimeRange) { _ in
            loadHistory()
        }
        .alert("Error", isPresented: $showError) {
            Button("OK") { }
        } message: {
            Text(errorMessage)
        }
    }
    
    private func exportHistory() {
        let csv = history.map { item in
            "\(item.originalName),\(item.newName),\(item.confidence),\(item.processedAt)"
        }.joined(separator: "\n")
        
        let savePanel = NSSavePanel()
        savePanel.allowedContentTypes = [.commaSeparatedText]
        savePanel.nameFieldStringValue = "tidybot_history.csv"
        
        savePanel.begin { response in
            if response == .OK, let url = savePanel.url {
                try? csv.write(to: url, atomically: true, encoding: .utf8)
            }
        }
    }
    
    private func clearHistory() {
        let alert = NSAlert()
        alert.messageText = "Clear History"
        alert.informativeText = "Are you sure you want to clear all processing history?"
        alert.alertStyle = .warning
        alert.addButton(withTitle: "Clear")
        alert.addButton(withTitle: "Cancel")
        
        if alert.runModal() == .alertFirstButtonReturn {
            Task {
                do {
                    try await apiClient.clearHistory()
                    await MainActor.run {
                        history.removeAll()
                    }
                } catch let error as APIError {
                    await MainActor.run {
                        errorMessage = "Failed to clear history: \(error.errorDescription ?? "Unknown error")"
                        showError = true
                    }
                } catch {
                    await MainActor.run {
                        errorMessage = "Failed to clear history: \(error.localizedDescription)"
                        showError = true
                    }
                }
            }
        }
    }
    
    private func loadHistory() {
        Task {
            await MainActor.run {
                isLoading = true
            }
            
            do {
                let items = try await apiClient.getHistory(timeRange: selectedTimeRange)
                await MainActor.run {
                    history = items.map { apiItem in
                        HistoryItem(
                            originalName: apiItem.originalName,
                            newName: apiItem.suggestedName ?? apiItem.originalName,
                            confidence: apiItem.confidence ?? 0.0,
                            processedAt: ISO8601DateFormatter().date(from: apiItem.processedAt) ?? Date(),
                            fileType: apiItem.fileType ?? "document",
                            filePath: apiItem.filePath
                        )
                    }
                    isLoading = false
                }
            } catch {
                await MainActor.run {
                    isLoading = false
                    errorMessage = "Failed to load history: \(error.localizedDescription)"
                    showError = true
                }
            }
        }
    }
    
    private func revertName(item: HistoryItem) {
        guard let path = item.filePath else { return }
        
        let url = URL(fileURLWithPath: path)
        let directory = url.deletingLastPathComponent()
        let originalURL = directory.appendingPathComponent(item.originalName)
        
        do {
            try FileManager.default.moveItem(at: url, to: originalURL)
            loadHistory() // Reload to reflect changes
        } catch {
            errorMessage = "Failed to revert name: \(error.localizedDescription)"
            showError = true
        }
    }
    
    private func showInFinder(item: HistoryItem) {
        guard let path = item.filePath else { return }
        let url = URL(fileURLWithPath: path)
        NSWorkspace.shared.activateFileViewerSelecting([url])
    }
}

struct HistoryItem: Identifiable {
    let id = UUID()
    let originalName: String
    let newName: String
    let confidence: Double
    let processedAt: Date
    let fileType: String
    let filePath: String?
    
    var icon: String {
        switch fileType {
        case "image": return "photo"
        case "document": return "doc.text"
        case "spreadsheet": return "tablecells"
        default: return "doc"
        }
    }
    
    static let sampleData: [HistoryItem] = []
}