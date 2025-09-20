import SwiftUI

struct SearchView: View {
    @StateObject private var viewModel = SearchViewModel()
    @EnvironmentObject var appState: AppState
    @State private var searchQuery = ""
    @State private var selectedResult: SearchResult?
    @State private var showIndexingSettings = false

    var body: some View {
        VStack(spacing: 0) {
            // Search bar
            searchBar

            Divider()

            // Search results or empty state
            if viewModel.isSearching {
                searchingView
            } else if searchQuery.isEmpty {
                emptyStateView
            } else if viewModel.searchResults.isEmpty {
                noResultsView
            } else {
                searchResultsView
            }

            Divider()

            // Status bar
            statusBar
        }
        .frame(minWidth: 700, minHeight: 500)
        .sheet(isPresented: $showIndexingSettings) {
            IndexingSettingsView()
        }
    }

    private var searchBar: some View {
        VStack(spacing: 12) {
            HStack {
                Image(systemName: "magnifyingglass")
                    .foregroundColor(.secondary)

                TextField("Search naturally: 'Find the paper about quantum computing from last year'",
                         text: $searchQuery)
                    .textFieldStyle(.plain)
                    .font(.title3)
                    .onSubmit {
                        performSearch()
                    }

                if !searchQuery.isEmpty {
                    Button(action: { searchQuery = "" }) {
                        Image(systemName: "xmark.circle.fill")
                            .foregroundColor(.secondary)
                    }
                    .buttonStyle(.plain)
                }

                Button("Search") {
                    performSearch()
                }
                .disabled(searchQuery.isEmpty)
            }
            .padding(.horizontal)
            .padding(.vertical, 12)

            // Search filters
            HStack {
                Menu("File Type") {
                    Button("All Types") { viewModel.fileTypeFilter = nil }
                    Divider()
                    Button("Documents") { viewModel.fileTypeFilter = .document }
                    Button("Images") { viewModel.fileTypeFilter = .image }
                    Button("Videos") { viewModel.fileTypeFilter = .video }
                    Button("Archives") { viewModel.fileTypeFilter = .archive }
                }
                .menuStyle(.borderlessButton)

                Menu("Date Range") {
                    Button("Any Time") { viewModel.dateRangeFilter = nil }
                    Divider()
                    Button("Today") { viewModel.dateRangeFilter = .today }
                    Button("This Week") { viewModel.dateRangeFilter = .thisWeek }
                    Button("This Month") { viewModel.dateRangeFilter = .thisMonth }
                    Button("This Year") { viewModel.dateRangeFilter = .thisYear }
                    Button("Last Year") { viewModel.dateRangeFilter = .lastYear }
                }
                .menuStyle(.borderlessButton)

                Toggle("Content Only", isOn: $viewModel.searchContentOnly)
                    .toggleStyle(.button)

                Spacer()

                Button(action: { showIndexingSettings = true }) {
                    Label("Indexing Settings", systemImage: "gearshape")
                }
            }
            .padding(.horizontal)
            .font(.caption)
        }
        .padding(.vertical, 8)
    }

    private var searchingView: some View {
        VStack(spacing: 16) {
            ProgressView()
                .scaleEffect(1.5)

            Text("Searching...")
                .font(.headline)

            Text(viewModel.searchStatusMessage)
                .font(.caption)
                .foregroundColor(.secondary)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }

    private var emptyStateView: some View {
        VStack(spacing: 20) {
            Image(systemName: "magnifyingglass")
                .font(.system(size: 64))
                .foregroundColor(.secondary)

            VStack(spacing: 8) {
                Text("Natural Language Search")
                    .font(.title2)
                    .bold()

                Text("Search your files using natural language")
                    .font(.subheadline)
                    .foregroundColor(.secondary)
            }

            VStack(alignment: .leading, spacing: 12) {
                Text("Example searches:")
                    .font(.caption)
                    .fontWeight(.medium)

                VStack(alignment: .leading, spacing: 8) {
                    SearchExampleRow(query: "Invoices from last month")
                    SearchExampleRow(query: "Screenshots of the dashboard")
                    SearchExampleRow(query: "PDF files about machine learning")
                    SearchExampleRow(query: "Photos from summer vacation 2024")
                    SearchExampleRow(query: "Excel spreadsheets with budget data")
                }
            }
            .padding()
            .background(Color.gray.opacity(0.05))
            .cornerRadius(8)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .padding()
    }

    private var noResultsView: some View {
        VStack(spacing: 16) {
            Image(systemName: "doc.text.magnifyingglass")
                .font(.system(size: 48))
                .foregroundColor(.secondary)

            Text("No results found")
                .font(.headline)

            Text("Try adjusting your search query or filters")
                .font(.caption)
                .foregroundColor(.secondary)

            if !viewModel.indexedFolders.isEmpty {
                VStack(alignment: .leading, spacing: 8) {
                    Text("Currently indexed folders:")
                        .font(.caption)
                        .fontWeight(.medium)

                    ForEach(viewModel.indexedFolders, id: \.self) { folder in
                        Label(folder.lastPathComponent, systemImage: "folder")
                            .font(.caption)
                    }
                }
                .padding()
                .background(Color.gray.opacity(0.05))
                .cornerRadius(8)
            }
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .padding()
    }

    private var searchResultsView: some View {
        ScrollView {
            LazyVStack(spacing: 1) {
                ForEach(viewModel.searchResults) { result in
                    SearchResultRow(
                        result: result,
                        isSelected: selectedResult?.id == result.id,
                        onTap: {
                            selectedResult = result
                        },
                        onDoubleTap: {
                            openFile(result.path)
                        }
                    )
                }
            }
            .padding(.horizontal)
        }
    }

    private var statusBar: some View {
        HStack {
            // Connection status
            ConnectionStatusIndicator(status: appState.connectionStatus)

            if viewModel.searchResults.count > 0 {
                Text("\(viewModel.searchResults.count) results")
                    .font(.caption)
            }

            Spacer()

            if viewModel.isIndexing {
                HStack(spacing: 4) {
                    ProgressView()
                        .scaleEffect(0.5)
                    Text("Indexing...")
                        .font(.caption)
                }
            }

            Text("Indexed: \(viewModel.indexedFileCount) files")
                .font(.caption)
                .foregroundColor(.secondary)
        }
        .padding(.horizontal)
        .padding(.vertical, 4)
    }

    private func performSearch() {
        guard !searchQuery.isEmpty else { return }
        Task {
            await viewModel.search(query: searchQuery)
        }
    }

    private func openFile(_ path: String) {
        NSWorkspace.shared.open(URL(fileURLWithPath: path))
    }
}

struct SearchExampleRow: View {
    let query: String

    var body: some View {
        HStack {
            Image(systemName: "arrow.right.circle")
                .font(.caption)
                .foregroundColor(.secondary)

            Text(query)
                .font(.caption)
                .foregroundColor(.secondary)
        }
    }
}

struct SearchResultRow: View {
    let result: SearchResult
    let isSelected: Bool
    let onTap: () -> Void
    let onDoubleTap: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Image(systemName: result.fileIcon)
                    .foregroundColor(result.fileIconColor)
                    .frame(width: 20)

                VStack(alignment: .leading, spacing: 4) {
                    Text(result.fileName)
                        .fontWeight(.medium)
                        .lineLimit(1)

                    Text(result.path)
                        .font(.caption)
                        .foregroundColor(.secondary)
                        .lineLimit(1)
                        .truncationMode(.middle)
                }

                Spacer()

                if !result.isAvailableOffline {
                    Image(systemName: "cloud")
                        .foregroundColor(.secondary)
                }

                VStack(alignment: .trailing, spacing: 4) {
                    Text(result.formattedDate)
                        .font(.caption)
                        .foregroundColor(.secondary)

                    if result.relevanceScore > 0 {
                        RelevanceIndicator(score: result.relevanceScore)
                    }
                }
            }

            if !result.snippet.isEmpty {
                Text(result.snippet)
                    .font(.caption)
                    .foregroundColor(.secondary)
                    .lineLimit(2)
                    .padding(.horizontal, 24)
            }
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 8)
        .background(isSelected ? Color.accentColor.opacity(0.1) : Color.clear)
        .contentShape(Rectangle())
        .onTapGesture {
            onTap()
        }
        .onTapGesture(count: 2) {
            onDoubleTap()
        }
    }
}

struct RelevanceIndicator: View {
    let score: Double

    var body: some View {
        HStack(spacing: 2) {
            ForEach(0..<5) { index in
                Image(systemName: "star.fill")
                    .font(.system(size: 8))
                    .foregroundColor(
                        Double(index) < score * 5 ? .yellow : Color.gray.opacity(0.2)
                    )
            }
        }
    }
}

struct ConnectionStatusIndicator: View {
    let status: ConnectionStatus

    var body: some View {
        HStack(spacing: 4) {
            Circle()
                .fill(statusColor)
                .frame(width: 8, height: 8)

            Text(statusText)
                .font(.caption)
                .foregroundColor(.secondary)
        }
    }

    private var statusColor: Color {
        switch status {
        case .online:
            return .green
        case .offline:
            return .orange
        case .syncing:
            return .blue
        }
    }

    private var statusText: String {
        switch status {
        case .online:
            return "Online"
        case .offline:
            return "Offline"
        case .syncing:
            return "Syncing"
        }
    }
}

struct SearchResult: Identifiable {
    let id = UUID()
    let fileName: String
    let path: String
    let snippet: String
    let fileIcon: String
    let fileIconColor: Color
    let dateModified: Date
    let relevanceScore: Double
    let isAvailableOffline: Bool

    var formattedDate: String {
        let formatter = RelativeDateTimeFormatter()
        formatter.unitsStyle = .abbreviated
        return formatter.localizedString(for: dateModified, relativeTo: Date())
    }
}

enum ConnectionStatus {
    case online
    case offline
    case syncing
}

enum FileTypeFilter {
    case document
    case image
    case video
    case archive
}

enum DateRangeFilter {
    case today
    case thisWeek
    case thisMonth
    case thisYear
    case lastYear
}

class SearchViewModel: ObservableObject {
    @Published var searchResults: [SearchResult] = []
    @Published var isSearching = false
    @Published var isIndexing = false
    @Published var searchStatusMessage = ""
    @Published var indexedFileCount = 0
    @Published var indexedFolders: [URL] = []

    @Published var fileTypeFilter: FileTypeFilter?
    @Published var dateRangeFilter: DateRangeFilter?
    @Published var searchContentOnly = false

    private let apiClient = APIClient()

    func search(query: String) async {
        await MainActor.run {
            isSearching = true
            searchStatusMessage = "Searching local files..."
            searchResults = []
        }

        do {
            // Build search parameters
            var params: [String: Any] = ["query": query]

            if let fileType = fileTypeFilter {
                params["file_type"] = fileTypeToString(fileType)
            }

            if let dateRange = dateRangeFilter {
                params["date_range"] = dateRangeToString(dateRange)
            }

            params["content_only"] = searchContentOnly

            // Perform search
            let results = try await apiClient.searchFiles(params: params)

            // Convert to SearchResult objects
            let searchResults = results.compactMap { dict -> SearchResult? in
                guard let path = dict["path"] as? String,
                      let fileName = URL(fileURLWithPath: path).lastPathComponent as String? else {
                    return nil
                }

                return SearchResult(
                    fileName: fileName,
                    path: path,
                    snippet: dict["snippet"] as? String ?? "",
                    fileIcon: getFileIcon(for: path),
                    fileIconColor: getFileIconColor(for: path),
                    dateModified: Date(), // Would parse from dict
                    relevanceScore: dict["score"] as? Double ?? 0.0,
                    isAvailableOffline: dict["is_local"] as? Bool ?? true
                )
            }

            await MainActor.run {
                self.searchResults = searchResults
                isSearching = false
            }
        } catch {
            await MainActor.run {
                searchStatusMessage = "Search failed: \(error.localizedDescription)"
                isSearching = false
            }
        }
    }

    private func fileTypeToString(_ type: FileTypeFilter) -> String {
        switch type {
        case .document: return "document"
        case .image: return "image"
        case .video: return "video"
        case .archive: return "archive"
        }
    }

    private func dateRangeToString(_ range: DateRangeFilter) -> String {
        switch range {
        case .today: return "today"
        case .thisWeek: return "this_week"
        case .thisMonth: return "this_month"
        case .thisYear: return "this_year"
        case .lastYear: return "last_year"
        }
    }

    private func getFileIcon(for path: String) -> String {
        let ext = URL(fileURLWithPath: path).pathExtension.lowercased()
        switch ext {
        case "pdf": return "doc.fill"
        case "doc", "docx": return "doc.text.fill"
        case "xls", "xlsx": return "tablecells.fill"
        case "ppt", "pptx": return "doc.richtext.fill"
        case "jpg", "jpeg", "png", "gif": return "photo.fill"
        case "mp4", "mov", "avi": return "video.fill"
        case "zip", "rar", "7z": return "archivebox.fill"
        default: return "doc.fill"
        }
    }

    private func getFileIconColor(for path: String) -> Color {
        let ext = URL(fileURLWithPath: path).pathExtension.lowercased()
        switch ext {
        case "pdf": return .red
        case "doc", "docx": return .blue
        case "xls", "xlsx": return .green
        case "ppt", "pptx": return .orange
        case "jpg", "jpeg", "png", "gif": return .purple
        case "mp4", "mov", "avi": return .pink
        case "zip", "rar", "7z": return .gray
        default: return .gray
        }
    }
}