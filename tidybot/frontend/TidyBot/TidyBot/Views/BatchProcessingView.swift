import SwiftUI

struct BatchProcessingView: View {
    @EnvironmentObject var appState: AppState
    @State private var selectedJob: BatchJob?
    
    var body: some View {
        HSplitView {
            // Jobs list
            VStack(alignment: .leading, spacing: 0) {
                Text("Active Jobs")
                    .font(.headline)
                    .padding()
                
                Divider()
                
                ScrollView {
                    LazyVStack(spacing: 8) {
                        ForEach(appState.activeJobs) { job in
                            JobRowView(job: job, isSelected: selectedJob?.id == job.id)
                                .onTapGesture {
                                    selectedJob = job
                                }
                        }
                    }
                    .padding()
                }
            }
            .frame(minWidth: 300, maxWidth: 400)
            
            // Job details
            if let job = selectedJob {
                JobDetailView(job: job)
            } else {
                EmptyJobDetailView()
            }
        }
    }
}

struct JobRowView: View {
    let job: BatchJob
    let isSelected: Bool
    
    var statusColor: Color {
        switch job.status {
        case "completed": return .green
        case "failed": return .red
        case "processing": return .blue
        default: return .gray
        }
    }
    
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Circle()
                    .fill(statusColor)
                    .frame(width: 8, height: 8)
                
                Text("Job \(String(job.id.prefix(8)))")
                    .font(.headline)
                
                Spacer()
                
                Text(job.status.capitalized)
                    .font(.caption)
                    .padding(.horizontal, 8)
                    .padding(.vertical, 2)
                    .background(statusColor.opacity(0.2))
                    .cornerRadius(4)
            }
            
            HStack {
                ProgressView(value: job.progressPercentage, total: 100)
                    .progressViewStyle(.linear)
                
                Text("\(Int(job.progressPercentage))%")
                    .font(.caption)
                    .monospacedDigit()
            }
            
            HStack {
                Label("\(job.completedTasks)/\(job.totalTasks)", systemImage: "checkmark.circle")
                    .font(.caption)
                
                if job.failedTasks > 0 {
                    Label("\(job.failedTasks)", systemImage: "xmark.circle")
                        .font(.caption)
                        .foregroundColor(.red)
                }
            }
        }
        .padding()
        .background(
            RoundedRectangle(cornerRadius: 8)
                .fill(isSelected ? Color.accentColor.opacity(0.1) : Color(NSColor.controlBackgroundColor))
        )
        .overlay(
            RoundedRectangle(cornerRadius: 8)
                .strokeBorder(isSelected ? Color.accentColor : Color.clear, lineWidth: 2)
        )
    }
}

struct JobDetailView: View {
    let job: BatchJob
    @State private var showingResults = false
    
    var body: some View {
        VStack(alignment: .leading, spacing: 20) {
            // Header
            HStack {
                VStack(alignment: .leading) {
                    Text("Job Details")
                        .font(.title2)
                        .fontWeight(.semibold)
                    
                    Text("ID: \(job.id)")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
                
                Spacer()
                
                Button("View Results") {
                    showingResults = true
                }
                .disabled(job.status != "completed")
            }
            
            Divider()
            
            // Statistics
            LazyVGrid(columns: [
                GridItem(.flexible()),
                GridItem(.flexible()),
                GridItem(.flexible())
            ], spacing: 20) {
                StatCard(title: "Total Files", value: "\(job.totalTasks)", icon: "doc.stack")
                StatCard(title: "Processed", value: "\(job.completedTasks)", icon: "checkmark.circle.fill", color: .green)
                StatCard(title: "Failed", value: "\(job.failedTasks)", icon: "xmark.circle.fill", color: .red)
            }
            
            // Progress
            VStack(alignment: .leading, spacing: 8) {
                Text("Progress")
                    .font(.headline)
                
                ProgressView(value: job.progressPercentage, total: 100) {
                    Text("\(Int(job.progressPercentage))% Complete")
                }
                .progressViewStyle(.linear)
            }
            
            // Timeline
            VStack(alignment: .leading, spacing: 8) {
                Text("Timeline")
                    .font(.headline)
                
                TimelineRow(label: "Created", time: job.createdAt)
                
                if let completedAt = job.completedAt {
                    TimelineRow(label: "Completed", time: completedAt)
                }
            }
            
            Spacer()
        }
        .padding()
        .sheet(isPresented: $showingResults) {
            JobResultsView(jobId: job.id)
        }
    }
}

struct EmptyJobDetailView: View {
    var body: some View {
        VStack {
            Image(systemName: "square.stack.3d.up")
                .font(.system(size: 60))
                .foregroundColor(.secondary)
            
            Text("No Job Selected")
                .font(.title2)
                .padding(.top)
            
            Text("Select a job from the list to view details")
                .font(.caption)
                .foregroundColor(.secondary)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
}

struct StatCard: View {
    let title: String
    let value: String
    let icon: String
    var color: Color = .accentColor
    
    var body: some View {
        VStack(spacing: 8) {
            Image(systemName: icon)
                .font(.title2)
                .foregroundColor(color)
            
            Text(value)
                .font(.title)
                .fontWeight(.semibold)
            
            Text(title)
                .font(.caption)
                .foregroundColor(.secondary)
        }
        .frame(maxWidth: .infinity)
        .padding()
        .background(Color(NSColor.controlBackgroundColor))
        .cornerRadius(8)
    }
}

struct TimelineRow: View {
    let label: String
    let time: String
    
    var body: some View {
        HStack {
            Text(label)
                .foregroundColor(.secondary)
            
            Spacer()
            
            Text(formatDate(time))
                .font(.caption)
                .monospacedDigit()
        }
    }
    
    private func formatDate(_ dateString: String) -> String {
        let formatter = ISO8601DateFormatter()
        guard let date = formatter.date(from: dateString) else { return dateString }
        
        let displayFormatter = DateFormatter()
        displayFormatter.dateStyle = .medium
        displayFormatter.timeStyle = .short
        
        return displayFormatter.string(from: date)
    }
}

struct JobResultsView: View {
    let jobId: String
    @Environment(\.dismiss) var dismiss
    
    var body: some View {
        VStack {
            HStack {
                Text("Job Results")
                    .font(.title2)
                    .fontWeight(.semibold)
                
                Spacer()
                
                Button("Done") {
                    dismiss()
                }
            }
            .padding()
            
            Divider()
            
            // Results table would go here
            Text("Results for job \(jobId)")
                .padding()
            
            Spacer()
        }
        .frame(width: 600, height: 400)
    }
}