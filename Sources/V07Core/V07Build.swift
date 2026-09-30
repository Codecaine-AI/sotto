import Foundation

/// Bundle metadata is the single source of truth for app and storage identity.
public enum V07Build: Equatable, Sendable {
    case release, development

    // Unbundled Swift runs stay isolated from the installed app's preferences.
    public static let current: Self = Bundle.main.object(forInfoDictionaryKey: "V07DevelopmentBuild") as? Bool == false
        ? .release : .development

    // A packaged app reports the name and identifier in its own Info.plist, so a
    // rebranded bundle keeps its own settings directory and Keychain service.
    public var displayName: String {
        Bundle.main.object(forInfoDictionaryKey: "CFBundleName") as? String
            ?? (self == .development ? "V07 Dev" : "V07")
    }
    public var isDevelopment: Bool { self == .development }
    public var bundleIdentifier: String {
        Bundle.main.bundleIdentifier ?? (self == .development ? "dev.davis.v07.dev" : "dev.davis.v07")
    }
    public var credentialService: String { bundleIdentifier + ".server" }
    public var windowAutosaveName: String { self == .development ? "V07DevMainWindow" : "V07MainWindow" }
    public var dataDirectory: URL {
        FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0]
            .appendingPathComponent(displayName, isDirectory: true)
    }
}
