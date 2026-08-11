import Capacitor
import UIKit

@objc(UploadKeepAlivePlugin)
public class UploadKeepAlivePlugin: CAPPlugin, CAPBridgedPlugin {
    public let identifier = "UploadKeepAlivePlugin"
    public let jsName = "UploadKeepAlive"
    public let pluginMethods: [CAPPluginMethod] = [
        CAPPluginMethod(name: "start", returnType: CAPPluginReturnPromise),
        CAPPluginMethod(name: "stop", returnType: CAPPluginReturnPromise),
    ]

    private var backgroundTask = UIBackgroundTaskIdentifier.invalid

    @objc func start(_ call: CAPPluginCall) {
        DispatchQueue.main.async {
            UIApplication.shared.isIdleTimerDisabled = true
            if self.backgroundTask == .invalid {
                self.backgroundTask = UIApplication.shared.beginBackgroundTask(
                    withName: "PewcorderUpload"
                ) {
                    self.endBackgroundTask()
                }
            }
            call.resolve()
        }
    }

    @objc func stop(_ call: CAPPluginCall) {
        DispatchQueue.main.async {
            UIApplication.shared.isIdleTimerDisabled = false
            self.endBackgroundTask()
            call.resolve()
        }
    }

    private func endBackgroundTask() {
        guard backgroundTask != .invalid else { return }
        UIApplication.shared.endBackgroundTask(backgroundTask)
        backgroundTask = .invalid
    }

    deinit {
        DispatchQueue.main.async {
            UIApplication.shared.isIdleTimerDisabled = false
        }
        endBackgroundTask()
    }
}
