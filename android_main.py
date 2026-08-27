"""
Android Launcher for XAUUSD Signal Desk Pro.
Starts the local Python backend server and mounts a native full-screen WebView.
"""

import os
import sys
import threading
import time

try:
    from kivy.app import App
    from kivy.clock import Clock
    from kivy.core.window import Window
    from kivy.uix.widget import Widget
    HAS_KIVY = True
except ImportError:
    HAS_KIVY = False
    App = object  # type: ignore

PORT = 8000
SERVER_URL = f"http://127.0.0.1:{PORT}"


def start_backend_server():
    """Runs the web server in a daemon thread."""
    try:
        from web_server import WebServer
        from config import CONFIG, DataSource

        # Use binance or demo on mobile
        CONFIG.data_source = DataSource.BINANCE
        CONFIG.binance.symbol = "XAUUSDT"
        CONFIG.binance.market = "futures"

        server = WebServer(host="127.0.0.1", port=PORT)
        server.run()
    except Exception as exc:
        print(f"[AndroidApp] Backend error: {exc}")


def launch_android_webview(url):
    """Initializes Android hardware-accelerated WebView via PyJNIus."""
    try:
        from jnius import autoclass
        from android.runnable import run_on_ui_thread

        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        WebView = autoclass("android.webkit.WebView")
        WebViewClient = autoclass("android.webkit.WebViewClient")
        WebSettings = autoclass("android.webkit.WebSettings")
        LinearLayout = autoclass("android.widget.LinearLayout")
        LayoutParams = autoclass("android.view.ViewGroup$LayoutParams")

        @run_on_ui_thread
        def create_webview():
            activity = PythonActivity.mActivity
            webview = WebView(activity)
            settings = webview.getSettings()
            settings.setJavaScriptEnabled(True)
            settings.setDomStorageEnabled(True)
            settings.setDatabaseEnabled(True)
            settings.setBuiltInZoomControls(True)
            settings.setDisplayZoomControls(False)
            settings.setSupportZoom(True)
            settings.setUseWideViewPort(True)
            settings.setLoadWithOverviewMode(True)
            settings.setCacheMode(WebSettings.LOAD_DEFAULT)

            webview.setWebViewClient(WebViewClient())
            webview.loadUrl(url)

            layout = LinearLayout(activity)
            layout.setOrientation(LinearLayout.VERTICAL)
            layout.addView(webview, LayoutParams(LayoutParams.MATCH_PARENT, LayoutParams.MATCH_PARENT))
            activity.setContentView(layout)

        create_webview()
    except Exception as exc:
        print(f"[AndroidApp] PyJNIus WebView error: {exc}")


if HAS_KIVY:
    class XAUUSDAndroidApp(App):
        def build(self):
            Window.clearcolor = (0.094, 0.102, 0.125, 1)  # #181a20
            return Widget()

        def on_start(self):
            # 1. Start Python Web Engine
            t = threading.Thread(target=start_backend_server, daemon=True)
            t.start()

            # 2. Wait 1.2s for server initialization then mount WebView
            Clock.schedule_once(lambda dt: launch_android_webview(SERVER_URL), 1.2)


def main():
    if HAS_KIVY:
        XAUUSDAndroidApp().run()
    else:
        # Fallback to standard server
        start_backend_server()


if __name__ == "__main__":
    main()
