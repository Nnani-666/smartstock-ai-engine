"""
Generate a complete, modern Xcode project for SmartStock iOS App.
Compiles with Xcode 16+ for iOS Simulator (iPhone 16 / iPhone 16 Pro) and Physical Devices.
"""

import os
import shutil
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
XCODE_PROJ_DIR = BASE_DIR / "SmartStock.xcodeproj"
APP_DIR = BASE_DIR / "SmartStock"

def create_project():
    os.makedirs(XCODE_PROJ_DIR, exist_ok=True)
    os.makedirs(APP_DIR, exist_ok=True)

    # 1. Copy stitch web assets into SmartStock/stitch
    stitch_dest = APP_DIR / "stitch"
    if stitch_dest.exists():
        shutil.rmtree(stitch_dest)
    shutil.copytree(BASE_DIR / "stitch", stitch_dest)
    print("Copied stitch assets to SmartStock/stitch")

    # 2. Write Info.plist
    info_plist_content = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleDevelopmentRegion</key>
    <string>en</string>
    <key>CFBundleDisplayName</key>
    <string>SmartStock</string>
    <key>CFBundleExecutable</key>
    <string>$(EXECUTABLE_NAME)</string>
    <key>CFBundleIdentifier</key>
    <string>$(PRODUCT_BUNDLE_IDENTIFIER)</string>
    <key>CFBundleInfoDictionaryVersion</key>
    <string>6.0</string>
    <key>CFBundleName</key>
    <string>$(PRODUCT_NAME)</string>
    <key>CFBundlePackageType</key>
    <string>$(PRODUCT_BUNDLE_PACKAGE_TYPE)</string>
    <key>CFBundleShortVersionString</key>
    <string>1.0</string>
    <key>CFBundleVersion</key>
    <string>1</string>
    <key>LSRequiresIPhoneOS</key>
    <true/>
    <key>UIApplicationSceneManifest</key>
    <dict>
        <key>UIApplicationSupportsMultipleScenes</key>
        <false/>
    </dict>
    <key>UIRequiredDeviceCapabilities</key>
    <array>
        <string>arm64</string>
    </array>
    <key>UISupportedInterfaceOrientations</key>
    <array>
        <string>UIInterfaceOrientationPortrait</string>
    </array>
    <key>NSAppTransportSecurity</key>
    <dict>
        <key>NSAllowsArbitraryLoads</key>
        <true/>
    </dict>
</dict>
</plist>
"""
    with open(APP_DIR / "Info.plist", "w", encoding="utf-8") as f:
        f.write(info_plist_content)

    # 3. Write SmartStockApp.swift
    app_swift_content = """import SwiftUI

@main
struct SmartStockApp: App {
    var body: some Scene {
        WindowGroup {
            ContentView()
                .ignoresSafeArea()
        }
    }
}
"""
    with open(APP_DIR / "SmartStockApp.swift", "w", encoding="utf-8") as f:
        f.write(app_swift_content)

    # 4. Write ContentView.swift
    content_view_swift = """import SwiftUI
import WebKit

struct WebView: UIViewRepresentable {
    let url: URL

    func makeUIView(context: Context) -> WKWebView {
        let config = WKWebViewConfiguration()
        config.defaultWebpagePreferences.allowsContentJavaScript = true
        
        let webView = WKWebView(frame: .zero, configuration: config)
        webView.scrollView.bounces = true
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
                    Text("Sharma Kirana & General Store")
                        .font(.headline)
                        .foregroundColor(Color(red: 11/255, green: 49/255, blue: 39/255))
                    Text("Initializing SmartStock Retail OS (₹ INR)...")
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
        if let bundlePath = Bundle.main.path(forResource: "02_overview", ofType: "html", inDirectory: "stitch/screens") {
            self.webURL = URL(fileURLWithPath: bundlePath)
            return
        }
        if let localPath = Bundle.main.resourceURL?.appendingPathComponent("stitch/screens/01_signin.html"),
           FileManager.default.fileExists(atPath: localPath.path) {
            self.webURL = localPath
            return
        }
        // Fallback
        self.webURL = URL(string: "http://127.0.0.1:8000")
    }
}
"""
    with open(APP_DIR / "ContentView.swift", "w", encoding="utf-8") as f:
        f.write(content_view_swift)

    # 5. Assets.xcassets
    assets_dir = APP_DIR / "Assets.xcassets" / "AppIcon.appiconset"
    os.makedirs(assets_dir, exist_ok=True)
    with open(APP_DIR / "Assets.xcassets" / "Contents.json", "w", encoding="utf-8") as f:
        f.write('{"info":{"author":"xcode","version":1}}')
    with open(assets_dir / "Contents.json", "w", encoding="utf-8") as f:
        f.write('{"images":[],"info":{"author":"xcode","version":1}}')

    # 6. Generate project.pbxproj
    # Fixed UUIDs for predictable reproducible build
    P_PROJ = "AA0100010000000000000001"
    P_TGT = "AA0100020000000000000002"
    P_GRP_ROOT = "AA0100030000000000000003"
    P_GRP_APP = "AA0100040000000000000004"
    P_GRP_PROD = "AA0100050000000000000005"
    
    P_FILE_APP = "AA0100100000000000000010"
    P_FILE_CV = "AA0100110000000000000011"
    P_FILE_PLIST = "AA0100120000000000000012"
    P_FILE_ASSETS = "AA0100130000000000000013"
    P_FILE_STITCH = "AA0100140000000000000014"
    P_FILE_PROD = "AA0100150000000000000015"

    P_BUILD_APP = "AA0100200000000000000020"
    P_BUILD_CV = "AA0100210000000000000021"
    P_BUILD_ASSETS = "AA0100230000000000000023"
    P_BUILD_STITCH = "AA0100240000000000000024"

    P_PHASE_SOURCES = "AA0100300000000000000030"
    P_PHASE_FRAMEWORKS = "AA0100310000000000000031"
    P_PHASE_RESOURCES = "AA0100320000000000000032"

    P_CONF_PROJ_DBG = "AA0100400000000000000040"
    P_CONF_PROJ_REL = "AA0100410000000000000041"
    P_CONF_TGT_DBG = "AA0100420000000000000042"
    P_CONF_TGT_REL = "AA0100430000000000000043"

    P_LIST_PROJ = "AA0100500000000000000050"
    P_LIST_TGT = "AA0100510000000000000051"

    pbxproj = f"""// !$*UTF8*$!
{{
	archiveVersion = 1;
	classes = {{
	}};
	objectVersion = 56;
	objects = {{

/* Begin PBXBuildFile section */
		{P_BUILD_APP} /* SmartStockApp.swift in Sources */ = {{isa = PBXBuildFile; fileRef = {P_FILE_APP} /* SmartStockApp.swift */; }};
		{P_BUILD_CV} /* ContentView.swift in Sources */ = {{isa = PBXBuildFile; fileRef = {P_FILE_CV} /* ContentView.swift */; }};
		{P_BUILD_ASSETS} /* Assets.xcassets in Resources */ = {{isa = PBXBuildFile; fileRef = {P_FILE_ASSETS} /* Assets.xcassets */; }};
		{P_BUILD_STITCH} /* stitch in Resources */ = {{isa = PBXBuildFile; fileRef = {P_FILE_STITCH} /* stitch */; }};
/* End PBXBuildFile section */

/* Begin PBXFileReference section */
		{P_FILE_PROD} /* SmartStock.app */ = {{isa = PBXFileReference; explicitFileType = wrapper.application; includeInIndex = 0; path = SmartStock.app; sourceTree = BUILT_PRODUCTS_DIR; }};
		{P_FILE_APP} /* SmartStockApp.swift */ = {{isa = PBXFileReference; lastKnownFileType = sourcecode.swift; path = SmartStockApp.swift; sourceTree = "<group>"; }};
		{P_FILE_CV} /* ContentView.swift */ = {{isa = PBXFileReference; lastKnownFileType = sourcecode.swift; path = ContentView.swift; sourceTree = "<group>"; }};
		{P_FILE_PLIST} /* Info.plist */ = {{isa = PBXFileReference; lastKnownFileType = text.plist.xml; path = Info.plist; sourceTree = "<group>"; }};
		{P_FILE_ASSETS} /* Assets.xcassets */ = {{isa = PBXFileReference; lastKnownFileType = folder.assetcatalog; path = Assets.xcassets; sourceTree = "<group>"; }};
		{P_FILE_STITCH} /* stitch */ = {{isa = PBXFileReference; lastKnownFileType = folder; path = stitch; sourceTree = "<group>"; }};
/* End PBXFileReference section */

/* Begin PBXFrameworksBuildPhase section */
		{P_PHASE_FRAMEWORKS} /* Frameworks */ = {{
			isa = PBXFrameworksBuildPhase;
			buildActionMask = 2147483647;
			files = (
			);
			runOnlyForDeploymentPostprocessing = 0;
		}};
/* End PBXFrameworksBuildPhase section */

/* Begin PBXGroup section */
		{P_GRP_ROOT} = {{
			isa = PBXGroup;
			children = (
				{P_GRP_APP} /* SmartStock */,
				{P_GRP_PROD} /* Products */,
			);
			sourceTree = "<group>";
		}};
		{P_GRP_APP} /* SmartStock */ = {{
			isa = PBXGroup;
			children = (
				{P_FILE_APP} /* SmartStockApp.swift */,
				{P_FILE_CV} /* ContentView.swift */,
				{P_FILE_STITCH} /* stitch */,
				{P_FILE_ASSETS} /* Assets.xcassets */,
				{P_FILE_PLIST} /* Info.plist */,
			);
			path = SmartStock;
			sourceTree = "<group>";
		}};
		{P_GRP_PROD} /* Products */ = {{
			isa = PBXGroup;
			children = (
				{P_FILE_PROD} /* SmartStock.app */,
			);
			name = Products;
			sourceTree = "<group>";
		}};
/* End PBXGroup section */

/* Begin PBXNativeTarget section */
		{P_TGT} /* SmartStock */ = {{
			isa = PBXNativeTarget;
			buildConfigurationList = {P_LIST_TGT} /* Build configuration list for PBXNativeTarget "SmartStock" */;
			buildPhases = (
				{P_PHASE_SOURCES} /* Sources */,
				{P_PHASE_FRAMEWORKS} /* Frameworks */,
				{P_PHASE_RESOURCES} /* Resources */,
			);
			buildRules = (
			);
			dependencies = (
			);
			name = SmartStock;
			productName = SmartStock;
			productReference = {P_FILE_PROD} /* SmartStock.app */;
			productType = "com.apple.product-type.application";
		}};
/* End PBXNativeTarget section */

/* Begin PBXProject section */
		{P_PROJ} /* Project object */ = {{
			isa = PBXProject;
			attributes = {{
				BuildIndependentTargetsInParallel = 1;
				LastSwiftUpdateCheck = 1600;
				LastUpgradeCheck = 1600;
				TargetAttributes = {{
					{P_TGT} = {{
						CreatedOnToolsVersion = 16.0;
					}};
				}};
			}};
			buildConfigurationList = {P_LIST_PROJ} /* Build configuration list for PBXProject "SmartStock" */;
			compatibilityVersion = "Xcode 14.0";
			developmentRegion = en;
			hasScannedForEncodings = 0;
			knownRegions = (
				en,
				Base,
			);
			mainGroup = {P_GRP_ROOT};
			productRefGroup = {P_GRP_PROD} /* Products */;
			projectDirPath = "";
			projectRoot = "";
			targets = (
				{P_TGT} /* SmartStock */,
			);
		}};
/* End PBXProject section */

/* Begin PBXResourcesBuildPhase section */
		{P_PHASE_RESOURCES} /* Resources */ = {{
			isa = PBXResourcesBuildPhase;
			buildActionMask = 2147483647;
			files = (
				{P_BUILD_ASSETS} /* Assets.xcassets in Resources */,
				{P_BUILD_STITCH} /* stitch in Resources */,
			);
			runOnlyForDeploymentPostprocessing = 0;
		}};
/* End PBXResourcesBuildPhase section */

/* Begin PBXSourcesBuildPhase section */
		{P_PHASE_SOURCES} /* Sources */ = {{
			isa = PBXSourcesBuildPhase;
			buildActionMask = 2147483647;
			files = (
				{P_BUILD_APP} /* SmartStockApp.swift in Sources */,
				{P_BUILD_CV} /* ContentView.swift in Sources */,
			);
			runOnlyForDeploymentPostprocessing = 0;
		}};
/* End PBXSourcesBuildPhase section */

/* Begin XCBuildConfiguration section */
		{P_CONF_PROJ_DBG} /* Debug */ = {{
			isa = XCBuildConfiguration;
			buildSettings = {{
				ALWAYS_SEARCH_USER_PATHS = NO;
				ASSETCATALOG_COMPILER_GENERATE_SWIFT_ASSET_SYMBOL_EXTENSIONS = YES;
				CLANG_ANALYZER_NONNULL = YES;
				CLANG_ANALYZER_NUMBER_OBJECT_CONVERSION = YES_AGGRESSIVE;
				CLANG_CXX_LANGUAGE_STANDARD = "gnu++20";
				CLANG_ENABLE_MODULES = YES;
				CLANG_ENABLE_OBJC_ARC = YES;
				CLANG_ENABLE_OBJC_WEAK = YES;
				CLANG_WARN_BLOCK_CAPTURE_AUTORELEASING = YES;
				CLANG_WARN_BOOL_CONVERSION = YES;
				CLANG_WARN_COMMA = YES;
				CLANG_WARN_CONSTANT_CONVERSION = YES;
				CLANG_WARN_DEPRECATED_OBJC_IMPLEMENTATIONS = YES;
				CLANG_WARN_DIRECT_OBJC_ISA_USAGE = YES_ERROR;
				CLANG_WARN_DOCUMENTATION_COMMENTS = YES;
				CLANG_WARN_EMPTY_BODY = YES;
				CLANG_WARN_ENUM_CONVERSION = YES;
				CLANG_WARN_INFINITE_RECURSION = YES;
				CLANG_WARN_INT_CONVERSION = YES;
				CLANG_WARN_NON_LITERAL_NULL_CONVERSION = YES;
				CLANG_WARN_OBJC_IMPLICIT_RETAIN_SELF = YES;
				CLANG_WARN_OBJC_LITERAL_CONVERSION = YES;
				CLANG_WARN_OBJC_ROOT_CLASS = YES_ERROR;
				CLANG_WARN_QUOTED_INCLUDE_IN_FRAMEWORK_HEADER = YES;
				CLANG_WARN_RANGE_LOOP_ANALYSIS = YES;
				CLANG_WARN_STRICT_PROTOTYPES = YES;
				CLANG_WARN_SUSPICIOUS_MOVE = YES;
				CLANG_WARN_UNGUARDED_AVAILABILITY = YES_AGGRESSIVE;
				CLANG_WARN_UNREACHABLE_CODE = YES;
				CLANG_WARN__DUPLICATE_METHOD_MATCH = YES;
				COPY_PHASE_STRIP = NO;
				DEBUG_INFORMATION_FORMAT = dwarf;
				ENABLE_STRICT_OBJC_MSGSEND = YES;
				ENABLE_TESTABILITY = YES;
				ENABLE_USER_SCRIPT_SANDBOXING = YES;
				GCC_C_LANGUAGE_STANDARD = gnu17;
				GCC_DYNAMIC_NO_PIC = NO;
				GCC_NO_COMMON_BLOCKS = YES;
				GCC_OPTIMIZATION_LEVEL = 0;
				GCC_PREPROCESSOR_DEFINITIONS = (
					"DEBUG=1",
					"$(inherited)",
				);
				GCC_WARN_64_TO_32_BIT_CONVERSION = YES;
				GCC_WARN_ABOUT_RETURN_TYPE = YES_ERROR;
				GCC_WARN_UNDEFINED_VARIABLES = YES;
				GCC_WARN_UNUSED_FUNCTION = YES;
				GCC_WARN_UNUSED_VARIABLE = YES;
				IPHONEOS_DEPLOYMENT_TARGET = 16.0;
				MTL_ENABLE_DEBUG_INFO = INCLUDE_SOURCE;
				MTL_FAST_MATH = YES;
				ONLY_ACTIVE_ARCH = YES;
				SDKROOT = iphoneos;
				SWIFT_ACTIVE_COMPILATION_CONDITIONS = "DEBUG $(inherited)";
				SWIFT_OPTIMIZATION_LEVEL = "-Onone";
			}};
			name = Debug;
		}};
		{P_CONF_PROJ_REL} /* Release */ = {{
			isa = XCBuildConfiguration;
			buildSettings = {{
				ALWAYS_SEARCH_USER_PATHS = NO;
				ASSETCATALOG_COMPILER_GENERATE_SWIFT_ASSET_SYMBOL_EXTENSIONS = YES;
				CLANG_ANALYZER_NONNULL = YES;
				CLANG_ANALYZER_NUMBER_OBJECT_CONVERSION = YES_AGGRESSIVE;
				CLANG_CXX_LANGUAGE_STANDARD = "gnu++20";
				CLANG_ENABLE_MODULES = YES;
				CLANG_ENABLE_OBJC_ARC = YES;
				CLANG_ENABLE_OBJC_WEAK = YES;
				CLANG_WARN_BLOCK_CAPTURE_AUTORELEASING = YES;
				CLANG_WARN_BOOL_CONVERSION = YES;
				CLANG_WARN_COMMA = YES;
				CLANG_WARN_CONSTANT_CONVERSION = YES;
				CLANG_WARN_DEPRECATED_OBJC_IMPLEMENTATIONS = YES;
				CLANG_WARN_DIRECT_OBJC_ISA_USAGE = YES_ERROR;
				CLANG_WARN_DOCUMENTATION_COMMENTS = YES;
				CLANG_WARN_EMPTY_BODY = YES;
				CLANG_WARN_ENUM_CONVERSION = YES;
				CLANG_WARN_INFINITE_RECURSION = YES;
				CLANG_WARN_INT_CONVERSION = YES;
				CLANG_WARN_NON_LITERAL_NULL_CONVERSION = YES;
				CLANG_WARN_OBJC_IMPLICIT_RETAIN_SELF = YES;
				CLANG_WARN_OBJC_LITERAL_CONVERSION = YES;
				CLANG_WARN_OBJC_ROOT_CLASS = YES_ERROR;
				CLANG_WARN_QUOTED_INCLUDE_IN_FRAMEWORK_HEADER = YES;
				CLANG_WARN_RANGE_LOOP_ANALYSIS = YES;
				CLANG_WARN_STRICT_PROTOTYPES = YES;
				CLANG_WARN_SUSPICIOUS_MOVE = YES;
				CLANG_WARN_UNGUARDED_AVAILABILITY = YES_AGGRESSIVE;
				CLANG_WARN_UNREACHABLE_CODE = YES;
				CLANG_WARN__DUPLICATE_METHOD_MATCH = YES;
				COPY_PHASE_STRIP = NO;
				DEBUG_INFORMATION_FORMAT = "dwarf-with-dsym";
				ENABLE_NS_ASSERTIONS = NO;
				ENABLE_STRICT_OBJC_MSGSEND = YES;
				ENABLE_USER_SCRIPT_SANDBOXING = YES;
				GCC_C_LANGUAGE_STANDARD = gnu17;
				GCC_NO_COMMON_BLOCKS = YES;
				GCC_WARN_64_TO_32_BIT_CONVERSION = YES;
				GCC_WARN_ABOUT_RETURN_TYPE = YES_ERROR;
				GCC_WARN_UNDEFINED_VARIABLES = YES;
				GCC_WARN_UNUSED_FUNCTION = YES;
				GCC_WARN_UNUSED_VARIABLE = YES;
				IPHONEOS_DEPLOYMENT_TARGET = 16.0;
				MTL_ENABLE_DEBUG_INFO = NO;
				MTL_FAST_MATH = YES;
				SDKROOT = iphoneos;
				SWIFT_COMPILATION_MODE = wholemodule;
			}};
			name = Release;
		}};
		{P_CONF_TGT_DBG} /* Debug */ = {{
			isa = XCBuildConfiguration;
			buildSettings = {{
				ASSETCATALOG_COMPILER_APPICON_NAME = AppIcon;
				CODE_SIGN_STYLE = Automatic;
				CURRENT_PROJECT_VERSION = 1;
				DEVELOPMENT_ASSET_PATHS = "";
				ENABLE_PREVIEWS = YES;
				GENERATE_INFOPLIST_FILE = NO;
				INFOPLIST_FILE = SmartStock/Info.plist;
				INFOPLIST_KEY_UIApplicationSceneManifest_Generation = YES;
				INFOPLIST_KEY_UIApplicationSupportsIndirectInputEvents = YES;
				INFOPLIST_KEY_UILaunchScreen_Generation = YES;
				INFOPLIST_KEY_UISupportedInterfaceOrientations_iPhone = UIInterfaceOrientationPortrait;
				LD_RUNPATH_SEARCH_PATHS = (
					"$(inherited)",
					"@executable_path/Frameworks",
				);
				MARKETING_VERSION = 1.0;
				PRODUCT_BUNDLE_IDENTIFIER = in.sharmakirana.smartstock;
				PRODUCT_NAME = "$(TARGET_NAME)";
				SWIFT_EMIT_LOC_STRINGS = YES;
				SWIFT_VERSION = 5.0;
				TARGETED_DEVICE_FAMILY = "1,2";
			}};
			name = Debug;
		}};
		{P_CONF_TGT_REL} /* Release */ = {{
			isa = XCBuildConfiguration;
			buildSettings = {{
				ASSETCATALOG_COMPILER_APPICON_NAME = AppIcon;
				CODE_SIGN_STYLE = Automatic;
				CURRENT_PROJECT_VERSION = 1;
				DEVELOPMENT_ASSET_PATHS = "";
				ENABLE_PREVIEWS = YES;
				GENERATE_INFOPLIST_FILE = NO;
				INFOPLIST_FILE = SmartStock/Info.plist;
				INFOPLIST_KEY_UIApplicationSceneManifest_Generation = YES;
				INFOPLIST_KEY_UIApplicationSupportsIndirectInputEvents = YES;
				INFOPLIST_KEY_UILaunchScreen_Generation = YES;
				INFOPLIST_KEY_UISupportedInterfaceOrientations_iPhone = UIInterfaceOrientationPortrait;
				LD_RUNPATH_SEARCH_PATHS = (
					"$(inherited)",
					"@executable_path/Frameworks",
				);
				MARKETING_VERSION = 1.0;
				PRODUCT_BUNDLE_IDENTIFIER = in.sharmakirana.smartstock;
				PRODUCT_NAME = "$(TARGET_NAME)";
				SWIFT_EMIT_LOC_STRINGS = YES;
				SWIFT_VERSION = 5.0;
				TARGETED_DEVICE_FAMILY = "1,2";
			}};
			name = Release;
		}};
/* End XCBuildConfiguration section */

/* Begin XCConfigurationList section */
		{P_LIST_PROJ} /* Build configuration list for PBXProject "SmartStock" */ = {{
			isa = XCConfigurationList;
			buildConfigurations = (
				{P_CONF_PROJ_DBG} /* Debug */,
				{P_CONF_PROJ_REL} /* Release */,
			);
			defaultConfigurationIsVisible = 0;
			defaultConfigurationName = Release;
		}};
		{P_LIST_TGT} /* Build configuration list for PBXNativeTarget "SmartStock" */ = {{
			isa = XCConfigurationList;
			buildConfigurations = (
				{P_CONF_TGT_DBG} /* Debug */,
				{P_CONF_TGT_REL} /* Release */,
			);
			defaultConfigurationIsVisible = 0;
			defaultConfigurationName = Release;
		}};
/* End XCConfigurationList section */

	}};
	rootObject = {P_PROJ} /* Project object */;
}}
"""
    with open(XCODE_PROJ_DIR / "project.pbxproj", "w", encoding="utf-8") as f:
        f.write(pbxproj)

    print(f"Generated SmartStock.xcodeproj successfully at {XCODE_PROJ_DIR}")

if __name__ == "__main__":
    create_project()
