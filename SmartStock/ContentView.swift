import SwiftUI
import WebKit

struct WebView: UIViewRepresentable {
    let url: URL

    func makeCoordinator() -> Coordinator {
        Coordinator(self)
    }

    func makeUIView(context: Context) -> WKWebView {
        let config = WKWebViewConfiguration()
        config.defaultWebpagePreferences.allowsContentJavaScript = true
        
        let webView = WKWebView(frame: .zero, configuration: config)
        webView.uiDelegate = context.coordinator
        webView.scrollView.bounces = true
        webView.scrollView.contentInsetAdjustmentBehavior = .never
        webView.isOpaque = false
        webView.backgroundColor = UIColor(red: 246/255, green: 250/255, blue: 245/255, alpha: 1.0)
        
        if url.isFileURL {
            let baseDir = url.deletingLastPathComponent().deletingLastPathComponent()
            webView.loadFileURL(url, allowingReadAccessTo: baseDir)
        } else {
            let request = URLRequest(url: url)
            webView.load(request)
        }
        return webView
    }

    func updateUIView(_ uiView: WKWebView, context: Context) {}

    class Coordinator: NSObject, WKUIDelegate {
        var parent: WebView

        init(_ parent: WebView) {
            self.parent = parent
        }

        func webView(_ webView: WKWebView, runJavaScriptAlertPanelWithMessage message: String, initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping () -> Void) {
            guard let windowScene = UIApplication.shared.connectedScenes.first as? UIWindowScene,
                  let rootVC = windowScene.windows.first(where: { $0.isKeyWindow })?.rootViewController ?? windowScene.windows.first?.rootViewController else {
                completionHandler()
                return
            }
            let alert = UIAlertController(title: "SmartStock", message: message, preferredStyle: .alert)
            alert.addAction(UIAlertAction(title: "OK", style: .default, handler: { _ in completionHandler() }))
            rootVC.present(alert, animated: true)
        }

        func webView(_ webView: WKWebView, runJavaScriptConfirmPanelWithMessage message: String, initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping (Bool) -> Void) {
            guard let windowScene = UIApplication.shared.connectedScenes.first as? UIWindowScene,
                  let rootVC = windowScene.windows.first(where: { $0.isKeyWindow })?.rootViewController ?? windowScene.windows.first?.rootViewController else {
                completionHandler(true)
                return
            }
            let alert = UIAlertController(title: "SmartStock", message: message, preferredStyle: .alert)
            alert.addAction(UIAlertAction(title: "Cancel", style: .cancel, handler: { _ in completionHandler(false) }))
            alert.addAction(UIAlertAction(title: "OK", style: .default, handler: { _ in completionHandler(true) }))
            rootVC.present(alert, animated: true)
        }
    }
}

struct ContentView: View {
    @State private var webURL: URL? = nil

    var body: some View {
        ZStack {
            Color(red: 246/255, green: 250/255, blue: 245/255)
                .ignoresSafeArea()

            if let url = webURL {
                WebView(url: url)
                    .ignoresSafeArea()
            } else {
                VStack(spacing: 16) {
                    ProgressView()
                    Text("SmartStock")
                        .font(.headline)
                        .foregroundColor(Color(red: 11/255, green: 49/255, blue: 39/255))
                    Text("Initializing Retail Engine (₹ INR)...")
                        .font(.subheadline)
                        .foregroundColor(.secondary)
                }
            }
        }
        .onAppear {
            findStartURL()
        }
    }

    private func findStartURL() {
        if let bundlePath = Bundle.main.path(forResource: "01_signin", ofType: "html", inDirectory: "stitch/screens") {
            self.webURL = URL(fileURLWithPath: bundlePath)
            return
        }
        if let localPath = Bundle.main.resourceURL?.appendingPathComponent("stitch/screens/01_signin.html"),
           FileManager.default.fileExists(atPath: localPath.path) {
            self.webURL = localPath
            return
        }
        if let bundlePath = Bundle.main.path(forResource: "02_overview", ofType: "html", inDirectory: "stitch/screens") {
            self.webURL = URL(fileURLWithPath: bundlePath)
            return
        }
        // Fallback
        self.webURL = URL(string: "http://127.0.0.1:8000")
    }
}
