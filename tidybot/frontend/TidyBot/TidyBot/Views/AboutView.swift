import SwiftUI

struct AboutView: View {
    var body: some View {
        VStack(spacing: 20) {
            // App icon (you can replace this with your actual app icon)
            Image(systemName: "doc.badge.gearshape.fill")
                .font(.system(size: 64))
                .foregroundStyle(.blue.gradient)
            
            VStack(spacing: 8) {
                Text("TidyBot")
                    .font(.largeTitle)
                    .fontWeight(.bold)
                
                Text("Intelligent File Organization Assistant")
                    .font(.headline)
                    .foregroundStyle(.secondary)
                
                Text("Version 1.0.0")
                    .font(.subheadline)
                    .foregroundStyle(.tertiary)
            }
            
            VStack(spacing: 12) {
                Text("TidyBot uses AI to automatically organize your files using OCR, object detection, and image captioning to understand content and sort files intelligently.")
                    .multilineTextAlignment(.center)
                    .font(.body)
                    .foregroundStyle(.secondary)
                    .frame(maxWidth: 300)
                
                Divider()
                    .padding(.horizontal)
                
                VStack(spacing: 4) {
                    Text("© 2024 TidyBot")
                        .font(.caption)
                        .foregroundStyle(.tertiary)
                    
                    HStack(spacing: 16) {
                        Button("Website") {
                            if let url = URL(string: "https://example.com") {
                                NSWorkspace.shared.open(url)
                            }
                        }
                        .controlSize(.small)
                        
                        Button("Privacy Policy") {
                            if let url = URL(string: "https://example.com/privacy") {
                                NSWorkspace.shared.open(url)
                            }
                        }
                        .controlSize(.small)
                        
                        Button("Support") {
                            if let url = URL(string: "https://example.com/support") {
                                NSWorkspace.shared.open(url)
                            }
                        }
                        .controlSize(.small)
                    }
                    .font(.caption)
                }
            }
        }
        .padding(30)
        .frame(width: 400, height: 450)
    }
}

#Preview {
    AboutView()
}