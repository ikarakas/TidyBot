import SwiftUI

struct SettingsView: View {
    @EnvironmentObject var appState: AppState
    @AppStorage("serverURL") private var serverURL = "http://localhost:11007"
    @AppStorage("autoProcess") private var autoProcess = false
    @AppStorage("preserveOriginals") private var preserveOriginals = true
    @AppStorage("showConfidenceScores") private var showConfidenceScores = true
    @AppStorage("defaultOrganizationPath") private var defaultOrganizationPath = "~/Documents/TidyBot"
    
    var body: some View {
        TabView {
            GeneralSettingsView()
                .tabItem {
                    Label("General", systemImage: "gear")
                }
            
            ProcessingSettingsView()
                .tabItem {
                    Label("Processing", systemImage: "cpu")
                }
            
            OrganizationSettingsView()
                .tabItem {
                    Label("Organization", systemImage: "folder")
                }
            
            AdvancedSettingsView()
                .tabItem {
                    Label("Advanced", systemImage: "wrench.and.screwdriver")
                }
        }
        .frame(width: 600, height: 400)
    }
}

struct GeneralSettingsView: View {
    @AppStorage("appearance") private var appearance = "auto"
    @AppStorage("showNotifications") private var showNotifications = true
    @AppStorage("playSound") private var playSound = true
    @AppStorage("launchAtStartup") private var launchAtStartup = false
    
    var body: some View {
        Form {
            Section {
                Picker("Appearance", selection: $appearance) {
                    Text("System").tag("auto")
                    Text("Light").tag("light")
                    Text("Dark").tag("dark")
                }
                
                Toggle("Launch at startup", isOn: $launchAtStartup)
            }
            
            Section("Notifications") {
                Toggle("Show notifications", isOn: $showNotifications)
                Toggle("Play sound on completion", isOn: $playSound)
                    .disabled(!showNotifications)
            }
        }
        .formStyle(.grouped)
        .padding()
    }
}

struct ProcessingSettingsView: View {
    @AppStorage("enableOCR") private var enableOCR = true
    @AppStorage("enableObjectDetection") private var enableObjectDetection = true
    @AppStorage("enableCaptioning") private var enableCaptioning = true
    @AppStorage("maxFileSize") private var maxFileSize = 100.0
    @AppStorage("processingTimeout") private var processingTimeout = 60.0
    @AppStorage("batchSize") private var batchSize = 10.0
    
    var body: some View {
        Form {
            Section("AI Features") {
                Toggle("Enable OCR text extraction", isOn: $enableOCR)
                Toggle("Enable object detection", isOn: $enableObjectDetection)
                Toggle("Enable image captioning", isOn: $enableCaptioning)
            }
            
            Section("Processing Limits") {
                HStack {
                    Text("Max file size")
                    Slider(value: $maxFileSize, in: 10...500, step: 10)
                    Text("\(Int(maxFileSize)) MB")
                        .monospacedDigit()
                        .frame(width: 60)
                }
                
                HStack {
                    Text("Processing timeout")
                    Slider(value: $processingTimeout, in: 30...300, step: 30)
                    Text("\(Int(processingTimeout)) sec")
                        .monospacedDigit()
                        .frame(width: 60)
                }
                
                HStack {
                    Text("Batch size")
                    Slider(value: $batchSize, in: 1...50, step: 1)
                    Text("\(Int(batchSize)) files")
                        .monospacedDigit()
                        .frame(width: 60)
                }
            }
        }
        .formStyle(.grouped)
        .padding()
    }
}

struct OrganizationSettingsView: View {
    @AppStorage("autoOrganize") private var autoOrganize = true
    @AppStorage("createSubfolders") private var createSubfolders = true
    @AppStorage("dateFormat") private var dateFormat = "yyyy/MM"
    @AppStorage("duplicateHandling") private var duplicateHandling = "rename"
    @State private var basePath = "~/Documents/TidyBot"
    
    var body: some View {
        Form {
            Section("Organization Rules") {
                Toggle("Auto-organize files", isOn: $autoOrganize)
                Toggle("Create subfolders", isOn: $createSubfolders)
                    .disabled(!autoOrganize)
                
                Picker("Date format", selection: $dateFormat) {
                    Text("Year/Month (2024/01)").tag("yyyy/MM")
                    Text("Year-Month-Day (2024-01-15)").tag("yyyy-MM-dd")
                    Text("Month Year (January 2024)").tag("MMMM yyyy")
                }
                .disabled(!autoOrganize)
            }
            
            Section("File Handling") {
                Picker("Duplicate files", selection: $duplicateHandling) {
                    Text("Auto-rename").tag("rename")
                    Text("Replace").tag("replace")
                    Text("Skip").tag("skip")
                    Text("Ask each time").tag("ask")
                }
                
                HStack {
                    Text("Base folder:")
                    TextField("Path", text: $basePath)
                        .textFieldStyle(.roundedBorder)
                    Button("Browse...") {
                        selectFolder()
                    }
                }
            }
        }
        .formStyle(.grouped)
        .padding()
    }
    
    private func selectFolder() {
        let panel = NSOpenPanel()
        panel.canChooseFiles = false
        panel.canChooseDirectories = true
        panel.allowsMultipleSelection = false
        
        if panel.runModal() == .OK {
            basePath = panel.url?.path ?? basePath
        }
    }
}

struct AdvancedSettingsView: View {
    @AppStorage("serverURL") private var serverURL = "http://localhost:11007"
    @AppStorage("apiTimeout") private var apiTimeout = 30.0
    @AppStorage("enableCache") private var enableCache = true
    @AppStorage("cacheSize") private var cacheSize = 100.0
    @AppStorage("logLevel") private var logLevel = "info"
    @State private var isTestingConnection = false
    @State private var connectionStatus = ""
    
    var body: some View {
        Form {
            Section("Server Configuration") {
                HStack {
                    Text("Server URL:")
                    TextField("URL", text: $serverURL)
                        .textFieldStyle(.roundedBorder)
                }
                
                HStack {
                    Text("API Timeout:")
                    Slider(value: $apiTimeout, in: 10...120, step: 10)
                    Text("\(Int(apiTimeout)) sec")
                        .monospacedDigit()
                        .frame(width: 60)
                }
                
                HStack {
                    Button("Test Connection") {
                        testConnection()
                    }
                    .disabled(isTestingConnection)
                    
                    if isTestingConnection {
                        ProgressView()
                            .progressViewStyle(.circular)
                            .scaleEffect(0.7)
                    }
                    
                    Text(connectionStatus)
                        .foregroundColor(connectionStatus.contains("Connected") ? .green : .red)
                }
            }
            
            Section("Cache") {
                Toggle("Enable cache", isOn: $enableCache)
                
                HStack {
                    Text("Cache size:")
                    Slider(value: $cacheSize, in: 10...500, step: 10)
                        .disabled(!enableCache)
                    Text("\(Int(cacheSize)) MB")
                        .monospacedDigit()
                        .frame(width: 60)
                }
                
                Button("Clear Cache") {
                    clearCache()
                }
                .disabled(!enableCache)
            }
            
            Section("Logging") {
                Picker("Log level", selection: $logLevel) {
                    Text("Error").tag("error")
                    Text("Warning").tag("warning")
                    Text("Info").tag("info")
                    Text("Debug").tag("debug")
                }
                
                Button("Open Log Folder") {
                    openLogFolder()
                }
            }
        }
        .formStyle(.grouped)
        .padding()
    }
    
    private func testConnection() {
        isTestingConnection = true
        connectionStatus = ""
        
        Task {
            do {
                let url = URL(string: "\(serverURL)/health")!
                let (_, response) = try await URLSession.shared.data(from: url)
                
                if let httpResponse = response as? HTTPURLResponse,
                   httpResponse.statusCode == 200 {
                    connectionStatus = "✓ Connected"
                } else {
                    connectionStatus = "✗ Connection failed"
                }
            } catch {
                connectionStatus = "✗ Connection error"
            }
            
            isTestingConnection = false
        }
    }
    
    private func clearCache() {
        // Clear cache implementation
    }
    
    private func openLogFolder() {
        let logPath = NSHomeDirectory() + "/Library/Logs/TidyBot"
        NSWorkspace.shared.open(URL(fileURLWithPath: logPath))
    }
}