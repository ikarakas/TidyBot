import SwiftUI
import UniformTypeIdentifiers

struct FileBrowserView: View {
    @StateObject private var viewModel = FileBrowserViewModel()
    @EnvironmentObject var appState: AppState
    @State private var selectedFiles: Set<FileItem> = []
    @State private var showRenamePreview = false
    @State private var isProcessing = false
    @State private var currentPath = FileManager.default.homeDirectoryForCurrentUser
    @State private var showFolderPicker = false
    @State private var selectedFolderForOrganization: URL?

    var body: some View {
        VStack(spacing: 0) {
            // Navigation Bar
            navigationBar

            Divider()

            // File List
            ScrollView {
                LazyVStack(spacing: 1) {
                    ForEach(viewModel.files) { file in
                        FileRowView(
                            file: file,
                            isSelected: selectedFiles.contains(file),
                            onTap: {
                                toggleSelection(file)
                            },
                            onDoubleTap: {
                                if file.isDirectory {
                                    navigateToFolder(file.url)
                                } else {
                                    openFile(file.url)
                                }
                            }
                        )
                        .contextMenu {
                            contextMenuItems(for: file)
                        }
                    }
                }
                .padding(.horizontal)
            }

            Divider()

            // Status Bar
            statusBar
        }
        .frame(minWidth: 600, minHeight: 400)
        .onAppear {
            viewModel.loadFiles(at: currentPath)
        }
        .sheet(isPresented: $showRenamePreview) {
            RenamePreviewView(
                files: Array(selectedFiles),
                onApply: { renamedFiles in
                    applyRenames(renamedFiles)
                }
            )
        }
        .fileImporter(
            isPresented: $showFolderPicker,
            allowedContentTypes: [.folder],
            allowsMultipleSelection: false
        ) { result in
            switch result {
            case .success(let urls):
                if let url = urls.first {
                    selectedFolderForOrganization = url
                    navigateToFolder(url)
                }
            case .failure(let error):
                print("Folder selection failed: \(error)")
            }
        }
    }

    private var navigationBar: some View {
        HStack {
            // Back button
            Button(action: navigateBack) {
                Image(systemName: "chevron.left")
            }
            .disabled(!viewModel.canNavigateBack)

            // Forward button
            Button(action: navigateForward) {
                Image(systemName: "chevron.right")
            }
            .disabled(!viewModel.canNavigateForward)

            // Path breadcrumbs
            HStack(spacing: 4) {
                ForEach(viewModel.pathComponents, id: \.self) { component in
                    Button(component.lastPathComponent) {
                        navigateToPath(component)
                    }
                    .buttonStyle(.plain)

                    if component != viewModel.pathComponents.last {
                        Image(systemName: "chevron.right")
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }
                }
            }

            Spacer()

            // View options
            Menu {
                Button("Show Hidden Files") {
                    viewModel.showHiddenFiles.toggle()
                }

                Divider()

                Menu("Sort By") {
                    Button("Name") { viewModel.sortBy = .name }
                    Button("Date Modified") { viewModel.sortBy = .dateModified }
                    Button("Size") { viewModel.sortBy = .size }
                    Button("Type") { viewModel.sortBy = .type }
                }
            } label: {
                Image(systemName: "line.3.horizontal.decrease.circle")
            }

            // Choose Folder button
            Button(action: { showFolderPicker = true }) {
                Label("Choose Folder", systemImage: "folder.badge.plus")
            }

            // AI Rename button
            Button(action: showRenamePreview) {
                Label("AI Rename", systemImage: "wand.and.stars")
            }
            .disabled(selectedFiles.isEmpty)

            // Organize Folder button
            if selectedFolderForOrganization != nil {
                Button(action: organizeSelectedFolder) {
                    Label("Organize Folder", systemImage: "folder.badge.gearshape")
                }
            }
        }
        .padding(.horizontal)
        .padding(.vertical, 8)
    }

    private var statusBar: some View {
        HStack {
            Text("\(viewModel.files.count) items")

            if !selectedFiles.isEmpty {
                Text("• \(selectedFiles.count) selected")
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
        }
        .padding(.horizontal)
        .padding(.vertical, 4)
        .font(.caption)
        .foregroundColor(.secondary)
    }

    @ViewBuilder
    private func contextMenuItems(for file: FileItem) -> some View {
        Button("AI Rename") {
            selectedFiles = [file]
            showRenamePreview = true
        }

        Button("Open") {
            openFile(file.url)
        }

        if file.isDirectory {
            Button("Index Folder") {
                Task {
                    await viewModel.indexFolder(file.url)
                }
            }
        }

        Divider()

        Button("Show in Finder") {
            NSWorkspace.shared.selectFile(
                file.url.path,
                inFileViewerRootedAtPath: file.url.deletingLastPathComponent().path
            )
        }
    }

    private func toggleSelection(_ file: FileItem) {
        if selectedFiles.contains(file) {
            selectedFiles.remove(file)
        } else {
            selectedFiles.insert(file)
        }
    }

    private func navigateToFolder(_ url: URL) {
        currentPath = url
        viewModel.loadFiles(at: url)
    }

    private func navigateToPath(_ url: URL) {
        navigateToFolder(url)
    }

    private func navigateBack() {
        viewModel.navigateBack()
        if let url = viewModel.currentURL {
            currentPath = url
        }
    }

    private func navigateForward() {
        viewModel.navigateForward()
        if let url = viewModel.currentURL {
            currentPath = url
        }
    }

    private func openFile(_ url: URL) {
        NSWorkspace.shared.open(url)
    }

    private func showRenamePreview() {
        guard !selectedFiles.isEmpty else { return }
        showRenamePreview = true
    }

    private func applyRenames(_ renamedFiles: [(FileItem, String)]) {
        Task {
            isProcessing = true
            await viewModel.applyRenames(renamedFiles)
            selectedFiles.removeAll()
            isProcessing = false
        }
    }

    private func organizeSelectedFolder() {
        guard let folderURL = selectedFolderForOrganization else { return }

        Task {
            isProcessing = true
            await viewModel.organizeFolder(folderURL)
            isProcessing = false
            // Refresh the view after organization
            viewModel.reloadFiles()
        }
    }
}

struct FileRowView: View {
    let file: FileItem
    let isSelected: Bool
    let onTap: () -> Void
    let onDoubleTap: () -> Void

    var body: some View {
        HStack {
            Image(systemName: file.icon)
                .foregroundColor(file.iconColor)
                .frame(width: 20)

            VStack(alignment: .leading, spacing: 2) {
                Text(file.name)
                    .lineLimit(1)
                    .truncationMode(.middle)

                HStack(spacing: 8) {
                    Text(file.formattedSize)
                    Text("•")
                    Text(file.formattedDate)
                }
                .font(.caption)
                .foregroundColor(.secondary)
            }

            Spacer()

            if isSelected {
                Image(systemName: "checkmark.circle.fill")
                    .foregroundColor(.accentColor)
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

class FileBrowserViewModel: ObservableObject {
    @Published var files: [FileItem] = []
    @Published var showHiddenFiles = false {
        didSet { reloadFiles() }
    }
    @Published var sortBy: SortOption = .name {
        didSet { sortFiles() }
    }
    @Published var isIndexing = false
    @Published var currentURL: URL?

    private var navigationHistory: [URL] = []
    private var navigationIndex = -1
    private let apiClient = APIClient()

    var canNavigateBack: Bool {
        navigationIndex > 0
    }

    var canNavigateForward: Bool {
        navigationIndex < navigationHistory.count - 1
    }

    var pathComponents: [URL] {
        guard let url = currentURL else { return [] }
        var components: [URL] = []
        var currentPath = url

        while currentPath.path != "/" {
            components.insert(currentPath, at: 0)
            currentPath = currentPath.deletingLastPathComponent()
        }

        return components
    }

    enum SortOption {
        case name, dateModified, size, type
    }

    func loadFiles(at url: URL) {
        currentURL = url
        addToHistory(url)

        Task { @MainActor in
            do {
                let fileManager = FileManager.default
                let contents = try fileManager.contentsOfDirectory(
                    at: url,
                    includingPropertiesForKeys: [.isDirectoryKey, .fileSizeKey, .contentModificationDateKey],
                    options: showHiddenFiles ? [] : [.skipsHiddenFiles]
                )

                files = contents.map { url in
                    FileItem(url: url)
                }

                sortFiles()
            } catch {
                print("Error loading files: \(error)")
                files = []
            }
        }
    }

    func reloadFiles() {
        if let url = currentURL {
            loadFiles(at: url)
        }
    }

    func sortFiles() {
        switch sortBy {
        case .name:
            files.sort { $0.name.localizedCaseInsensitiveCompare($1.name) == .orderedAscending }
        case .dateModified:
            files.sort { ($0.dateModified ?? Date.distantPast) > ($1.dateModified ?? Date.distantPast) }
        case .size:
            files.sort { $0.size > $1.size }
        case .type:
            files.sort { $0.fileExtension.localizedCaseInsensitiveCompare($1.fileExtension) == .orderedAscending }
        }

        // Always put directories first
        files.sort { $0.isDirectory && !$1.isDirectory }
    }

    func navigateBack() {
        guard canNavigateBack else { return }
        navigationIndex -= 1
        let url = navigationHistory[navigationIndex]
        currentURL = url
        loadFiles(at: url)
    }

    func navigateForward() {
        guard canNavigateForward else { return }
        navigationIndex += 1
        let url = navigationHistory[navigationIndex]
        currentURL = url
        loadFiles(at: url)
    }

    private func addToHistory(_ url: URL) {
        // Remove any forward history when navigating to a new location
        if navigationIndex < navigationHistory.count - 1 {
            navigationHistory.removeLast(navigationHistory.count - 1 - navigationIndex)
        }

        navigationHistory.append(url)
        navigationIndex = navigationHistory.count - 1
    }

    func indexFolder(_ url: URL) async {
        await MainActor.run {
            isIndexing = true
        }

        // Call indexing API endpoint
        // This would be implemented when the indexing endpoint is added

        await MainActor.run {
            isIndexing = false
        }
    }

    func applyRenames(_ renamedFiles: [(FileItem, String)]) async {
        let operations = renamedFiles.map { file, newName in
            ["original_path": file.url.path, "new_name": newName]
        }

        do {
            let response = try await apiClient.batchRenameOnDisk(operations: operations)

            if response["success"] as? Bool == true {
                await MainActor.run {
                    reloadFiles()
                }
            }
        } catch {
            print("Error applying renames: \(error)")
        }
    }

    func organizeFolder(_ url: URL) async {
        await MainActor.run {
            isIndexing = true
        }

        do {
            // Get all files in the folder
            let fileManager = FileManager.default
            let contents = try fileManager.contentsOfDirectory(
                at: url,
                includingPropertiesForKeys: [.isDirectoryKey],
                options: [.skipsHiddenFiles]
            )

            // Filter out directories and process each file
            let files = contents.filter { url in
                let isDirectory = (try? url.resourceValues(forKeys: [.isDirectoryKey]))?.isDirectory ?? false
                return !isDirectory
            }

            // Process each file with AI naming and organization
            for fileURL in files {
                _ = try await apiClient.processFile(at: fileURL)
            }

            await MainActor.run {
                isIndexing = false
                reloadFiles()
            }
        } catch {
            print("Error organizing folder: \(error)")
            await MainActor.run {
                isIndexing = false
            }
        }
    }
}