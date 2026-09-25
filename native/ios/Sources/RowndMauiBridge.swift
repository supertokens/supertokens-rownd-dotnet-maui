import Foundation
import ReSwift
import Rownd
import UIKit

@objc(RWNRowndBridge)
public final class RowndMauiBridge: NSObject, StoreSubscriber {
    public typealias StoreSubscriberStateType = RowndState
    private var listener: ((Bool, Bool, String?) -> Void)?
    private var configured = false
    private var disposed = false

    @objc(configureWithAppKey:apiDomain:apiBasePath:hubURL:scheme:completion:)
    public func configure(appKey: String, apiDomain: String, apiBasePath: String,
                          hubURL: String, scheme: String, completion: @escaping (String?) -> Void) {
        guard Thread.isMainThread, !configured, !disposed,
              !appKey.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty,
              let api = URLComponents(string: apiDomain),
              ["http", "https"].contains(api.scheme ?? ""), api.host != nil,
              api.user == nil, api.password == nil, api.query == nil, api.fragment == nil,
              api.path.isEmpty || api.path == "/",
              apiBasePath.hasPrefix("/"),
              let hub = URL(string: hubURL), ["http", "https"].contains(hub.scheme ?? ""),
              hub.host != nil, hub.user == nil, hub.password == nil, hub.fragment == nil,
              scheme.range(of: "^[A-Za-z][A-Za-z0-9+.-]*$", options: .regularExpression) != nil,
              !["http", "https"].contains(scheme.lowercased()) else {
            completion("invalid_configuration_or_lifecycle")
            return
        }
        configured = true
        Rownd.config.baseUrl = hubURL
        Rownd.config.deepLinkScheme = scheme
        // Clipboard auto-consume would bypass the MAUI readiness queue.
        Rownd.config.enableSmartLinkPasteBehavior = false
        Task { @MainActor in
            // Pinned native configure can fatalError on keychain/bootstrap failures.
            // This cannot be translated to an NSError by an external facade.
            _ = await Rownd.configure(appKey: appKey, supertokens: RowndSuperTokensConfig(
                appName: Bundle.main.object(forInfoDictionaryKey: "CFBundleName") as? String ?? "Rownd MAUI",
                apiDomain: apiDomain, apiBasePath: apiBasePath))
            guard !disposed else { completion("disposed"); return }
            Rownd.getInstance().state().subscribe(self)
            completion(nil)
        }
    }

    @objc(setStateListener:)
    public func setStateListener(_ value: ((Bool, Bool, String?) -> Void)?) { listener = value }

    public func newState(state: RowndState) {
        DispatchQueue.main.async { [weak self] in
            guard let self, !self.disposed else { return }
            self.listener?(state.isInitialized, state.auth.isAuthenticated, state.auth.userId)
        }
    }

    @objc public func requestSignIn() { Rownd.requestSignIn() }
    @objc public func signOut() { Rownd.signOut() }
    @objc(getAccessToken:)
    public func getAccessToken(_ completion: @escaping (String?, String?) -> Void) {
        Task { @MainActor in
            do { completion(try await Rownd.getAccessToken(), nil) }
            catch { completion(nil, "token_retrieval_failed") }
        }
    }
    @objc(handleURL:)
    public func handleURL(_ url: URL) -> Bool {
        guard !disposed else { return false }
        return Rownd.handleSmartLink(url: url)
    }
    @objc public func dispose() {
        disposed = true
        listener = nil
        Rownd.getInstance().state().unsubscribe(self)
    }
}
