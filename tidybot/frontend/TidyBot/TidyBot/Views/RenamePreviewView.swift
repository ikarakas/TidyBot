import SwiftUI

struct RenamePreviewView: View {
    let files: [FileItem]
    let onApply: ([(FileItem, String)]) -> Void

    @Environment(\.dismiss) var dismiss
    @StateObject private var viewModel = RenamePreviewViewModel()
    @State private var renameSuggestions: [RenameSuggestion] = []
    @State private var isAnalyzing = false
    @State private var showError = false
    @State private var errorMessage = ""

    var body: some View {
        VStack(spacing: 0) {
            // Header
            header

            Divider()

            // Content
            if isAnalyzing {
                analyzeProgress
            } else if renameSuggestions.isEmpty {
                emptyState
            } else {
                suggestionsList
            }

            Divider()

            // Actions
            actionButtons
        }
        .frame(minWidth: 700, minHeight: 500)
        .onAppear {
            analyzeFiles()
        }
        .alert("Error", isPresented: $showError) {
            Button("OK") { }
        } message: {
            Text(errorMessage)
        }
    }

    private var header: some View {
        VStack(spacing: 8) {
            Text("AI Rename Preview")
                .font(.title2)
                .bold()

            Text("Review and edit the suggested names before applying")
                .font(.subheadline)
                .foregroundColor(.secondary)
        }
        .padding()
    }

    private var analyzeProgress: some View {
        VStack(spacing: 16) {
            ProgressView()
                .scaleEffect(1.5)

            Text("Analyzing \(files.count) file\(files.count == 1 ? "" : "s")...")
                .font(.headline)

            Text("This may take a moment while AI analyzes the content")
                .font(.caption)
                .foregroundColor(.secondary)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }

    private var emptyState: some View {
        VStack(spacing: 16) {
            Image(systemName: "doc.text.magnifyingglass")
                .font(.system(size: 48))
                .foregroundColor(.secondary)

            Text("No files to rename")
                .font(.headline)

            Text("Select files in the browser to rename them")
                .font(.caption)
                .foregroundColor(.secondary)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }

    private var suggestionsList: some View {
        ScrollView {
            VStack(spacing: 1) {
                // Headers
                HStack {
                    Text("Original Name")
                        .font(.caption)
                        .fontWeight(.medium)
                        .frame(maxWidth: .infinity, alignment: .leading)

                    Image(systemName: "arrow.right")
                        .font(.caption)
                        .foregroundColor(.secondary)
                        .frame(width: 30)

                    Text("Suggested Name")
                        .font(.caption)
                        .fontWeight(.medium)
                        .frame(maxWidth: .infinity, alignment: .leading)

                    Text("Confidence")
                        .font(.caption)
                        .fontWeight(.medium)
                        .frame(width: 80)
                }
                .padding(.horizontal)
                .padding(.vertical, 8)
                .background(Color.gray.opacity(0.1))

                Divider()

                // Suggestions
                ForEach($renameSuggestions) { $suggestion in
                    RenameSuggestionRow(suggestion: $suggestion)
                    Divider()
                }
            }
        }
    }

    private var actionButtons: some View {
        HStack {
            // Stats
            VStack(alignment: .leading, spacing: 4) {
                Text("\(renameSuggestions.count) files to rename")
                    .font(.caption)

                if let avgConfidence = averageConfidence {
                    Text("Average confidence: \(Int(avgConfidence * 100))%")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
            }

            Spacer()

            Button("Cancel") {
                dismiss()
            }
            .keyboardShortcut(.escape)

            Button("Apply All") {
                applyRenames()
            }
            .keyboardShortcut(.return)
            .disabled(renameSuggestions.isEmpty || renameSuggestions.allSatisfy { !$0.isEnabled })
        }
        .padding()
    }

    private var averageConfidence: Double? {
        let enabledSuggestions = renameSuggestions.filter { $0.isEnabled }
        guard !enabledSuggestions.isEmpty else { return nil }

        let totalConfidence = enabledSuggestions.reduce(0.0) { $0 + $1.confidence }
        return totalConfidence / Double(enabledSuggestions.count)
    }

    private func analyzeFiles() {
        Task {
            await MainActor.run {
                isAnalyzing = true
            }

            do {
                let suggestions = try await viewModel.analyzeFiles(files)

                await MainActor.run {
                    self.renameSuggestions = suggestions
                    isAnalyzing = false
                }
            } catch {
                await MainActor.run {
                    isAnalyzing = false
                    errorMessage = error.localizedDescription
                    showError = true
                }
            }
        }
    }

    private func applyRenames() {
        let enabledRenames = renameSuggestions
            .filter { $0.isEnabled }
            .compactMap { suggestion -> (FileItem, String)? in
                guard let file = files.first(where: { $0.id == suggestion.fileId }) else {
                    return nil
                }
                return (file, suggestion.suggestedName)
            }

        onApply(enabledRenames)
        dismiss()
    }
}

struct RenameSuggestionRow: View {
    @Binding var suggestion: RenameSuggestion
    @State private var isEditing = false
    @FocusState private var isFocused: Bool

    var body: some View {
        HStack {
            // Checkbox
            Toggle("", isOn: $suggestion.isEnabled)
                .toggleStyle(.checkbox)
                .labelsHidden()

            // Original name
            HStack {
                Image(systemName: suggestion.fileIcon)
                    .foregroundColor(suggestion.fileIconColor)

                Text(suggestion.originalName)
                    .lineLimit(1)
                    .truncationMode(.middle)
                    .foregroundColor(suggestion.isEnabled ? .primary : .secondary)
            }
            .frame(maxWidth: .infinity, alignment: .leading)

            // Arrow
            Image(systemName: "arrow.right")
                .font(.caption)
                .foregroundColor(.secondary)
                .frame(width: 30)

            // Suggested name (editable)
            if isEditing {
                TextField("New name", text: $suggestion.suggestedName)
                    .textFieldStyle(.roundedBorder)
                    .focused($isFocused)
                    .onSubmit {
                        isEditing = false
                    }
                    .frame(maxWidth: .infinity)
            } else {
                Text(suggestion.suggestedName)
                    .lineLimit(1)
                    .truncationMode(.middle)
                    .foregroundColor(suggestion.isEnabled ? confidenceColor : .secondary)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .contentShape(Rectangle())
                    .onTapGesture {
                        isEditing = true
                        isFocused = true
                    }
            }

            // Confidence indicator
            HStack(spacing: 4) {
                ConfidenceIndicator(confidence: suggestion.confidence)
                Text("\(Int(suggestion.confidence * 100))%")
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
            .frame(width: 80)
        }
        .padding(.horizontal)
        .padding(.vertical, 8)
        .background(suggestion.isEnabled ? Color.clear : Color.gray.opacity(0.05))
    }

    private var confidenceColor: Color {
        if suggestion.confidence >= 0.8 {
            return .green
        } else if suggestion.confidence >= 0.5 {
            return .orange
        } else {
            return .red
        }
    }
}

struct ConfidenceIndicator: View {
    let confidence: Double

    var body: some View {
        ZStack {
            Circle()
                .stroke(Color.gray.opacity(0.2), lineWidth: 2)
                .frame(width: 16, height: 16)

            Circle()
                .trim(from: 0, to: CGFloat(confidence))
                .stroke(color, lineWidth: 2)
                .frame(width: 16, height: 16)
                .rotationEffect(.degrees(-90))
        }
    }

    private var color: Color {
        if confidence >= 0.8 {
            return .green
        } else if confidence >= 0.5 {
            return .orange
        } else {
            return .red
        }
    }
}

struct RenameSuggestion: Identifiable, Equatable {
    let id = UUID()
    let fileId: String
    let originalName: String
    var suggestedName: String
    let confidence: Double
    var isEnabled: Bool
    let fileIcon: String
    let fileIconColor: Color
}

class RenamePreviewViewModel: ObservableObject {
    private let apiClient = APIClient()

    func analyzeFiles(_ files: [FileItem]) async throws -> [RenameSuggestion] {
        var suggestions: [RenameSuggestion] = []

        // Process files in parallel but limit concurrency
        await withTaskGroup(of: RenameSuggestion?.self) { group in
            for file in files {
                group.addTask {
                    do {
                        let result = try await self.processFile(file)
                        return result
                    } catch {
                        print("Error processing \(file.name): \(error)")
                        return nil
                    }
                }
            }

            for await suggestion in group {
                if let suggestion = suggestion {
                    suggestions.append(suggestion)
                }
            }
        }

        // Sort by original name
        suggestions.sort { $0.originalName.localizedCaseInsensitiveCompare($1.originalName) == .orderedAscending }

        return suggestions
    }

    private func processFile(_ file: FileItem) async throws -> RenameSuggestion {
        // Call the API to process the file
        let result = try await apiClient.processFile(at: file.url)

        let suggestedName = result["suggested_name"] as? String ?? file.name
        let confidence = result["confidence_score"] as? Double ?? 0.5

        return RenameSuggestion(
            fileId: file.id,
            originalName: file.name,
            suggestedName: suggestedName,
            confidence: confidence,
            isEnabled: confidence >= 0.5, // Auto-enable high confidence suggestions
            fileIcon: file.icon,
            fileIconColor: file.iconColor
        )
    }
}