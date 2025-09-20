import SwiftUI
import UniformTypeIdentifiers

struct ContentView: View {
    @EnvironmentObject var appState: AppState
    @EnvironmentObject var apiClient: APIClient
    @State private var isDragging = false
    @State private var selectedTab = "process"
    
    var body: some View {
        NavigationSplitView {
            SidebarView(selectedTab: $selectedTab)
        } detail: {
            ZStack {
                VisualEffectBackground()
                
                switch selectedTab {
                case "process":
                    ProcessingView()
                case "history":
                    HistoryView()
                case "presets":
                    PresetsView()
                case "batch":
                    BatchProcessingView()
                default:
                    ProcessingView()
                }
            }
        }
        .navigationSplitViewStyle(.balanced)
    }
}

struct SidebarView: View {
    @Binding var selectedTab: String
    @EnvironmentObject var appState: AppState
    
    var body: some View {
        List {
            Section("Main") {
                Button(action: { selectedTab = "process" }) {
                    Label("Process Files", systemImage: "doc.badge.gearshape")
                        .badge(appState.pendingFiles.count)
                }
                .buttonStyle(SidebarButtonStyle(isSelected: selectedTab == "process"))
                
                Button(action: { selectedTab = "batch" }) {
                    Label("Batch Jobs", systemImage: "square.stack.3d.up")
                        .badge(appState.activeJobs.count)
                }
                .buttonStyle(SidebarButtonStyle(isSelected: selectedTab == "batch"))
            }
            
            Section("Library") {
                Button(action: { selectedTab = "history" }) {
                    Label("History", systemImage: "clock.arrow.circlepath")
                }
                .buttonStyle(SidebarButtonStyle(isSelected: selectedTab == "history"))
                
                Button(action: { selectedTab = "presets" }) {
                    Label("Presets", systemImage: "slider.horizontal.3")
                }
                .buttonStyle(SidebarButtonStyle(isSelected: selectedTab == "presets"))
            }
        }
        .listStyle(SidebarListStyle())
        .navigationTitle("TidyBot")
        .frame(minWidth: 250)
        .toolbar {
            ToolbarItem(placement: .navigation) {
                Button(action: toggleSidebar) {
                    Image(systemName: "sidebar.left")
                }
            }
        }
    }
    
    private func toggleSidebar() {
        NSApp.keyWindow?.firstResponder?.tryToPerform(
            #selector(NSSplitViewController.toggleSidebar(_:)),
            with: nil
        )
    }
}

struct SidebarButtonStyle: ButtonStyle {
    let isSelected: Bool
    
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(.vertical, 4)
            .padding(.horizontal, 8)
            .background(
                RoundedRectangle(cornerRadius: 6)
                    .fill(isSelected ? Color.accentColor.opacity(0.2) : 
                          configuration.isPressed ? Color.gray.opacity(0.2) : Color.clear)
            )
            .foregroundColor(isSelected ? .accentColor : .primary)
    }
}

struct VisualEffectBackground: NSViewRepresentable {
    func makeNSView(context: Context) -> NSVisualEffectView {
        let view = NSVisualEffectView()
        view.blendingMode = .behindWindow
        view.material = .underWindowBackground
        view.state = .active
        return view
    }
    
    func updateNSView(_ nsView: NSVisualEffectView, context: Context) {}
}