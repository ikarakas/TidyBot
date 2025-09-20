import SwiftUI

struct PresetsView: View {
    @EnvironmentObject var appState: AppState
    @EnvironmentObject var apiClient: APIClient
    @State private var presets: [PresetItem] = []
    @State private var selectedPreset: PresetItem?
    @State private var showingCreateSheet = false
    @State private var isLoading = false
    @State private var showError = false
    @State private var errorMessage = ""
    
    var body: some View {
        HSplitView {
            // Presets list
            VStack(alignment: .leading, spacing: 0) {
                HStack {
                    Text("Presets")
                        .font(.headline)
                    
                    Spacer()
                    
                    Button(action: { showingCreateSheet = true }) {
                        Image(systemName: "plus")
                    }
                    .buttonStyle(.plain)
                }
                .padding()
                
                Divider()
                
                List(presets, selection: $selectedPreset) { preset in
                    PresetRowView(preset: preset)
                        .tag(preset)
                }
                .listStyle(.sidebar)
            }
            .frame(minWidth: 250, maxWidth: 350)
            
            // Preset details/editor
            if let preset = selectedPreset {
                PresetDetailView(preset: preset)
            } else {
                EmptyPresetView()
            }
        }
        .sheet(isPresented: $showingCreateSheet) {
            CreatePresetView { newPreset in
                presets.append(newPreset)
                selectedPreset = newPreset
            }
        }
        .onAppear {
            loadPresets()
        }
        .alert("Error", isPresented: $showError) {
            Button("OK") { }
        } message: {
            Text(errorMessage)
        }
    }
    
    private func loadPresets() {
        Task {
            await MainActor.run {
                isLoading = true
            }
            
            do {
                let apiPresets = try await apiClient.getPresets()
                await MainActor.run {
                    presets = apiPresets.map { preset in
                        PresetItem(
                            name: preset.name,
                            description: preset.description,
                            namingPattern: preset.settingsDict?["naming_pattern"] as? String ?? "{category}_{description}_{date}",
                            organizationStrategy: preset.settingsDict?["organization_strategy"] as? String ?? "by_type",
                            fileExtensions: preset.settingsDict?["file_extensions"] as? [String] ?? [],
                            icon: iconForPreset(preset.name),
                            isDefault: preset.isDefault ?? false
                        )
                    }
                    isLoading = false
                }
            } catch {
                await MainActor.run {
                    isLoading = false
                    errorMessage = "Failed to load presets: \(error.localizedDescription)"
                    showError = true
                    // Use default presets as fallback
                    presets = PresetItem.defaultPresets
                }
            }
        }
    }
    
    private func iconForPreset(_ name: String) -> String {
        switch name.lowercased() {
        case let n where n.contains("smart"):
            return "brain"
        case let n where n.contains("screenshot"):
            return "camera.viewfinder"
        case let n where n.contains("document"):
            return "archivebox"
        case let n where n.contains("photo"):
            return "photo"
        default:
            return "slider.horizontal.3"
        }
    }
}

struct PresetRowView: View {
    let preset: PresetItem
    
    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack {
                Image(systemName: preset.icon)
                    .foregroundColor(.accentColor)
                
                Text(preset.name)
                    .font(.headline)
                
                if preset.isDefault {
                    Text("DEFAULT")
                        .font(.caption2)
                        .padding(.horizontal, 4)
                        .padding(.vertical, 2)
                        .background(Color.accentColor.opacity(0.2))
                        .cornerRadius(4)
                }
            }
            
            Text(preset.description)
                .font(.caption)
                .foregroundColor(.secondary)
                .lineLimit(2)
        }
        .padding(.vertical, 4)
    }
}

struct PresetDetailView: View {
    let preset: PresetItem
    @State private var namingPattern: String
    @State private var organizationStrategy: String
    @State private var fileExtensions: String
    @State private var includeOCR = true
    @State private var organizeFiles = true
    
    init(preset: PresetItem) {
        self.preset = preset
        _namingPattern = State(initialValue: preset.namingPattern)
        _organizationStrategy = State(initialValue: preset.organizationStrategy)
        _fileExtensions = State(initialValue: preset.fileExtensions.joined(separator: ", "))
    }
    
    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                // Header
                HStack {
                    Image(systemName: preset.icon)
                        .font(.largeTitle)
                        .foregroundColor(.accentColor)
                    
                    VStack(alignment: .leading) {
                        Text(preset.name)
                            .font(.title)
                            .fontWeight(.semibold)
                        
                        Text(preset.description)
                            .font(.body)
                            .foregroundColor(.secondary)
                    }
                    
                    Spacer()
                    
                    Button("Save Changes") {
                        savePreset()
                    }
                    .buttonStyle(.borderedProminent)
                    .disabled(preset.isDefault)
                }
                
                Divider()
                
                // Naming Pattern
                GroupBox {
                    VStack(alignment: .leading, spacing: 12) {
                        Label("Naming Pattern", systemImage: "textformat")
                            .font(.headline)
                        
                        TextField("Pattern", text: $namingPattern)
                            .textFieldStyle(.roundedBorder)
                            .font(.system(.body, design: .monospaced))
                        
                        Text("Available variables: {category}, {description}, {date}, {year}, {month}, {day}, {original_name}")
                            .font(.caption)
                            .foregroundColor(.secondary)
                        
                        Text("Preview: ") +
                        Text(previewName())
                            .foregroundColor(.green)
                            .font(.system(.body, design: .monospaced))
                    }
                }
                
                // Organization Settings
                GroupBox {
                    VStack(alignment: .leading, spacing: 12) {
                        Label("Organization", systemImage: "folder")
                            .font(.headline)
                        
                        Picker("Strategy", selection: $organizationStrategy) {
                            Text("By Type").tag("by_type")
                            Text("By Date").tag("by_date")
                            Text("By Category").tag("by_category")
                            Text("By Project").tag("by_project")
                        }
                        
                        Toggle("Organize files after renaming", isOn: $organizeFiles)
                        
                        HStack {
                            Text("Base Path:")
                            Text("~/Documents/TidyBot/")
                                .font(.system(.body, design: .monospaced))
                                .foregroundColor(.secondary)
                        }
                    }
                }
                
                // File Filters
                GroupBox {
                    VStack(alignment: .leading, spacing: 12) {
                        Label("File Filters", systemImage: "line.horizontal.3.decrease.circle")
                            .font(.headline)
                        
                        TextField("Extensions (comma-separated)", text: $fileExtensions)
                            .textFieldStyle(.roundedBorder)
                        
                        Toggle("Include OCR for images", isOn: $includeOCR)
                    }
                }
                
                // Actions
                if !preset.isDefault {
                    HStack {
                        Button("Delete Preset") {
                            deletePreset()
                        }
                        .buttonStyle(.plain)
                        .foregroundColor(.red)
                        
                        Spacer()
                    }
                    .padding(.top)
                }
            }
            .padding()
        }
    }
    
    private func previewName() -> String {
        let preview = namingPattern
            .replacingOccurrences(of: "{category}", with: "document")
            .replacingOccurrences(of: "{description}", with: "sample_file")
            .replacingOccurrences(of: "{date}", with: "20240115")
            .replacingOccurrences(of: "{year}", with: "2024")
            .replacingOccurrences(of: "{month}", with: "01")
            .replacingOccurrences(of: "{day}", with: "15")
            .replacingOccurrences(of: "{original_name}", with: "original")
        
        return preview + ".pdf"
    }
    
    private func savePreset() {
        // Save preset changes
    }
    
    private func deletePreset() {
        // Delete preset with confirmation
    }
}

struct EmptyPresetView: View {
    var body: some View {
        VStack {
            Image(systemName: "slider.horizontal.3")
                .font(.system(size: 60))
                .foregroundColor(.secondary)
            
            Text("No Preset Selected")
                .font(.title2)
                .padding(.top)
            
            Text("Select a preset to view and edit its settings")
                .font(.caption)
                .foregroundColor(.secondary)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
}

struct CreatePresetView: View {
    @Environment(\.dismiss) var dismiss
    @State private var name = ""
    @State private var description = ""
    @State private var namingPattern = "{category}_{description}_{date}"
    
    let onCreate: (PresetItem) -> Void
    
    var body: some View {
        VStack(spacing: 20) {
            Text("Create New Preset")
                .font(.title2)
                .fontWeight(.semibold)
            
            Form {
                TextField("Name", text: $name)
                TextField("Description", text: $description)
                TextField("Naming Pattern", text: $namingPattern)
            }
            
            HStack {
                Button("Cancel") {
                    dismiss()
                }
                .buttonStyle(.plain)
                
                Spacer()
                
                Button("Create") {
                    let preset = PresetItem(
                        name: name,
                        description: description,
                        namingPattern: namingPattern,
                        organizationStrategy: "by_type",
                        fileExtensions: [],
                        icon: "slider.horizontal.3",
                        isDefault: false
                    )
                    onCreate(preset)
                    dismiss()
                }
                .buttonStyle(.borderedProminent)
                .disabled(name.isEmpty)
            }
        }
        .padding()
        .frame(width: 400, height: 250)
    }
}

struct PresetItem: Identifiable, Hashable {
    let id = UUID()
    let name: String
    let description: String
    let namingPattern: String
    let organizationStrategy: String
    let fileExtensions: [String]
    let icon: String
    let isDefault: Bool
    
    static let defaultPresets: [PresetItem] = [
        PresetItem(
            name: "Smart Naming",
            description: "Intelligently names files based on content analysis",
            namingPattern: "{category}_{description}_{date}",
            organizationStrategy: "by_type",
            fileExtensions: [],
            icon: "brain",
            isDefault: true
        ),
        PresetItem(
            name: "Screenshot Organizer",
            description: "Organize screenshots by date and content",
            namingPattern: "screenshot_{description}_{date}",
            organizationStrategy: "by_date",
            fileExtensions: ["png", "jpg"],
            icon: "camera.viewfinder",
            isDefault: true
        ),
        PresetItem(
            name: "Document Archive",
            description: "Archive documents by type and date",
            namingPattern: "{category}_{title}_{date}",
            organizationStrategy: "by_category",
            fileExtensions: ["pdf", "docx", "txt"],
            icon: "archivebox",
            isDefault: true
        )
    ]
}