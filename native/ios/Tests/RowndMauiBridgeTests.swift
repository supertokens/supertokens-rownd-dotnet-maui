import XCTest
@testable import RowndMauiBridge

final class RowndMauiBridgeTests: XCTestCase {
    func testInvalidConfigurationFailsBeforeNativeBootstrap() {
        let bridge = RowndMauiBridge()
        var error: String?
        bridge.configure(appKey: "", apiDomain: "https://api.example.test",
                         apiBasePath: "/auth", hubURL: "https://hub.example.test",
                         scheme: "sample") { error = $0 }
        XCTAssertEqual(error, "invalid_configuration_or_lifecycle")
    }

    func testCredentialsInApiOriginAreRejectedBeforeNativeBootstrap() {
        let bridge = RowndMauiBridge()
        var error: String?
        bridge.configure(appKey: "key", apiDomain: "https://user:password@api.example.test",
                         apiBasePath: "/auth", hubURL: "https://hub.example.test",
                         scheme: "sample") { error = $0 }
        XCTAssertEqual(error, "invalid_configuration_or_lifecycle")
    }
}
