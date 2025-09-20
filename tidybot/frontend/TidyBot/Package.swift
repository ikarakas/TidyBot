// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "TidyBot",
    platforms: [
        .macOS(.v14)
    ],
    products: [
        .library(
            name: "TidyBot",
            targets: ["TidyBot"]),
    ],
    dependencies: [
        // Add any Swift package dependencies here if needed
    ],
    targets: [
        .target(
            name: "TidyBot",
            dependencies: []),
        .testTarget(
            name: "TidyBotTests",
            dependencies: ["TidyBot"]),
    ]
)