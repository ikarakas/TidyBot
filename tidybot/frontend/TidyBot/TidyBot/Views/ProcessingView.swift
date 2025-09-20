import SwiftUI
import UniformTypeIdentifiers

struct ProcessingView: View {
    @EnvironmentObject var appState: AppState
    @EnvironmentObject var apiClient: APIClient
    @State private var isDragging = false
    @State private var showFileImporter = false
    @State private var selectedFiles: Set<FileItem.ID> = []
    
    var body: some View {
        VStack(spacing: 0) {
            if appState.pendingFiles.isEmpty {
                EmptyDropZoneView(isDragging: $isDragging, showFileImporter: $showFileImporter)
            } else {
                FileListView(files: $appState.pendingFiles, selectedFiles: $selectedFiles)
                
                ProcessingControlsView(selectedFiles: $selectedFiles)
                    .padding()
                    .background(Color(NSColor.controlBackgroundColor))
            }
        }
        .onDrop(of: [.fileURL], isTargeted: $isDragging) { providers in
            handleDrop(providers: providers)
        }
        .fileImporter(
            isPresented: $showFileImporter,
            allowedContentTypes: [.item],
            allowsMultipleSelection: true
        ) { result in
            handleFileImport(result: result)
        }
        .toolbar {
            ToolbarItemGroup {
                Button(action: { showFileImporter = true }) {
                    Label("Add Files", systemImage: "plus.circle")
                }
                
                Button(action: { appState.clearQueue() }) {
                    Label("Clear All", systemImage: "trash")
                }
                .disabled(appState.pendingFiles.isEmpty)
            }
        }
    }
    
    private func handleDrop(providers: [NSItemProvider]) -> Bool {
        for provider in providers {
            provider.loadItem(forTypeIdentifier: UTType.fileURL.identifier, options: nil) { data, _ in
                guard let data = data as? Data,
                      let url = URL(dataRepresentation: data, relativeTo: nil) else { return }
                
                DispatchQueue.main.async {
                    appState.addFile(url: url)
                }
            }
        }
        return true
    }
    
    private func handleFileImport(result: Result<[URL], Error>) {
        switch result {
        case .success(let urls):
            for url in urls {
                appState.addFile(url: url)
            }
        case .failure(let error):
            print("Error importing files: \(error)")
        }
    }
}

struct EmptyDropZoneView: View {
    @Binding var isDragging: Bool
    @Binding var showFileImporter: Bool
    @State private var pulseAnimation = false
    
    var body: some View {
        ZStack {
            RoundedRectangle(cornerRadius: 20)
                .strokeBorder(
                    style: StrokeStyle(lineWidth: 3, dash: [10]),
                    antialiased: true
                )
                .foregroundColor(isDragging ? .accentColor : Color.secondary.opacity(0.3))
                .animation(.easeInOut(duration: 0.2), value: isDragging)
            
            VStack(spacing: 20) {
                Image(systemName: "doc.badge.plus")
                    .font(.system(size: 60))
                    .foregroundColor(.secondary)
                    .scaleEffect(pulseAnimation ? 1.1 : 1.0)
                    .animation(.easeInOut(duration: 1.5).repeatForever(autoreverses: true), value: pulseAnimation)
                
                Text("Drop files here to process")
                    .font(.title2)
                    .fontWeight(.medium)
                
                Text("or")
                    .font(.caption)
                    .foregroundColor(.secondary)
                
                Button("Browse Files") {
                    showFileImporter = true
                }
                .buttonStyle(.borderedProminent)
                .controlSize(.large)
            }
        }
        .padding(40)
        .onAppear {
            pulseAnimation = true
        }
    }
}

struct FileListView: View {
    @Binding var files: [FileItem]
    @Binding var selectedFiles: Set<FileItem.ID>
    
    var body: some View {
        ScrollView {
            LazyVStack(spacing: 8) {
                ForEach(files) { file in
                    FileRowView(file: file, isSelected: selectedFiles.contains(file.id))
                        .onTapGesture {
                            if selectedFiles.contains(file.id) {
                                selectedFiles.remove(file.id)
                            } else {
                                selectedFiles.insert(file.id)
                            }
                        }
                }
            }
            .padding()
        }
    }
}

struct FileRowView: View {
    let file: FileItem
    let isSelected: Bool
    @State private var isHovering = false
    
    var body: some View {
        HStack(spacing: 16) {
            Image(systemName: file.icon)
                .font(.title2)
                .foregroundColor(.accentColor)
                .frame(width: 40)
            
            VStack(alignment: .leading, spacing: 4) {
                Text(file.name)
                    .font(.headline)
                    .lineLimit(1)
                
                HStack {
                    Text(file.formattedSize)
                        .font(.caption)
                        .foregroundColor(.secondary)
                    
                    if let suggestedName = file.suggestedName {
                        Text("→")
                            .foregroundColor(.secondary)
                        Text(suggestedName)
                            .font(.caption)
                            .foregroundColor(.green)
                    }
                }
            }
            
            Spacer()
            
            if file.status == .processing {
                ProgressView()
                    .progressViewStyle(.circular)
                    .scaleEffect(0.7)
            } else if file.status == .completed {
                Image(systemName: "checkmark.circle.fill")
                    .foregroundColor(.green)
            } else if file.status == .failed {
                Image(systemName: "exclamationmark.triangle.fill")
                    .foregroundColor(.red)
            }
            
            if let confidence = file.confidence {
                ConfidenceIndicator(confidence: confidence)
            }
        }
        .padding()
        .background(
            RoundedRectangle(cornerRadius: 10)
                .fill(isSelected ? Color.accentColor.opacity(0.1) : 
                     (isHovering ? Color.gray.opacity(0.1) : Color.clear))
        )
        .overlay(
            RoundedRectangle(cornerRadius: 10)
                .strokeBorder(isSelected ? Color.accentColor : Color.clear, lineWidth: 2)
        )
        .onHover { hovering in
            isHovering = hovering
        }
    }
}

struct ConfidenceIndicator: View {
    let confidence: Double
    
    var color: Color {
        switch confidence {
        case 0.8...1.0: return .green
        case 0.5..<0.8: return .yellow
        default: return .red
        }
    }
    
    var body: some View {
        HStack(spacing: 4) {
            Circle()
                .fill(color)
                .frame(width: 8, height: 8)
            Text("\(Int(confidence * 100))%")
                .font(.caption2)
                .foregroundColor(.secondary)
        }
    }
}

struct ProcessingControlsView: View {
    @Binding var selectedFiles: Set<FileItem.ID>
    @EnvironmentObject var appState: AppState
    @State private var selectedPreset = "default"
    @State private var organizeFiles = true
    
    var body: some View {
        HStack {
            Picker("Preset", selection: $selectedPreset) {
                Text("Smart Naming").tag("default")
                Text("Screenshot Organizer").tag("screenshot")
                Text("Document Archive").tag("document")
                Text("Photo Library").tag("photo")
            }
            .pickerStyle(.menu)
            .frame(width: 200)
            
            Toggle("Organize Files", isOn: $organizeFiles)
            
            Spacer()
            
            Button("Process Selected") {
                let selectedIds = Array(selectedFiles)
                selectedFiles.removeAll()
                appState.processFiles(fileIds: selectedIds)
            }
            .buttonStyle(.borderedProminent)
            .disabled(selectedFiles.isEmpty || appState.isProcessing)
            
            Button("Process All") {
                let allIds = appState.pendingFiles.map { $0.id }
                appState.processFiles(fileIds: allIds)
            }
            .buttonStyle(.borderedProminent)
            .disabled(appState.pendingFiles.isEmpty || appState.isProcessing)
            
            if appState.isProcessing {
                ProgressView()
                    .progressViewStyle(.circular)
                    .scaleEffect(0.7)
            }
        }
    }
}

