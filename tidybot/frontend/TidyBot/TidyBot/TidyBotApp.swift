import SwiftUI

@main
struct TidyBotApp: App {
    @StateObject private var appState = AppState()
    @StateObject private var apiClient = APIClient()
    
    var body: some Scene {
        WindowGroup {
            ContentView()
                .environmentObject(appState)
                .environmentObject(apiClient)
                .frame(minWidth: 1200, minHeight: 800)
        }
        .windowStyle(.automatic)
        .windowToolbarStyle(.unified(showsTitle: true))
        .commands {
            CommandGroup(replacing: .newItem) {
                Button("Process Files...") {
                    appState.showFileImporter = true
                }
                .keyboardShortcut("o", modifiers: [.command])
            }
            
            CommandMenu("Processing") {
                Button("Start Batch Processing") {
                    appState.startBatchProcessing()
                }
                .keyboardShortcut("b", modifiers: [.command])
                .disabled(appState.pendingFiles.isEmpty)
                
                Divider()
                
                Button("Clear Queue") {
                    appState.clearQueue()
                }
                .disabled(appState.pendingFiles.isEmpty)
            }
        }
        
        Settings {
            SettingsView()
                .environmentObject(appState)
        }
    }
}