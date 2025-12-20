import sys
import os
import platform
import subprocess
import re
import json
from pathlib import Path
from datetime import datetime, timedelta

from PyQt6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QLineEdit, QPushButton, QHBoxLayout, QTabWidget, QListWidget, QSplitter, QDialog, QLabel, QFormLayout, QComboBox, QCheckBox, QToolBar, QMenu, QFileDialog, QMessageBox
from PyQt6.QtGui import QAction, QPalette, QColor, QShortcut, QKeySequence
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEnginePage, QWebEngineSettings, QWebEngineProfile, QWebEngineDownloadRequest
from PyQt6.QtWebChannel import QWebChannel
from PyQt6.QtCore import QUrl, Qt, QObject, pyqtSlot

# Global persistent profile
_PERSISTENT_PROFILE = None

def _get_persistent_profile():
    """Get or create a persistent WebEngine profile for cookies and cache."""
    global _PERSISTENT_PROFILE
    if _PERSISTENT_PROFILE is None:
        profile_path = str(Path.home() / ".flow-browser")
        _PERSISTENT_PROFILE = QWebEngineProfile("flow")
        _PERSISTENT_PROFILE.setCachePath(profile_path + "/cache")
        _PERSISTENT_PROFILE.setPersistentStoragePath(profile_path + "/storage")
    return _PERSISTENT_PROFILE

class BrowserPage(QWebEnginePage):
    def __init__(self, main_window, parent=None, opener_page: QWebEnginePage | None = None):
        super().__init__(_get_persistent_profile(), parent)
        self._main_window = main_window
        self._opener_page = opener_page

    def acceptNavigationRequest(self, url, nav_type, isMainFrame):
        try:
            # blob: URLs are not fetchable by Chromium's download stack directly. If a site
            # tries to navigate to a blob: URL to download it, Qt often shows an error page.
            # Instead, capture the blob bytes from the current page via WebChannel and save.
            if isMainFrame and url.scheme() == "blob":
                # Fetch the blob from the opener page if available (blob URLs are scoped
                # to the origin that created them; popups/about:blank may not have access).
                fetch_page = self._opener_page or self
                self._main_window._download_blob_from_page(fetch_page, url.toString())
                return False

            # Many "download buttons" use JS like window.location=... or redirects,
            # which show up as NavigationTypeOther/Redirect rather than LinkClicked.
            # If the main-frame navigation looks like a file download, force it.
            if isMainFrame and self._main_window._looks_like_download_url(url):
                # Force a download (uses Chromium network stack + cookies).
                # Pass empty filename so the server's Content-Disposition / suggested name wins.
                self.download(url, "")
                return False
        except Exception as e:
            print(f"acceptNavigationRequest error: {e}")

        return super().acceptNavigationRequest(url, nav_type, isMainFrame)


class JsBridge(QObject):
    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self._mw = main_window

    @pyqtSlot(str, str)
    def saveBlob(self, data_url: str, filename: str):
        # data_url format: data:<mime>;base64,<payload>
        self._mw._save_blob_data_url(data_url, filename)

    @pyqtSlot(str)
    def saveBlobError(self, message: str):
        print(f"Blob download error: {message}")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.current_theme = "dark"
        self.web_dark_mode = False

        # Bookmarks are persisted as text files in ./flow-bookmarks (bk1.txt, bk2.txt, ...)
        # Each file contains a single URL.
        self.bookmarks = []
        self._load_bookmarks_from_disk()

        self.history = []
        self.downloads = []  # list[dict] (see _on_download_requested)

        self.downloads_list = None
        self._downloads_dialog = None

        # Hook downloads from the persistent profile (used by all web pages).
        _get_persistent_profile().downloadRequested.connect(self._on_download_requested)
        
        self.setWindowTitle("Flow Browser")
        self.setGeometry(100, 100, 1200, 800)
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # Top row: buttons and URL bar
        top_layout = QHBoxLayout()
        top_layout.setContentsMargins(8, 6, 8, 6)
        top_layout.setSpacing(6)
        
        # Buttons container
        button_widget = QWidget()
        button_layout = QHBoxLayout(button_widget)
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.setSpacing(2)  # Reduced spacing between buttons

        # App menu (shown from the "..." button on the right)
        self.app_menu = QMenu(self)

        # Former "File" actions
        self.app_menu.addAction("New Tab", self.add_new_tab)
        self.app_menu.addAction("Close Tab", self.close_current_tab)
        self.app_menu.addAction("Save Page as HTML", self.save_page_as_html)
        self.app_menu.addAction("Download current URL", self.download_current_url)
        self.app_menu.addSeparator()

        # Former "View" actions
        self.app_menu.addAction("Bookmarks", self.show_bookmarks)
        self.app_menu.addAction("History", self.show_history)
        self.app_menu.addAction("Downloads", self.show_downloads)
        self.app_menu.addAction("Cookies", self.show_cookies)
        self.app_menu.addAction("Inspect", self.open_devtools)
        self.app_menu.addAction("Settings", self.show_settings)

        self.back_btn = QPushButton("←")
        self.back_btn.setProperty("chromeNav", True)
        self.back_btn.setFixedSize(34, 34)
        self.back_btn.clicked.connect(self.go_back)
        button_layout.addWidget(self.back_btn)
        
        self.forward_btn = QPushButton("→")
        self.forward_btn.setProperty("chromeNav", True)
        self.forward_btn.setFixedSize(34, 34)
        self.forward_btn.clicked.connect(self.go_forward)
        button_layout.addWidget(self.forward_btn)
        
        self.refresh_btn = QPushButton("↻")
        self.refresh_btn.setProperty("chromeNav", True)
        self.refresh_btn.setFixedSize(34, 34)
        self.refresh_btn.clicked.connect(self.refresh_page)
        button_layout.addWidget(self.refresh_btn)
        
        # Home button
        self.home_btn = QPushButton("⌂")
        self.home_btn.setToolTip("Home")
        self.home_btn.setProperty("chromeNav", True)
        self.home_btn.setProperty("homeButton", True)  # Specific property for home button styling
        self.home_btn.setFixedSize(34, 34)
        self.home_btn.clicked.connect(self.go_home)
        button_layout.addWidget(self.home_btn)

        top_layout.addWidget(button_widget, 1)
        
        # URL bar
        self.url_bar = QLineEdit()
        self.url_bar.setProperty("chromeOmnibox", True)
        self.url_bar.returnPressed.connect(self.load_url)
        top_layout.addWidget(self.url_bar, 3)  # URL bar takes 75%

        # Menu button on the right
        self.menu_btn = QPushButton("...")
        self.menu_btn.setProperty("chromeNav", True)
        self.menu_btn.setMenu(self.app_menu)
        self.menu_btn.setFixedSize(34, 34)
        top_layout.addWidget(self.menu_btn, 0)
        
        layout.addLayout(top_layout)
        
        # Tab widget
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.setMovable(True)
        self.tabs.setUsesScrollButtons(True)
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.tabs.currentChanged.connect(self.on_tab_changed)
        layout.addWidget(self.tabs)
        
        # Add initial tab
        self.add_new_tab()
        self.apply_theme()
        self.apply_chrome_style()

        # DevTools / Inspect shortcuts
        self._inspect_shortcut_f12 = QShortcut(QKeySequence("F12"), self)
        self._inspect_shortcut_f12.setContext(Qt.ShortcutContext.ApplicationShortcut)
        self._inspect_shortcut_f12.activated.connect(self.open_devtools)

        self._inspect_shortcut_ctrl_shift_i = QShortcut(QKeySequence("Ctrl+Shift+I"), self)
        self._inspect_shortcut_ctrl_shift_i.setContext(Qt.ShortcutContext.ApplicationShortcut)
        self._inspect_shortcut_ctrl_shift_i.activated.connect(self.open_devtools)

        

        
    
    def enable_pointer_lock(self):
        self.page = self.tabs.currentWidget().web_view.page()
        self.page.setFullScreenRequested(self.handle_full_screen_requested)

    def handle_full_screen_requested(self, request):
        if request.isFullScreen():
            self.page.setFullScreenRequestedByUser(True)
            self.page.setFullScreen(request)
            self.page.setPointerRestrictionPolicy(QWebEnginePage.PointerRestrictionPolicy.Dragging)

    def disable_pointer_lock(self):
        self.page = self.tabs.currentWidget().web_view.page()
        self.page.setFullScreenRequested(None)
        self.page.setPointerRestrictionPolicy(QWebEnginePage.PointerRestrictionPolicy.Default)
    
    def apply_theme(self):
        if self.current_theme == "dark":
            # Darker than the previous "Chrome dark" approximation
            palette = QPalette()
            palette.setColor(QPalette.ColorRole.Window, QColor("#0f0f10"))
            palette.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.white)
            palette.setColor(QPalette.ColorRole.Base, QColor("#0f0f10"))
            palette.setColor(QPalette.ColorRole.AlternateBase, QColor("#1a1b1e"))
            palette.setColor(QPalette.ColorRole.ToolTipBase, QColor("#1a1b1e"))
            palette.setColor(QPalette.ColorRole.ToolTipText, Qt.GlobalColor.white)
            palette.setColor(QPalette.ColorRole.Text, Qt.GlobalColor.white)
            palette.setColor(QPalette.ColorRole.Button, QColor("#1a1b1e"))
            palette.setColor(QPalette.ColorRole.ButtonText, Qt.GlobalColor.white)
            palette.setColor(QPalette.ColorRole.BrightText, Qt.GlobalColor.red)
            palette.setColor(QPalette.ColorRole.Link, QColor("#8ab4f8"))
            palette.setColor(QPalette.ColorRole.Highlight, QColor("#8ab4f8"))
            palette.setColor(QPalette.ColorRole.HighlightedText, Qt.GlobalColor.black)
            self.setPalette(palette)
        else:
            # Light theme (Chrome-like grays)
            palette = QPalette()
            palette.setColor(QPalette.ColorRole.Window, QColor("#f1f3f4"))
            palette.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.black)
            palette.setColor(QPalette.ColorRole.Base, Qt.GlobalColor.white)
            palette.setColor(QPalette.ColorRole.AlternateBase, QColor("#f1f3f4"))
            palette.setColor(QPalette.ColorRole.ToolTipBase, Qt.GlobalColor.white)
            palette.setColor(QPalette.ColorRole.ToolTipText, Qt.GlobalColor.black)
            palette.setColor(QPalette.ColorRole.Text, Qt.GlobalColor.black)
            palette.setColor(QPalette.ColorRole.Button, QColor("#f1f3f4"))
            palette.setColor(QPalette.ColorRole.ButtonText, Qt.GlobalColor.black)
            palette.setColor(QPalette.ColorRole.BrightText, Qt.GlobalColor.red)
            palette.setColor(QPalette.ColorRole.Link, QColor("#1a73e8"))
            palette.setColor(QPalette.ColorRole.Highlight, QColor("#1a73e8"))
            palette.setColor(QPalette.ColorRole.HighlightedText, Qt.GlobalColor.white)
            self.setPalette(palette)

        # Apply theme application-wide so dialogs/menus follow it too
        app = QApplication.instance()
        if app:
            app.setPalette(palette)

        # Keep the "Chrome" styling in sync with the theme
        self.apply_chrome_style()

    def apply_chrome_style(self):
        if self.current_theme == "dark":
            # Darker theme values (deeper blacks)
            top_bg = "#0f0f10"
            tab_bg = "#1a1b1e"
            tab_active_bg = "#0f0f10"
            border = "#2a2b2f"
            text = "#e8eaed"
            hover = "rgba(232,234,237,0.10)"
            press = "rgba(232,234,237,0.16)"
            omnibox_bg = "#1a1b1e"
        else:
            top_bg = "#f1f3f4"
            tab_bg = "#e8eaed"
            tab_active_bg = "#ffffff"
            border = "#dadce0"
            text = "#202124"
            hover = "rgba(60,64,67,0.08)"
            press = "rgba(60,64,67,0.12)"
            omnibox_bg = "#ffffff"

        # Apply stylesheet application-wide so dialogs/menus follow it too
        app = QApplication.instance()
        target = app if app else self

        target.setStyleSheet(f"""
            QWidget {{
                color: {text};
            }}

            /* Window background */
            QMainWindow, QDialog {{
                background: {top_bg};
            }}

            /* Chrome-like icon buttons */
            QPushButton[chromeNav=\"true\"] {{
                border: none;
                background: transparent;
                border-radius: 10px;
                padding: 3px;
            }}
            QPushButton[chromeNav=\"true\"]:hover {{
                background: {hover};
            }}
            QPushButton[chromeNav=\"true\"]:pressed {{
                background: {press};
            }}

            /* Hide the small dropdown arrow that Qt adds to menu buttons */
            QPushButton[chromeNav=\"true\"]::menu-indicator {{
                image: none;
                width: 0px;
            }}

            /* Home button with reduced padding */
            QPushButton[homeButton=\"true\"] {{
                padding: 1px 2px;
            }}

            /* Omnibox */
            QLineEdit[chromeOmnibox=\"true\"] {{
                background: {omnibox_bg};
                border: 1px solid {border};
                border-radius: 17px;
                padding: 7px 12px;
                selection-background-color: #1a73e8;
                selection-color: white;
            }}
            QLineEdit[chromeOmnibox=\"true\"]:focus {{
                border: 1px solid #1a73e8;
            }}

            /* Menus (e.g. the "..." button) */
            QMenu {{
                background-color: {omnibox_bg};
                color: {text};
                border: 1px solid {border};
                border-radius: 10px;
                padding: 8px;
            }}
            QMenu::item {{
                padding: 8px 24px;
                border-radius: 6px;
            }}
            QMenu::item:selected {{
                background-color: {hover};
            }}
            QMenu::separator {{
                height: 1px;
                background-color: {border};
                margin: 6px 4px;
            }}

            /* ComboBox dropdowns (e.g. Settings -> Theme) */
            QComboBox {{
                background-color: {omnibox_bg};
                color: {text};
                border: 1px solid {border};
                border-radius: 8px;
                padding: 4px 10px;
            }}
            QComboBox::drop-down {{
                border: none;
                width: 24px;
            }}
            QComboBox QAbstractItemView {{
                background-color: {omnibox_bg};
                color: {text};
                border: 1px solid {border};
                border-radius: 10px;
                selection-background-color: {hover};
                selection-color: {text};
                outline: 0;
            }}

            /* Tabs */
            QTabWidget::pane {{
                border: 0;
            }}
            QTabBar::tab {{
                background: {tab_bg};
                border: 1px solid {border};
                border-bottom: 0;
                border-top-left-radius: 10px;
                border-top-right-radius: 10px;
                padding: 6px 12px;
                margin-right: 3px;
                min-width: 120px;
            }}
            QTabBar::tab:selected {{
                background: {tab_active_bg};
            }}
            QTabBar::tab:hover {{
                background: {hover};
            }}
        """)
  
    def add_new_tab(self, url="https://www.startpage.com", opener_page: QWebEnginePage | None = None):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        web_view = QWebEngineView()
        web_view.setPage(BrowserPage(self, web_view, opener_page=opener_page))

        # WebChannel bridge (used for blob: downloads triggered by JS download buttons)
        tab._web_channel = QWebChannel(web_view.page())
        tab._js_bridge = JsBridge(self, tab)
        tab._web_channel.registerObject("flowBridge", tab._js_bridge)
        web_view.page().setWebChannel(tab._web_channel)
        web_view.settings().setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
        web_view.settings().setAttribute(QWebEngineSettings.WebAttribute.AutoLoadImages, True)
        web_view.settings().setAttribute(QWebEngineSettings.WebAttribute.PluginsEnabled, True)
        web_view.settings().setAttribute(QWebEngineSettings.WebAttribute.FullScreenSupportEnabled, True)
        layout.addWidget(web_view)
        tab.web_view = web_view  # Store reference
        index = self.tabs.addTab(tab, "New Tab")
        self.tabs.setCurrentIndex(index)
        web_view.load(QUrl(url))
        web_view.setFocus()

        # Ctrl+S: save as plain .html (Qt/Chromium default is .mhtml)
        tab._save_html_shortcut = QShortcut(QKeySequence.StandardKey.Save, web_view)
        tab._save_html_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        tab._save_html_shortcut.activated.connect(self.save_page_as_html)
        
        # Handle new windows (like popups or new tabs from links)
        web_view.page().newWindowRequested.connect(self.handle_new_window)
        web_view.page().fullScreenRequested.connect(self.handle_full_screen)
        web_view.page().featurePermissionRequested.connect(self.handle_feature_permission)
        
        # Connect signals
        web_view.titleChanged.connect(lambda title, view=web_view: self.update_tab_title(title, view))
        web_view.urlChanged.connect(lambda url, view=web_view: self.update_url_bar(url, view))
        web_view.urlChanged.connect(lambda _url, view=web_view: self.update_nav_buttons(view=view))
        web_view.loadFinished.connect(self.add_to_history)
        web_view.loadFinished.connect(lambda _ok, view=web_view: self._install_blob_download_hook(view))
        
        return web_view
    
    def close_current_tab(self):
        index = self.tabs.currentIndex()
        self.close_tab(index)
    
    def go_back(self):
        current_tab = self.tabs.currentWidget()
        if current_tab:
            current_tab.web_view.back()
    
    def go_forward(self):
        current_tab = self.tabs.currentWidget()
        if current_tab:
            current_tab.web_view.forward()
    
    def refresh_page(self):
        current_tab = self.tabs.currentWidget()
        if current_tab:
            current_tab.web_view.reload()
    
    def go_home(self):
        self.url_bar.setText("https://www.startpage.com")
        self.load_url()

    def save_page_as_html(self):
        """Save the currently displayed page to a .html file (DOM only).

        Note: This exports the current DOM via QWebEnginePage.toHtml(). It does not bundle
        external assets (images/css/js) like an archive format would.
        """
        current_tab = self.tabs.currentWidget()
        if not current_tab or not hasattr(current_tab, "web_view"):
            return

        title = current_tab.web_view.title() or "page"
        default_name = f"{self._sanitize_filename(title)}.html"
        default_path = str(self._downloads_dir() / default_name)

        path, _filter = QFileDialog.getSaveFileName(
            self,
            "Save Page as HTML",
            default_path,
            "HTML Files (*.html);;All Files (*.*)",
        )
        if not path:
            return

        def _write_html(html: str):
            try:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(html)
            except Exception as e:
                QMessageBox.critical(self, "Save Failed", f"Could not save file:\n{e}")

        current_tab.web_view.page().toHtml(_write_html)

    def _save_blob_data_url(self, data_url: str, filename: str):
        try:
            if not data_url.startswith("data:"):
                raise ValueError("Expected a data: URL")

            # Split at the first comma.
            header, b64 = data_url.split(",", 1)
            if ";base64" not in header:
                raise ValueError("Expected base64 data")

            directory = self._downloads_dir()
            directory.mkdir(parents=True, exist_ok=True)

            safe_name = filename or "download"
            safe_name = self._unique_download_filename(directory, safe_name)
            out_path = directory / safe_name

            import base64

            data = base64.b64decode(b64)
            with open(out_path, "wb") as f:
                f.write(data)

            self.downloads.append(
                {
                    "request": None,
                    "filename": safe_name,
                    "url": "blob:",
                    "path": str(out_path),
                    "received": len(data),
                    "total": len(data),
                    "state": None,
                    "completed": True,
                    "status": "Completed",
                }
            )
            self._refresh_downloads_list()
            print(f"Blob saved: {out_path}")
        except Exception as e:
            print(f"Blob save failed: {e}")

    def _download_blob_from_page(self, page: QWebEnginePage, blob_url: str):
        # Attempt to resolve a filename from any anchor pointing at the blob.
        # Then fetch(blob_url) inside the page context and send it over WebChannel.
        js = r"""
(function() {
  const blobUrl = %BLOB_URL%;

  function pickFilename() {
    try {
      const a = document.querySelector('a[href="' + blobUrl.replace(/"/g, '\\"') + '"]');
      if (a) {
        return a.getAttribute('download') || a.getAttribute('data-filename') || 'download';
      }
    } catch (e) {}
    return 'download';
  }

  function doFetch(flowBridge) {
    const filename = pickFilename();
    fetch(blobUrl).then(r => r.blob()).then(blob => {
      const reader = new FileReader();
      reader.onloadend = function() {
        try {
          flowBridge.saveBlob(reader.result, filename);
        } catch (err) {
          flowBridge.saveBlobError(String(err));
        }
      };
      reader.onerror = function() {
        flowBridge.saveBlobError('FileReader failed');
      };
      reader.readAsDataURL(blob);
    }).catch(err => {
      flowBridge.saveBlobError(String(err));
    });
  }

  function setupWebChannelAndFetch() {
    if (window.flowBridge) {
      doFetch(window.flowBridge);
      return;
    }
    if (!window.qt || !qt.webChannelTransport) {
      console.log('Flow: qt.webChannelTransport not available');
      return;
    }
    new QWebChannel(qt.webChannelTransport, function(channel) {
      window.flowBridge = channel.objects.flowBridge;
      doFetch(window.flowBridge);
    });
  }

  if (typeof QWebChannel === 'undefined') {
    const s = document.createElement('script');
    s.src = 'qrc:///qtwebchannel/qwebchannel.js';
    s.onload = setupWebChannelAndFetch;
    document.documentElement.appendChild(s);
  } else {
    setupWebChannelAndFetch();
  }
})();
"""

        js = js.replace("%BLOB_URL%", repr(blob_url))
        try:
            page.runJavaScript(js)
        except Exception as e:
            print(f"Failed to fetch blob from page: {e}")

    def _install_blob_download_hook(self, web_view: QWebEngineView):
        # Inject a click handler that captures <a href="blob:..." download="..."> and
        # streams the blob to Python for saving.
        js = r"""
(function() {
  if (window.__flow_blob_hook_installed) return;
  window.__flow_blob_hook_installed = true;

  function install() {
    if (!window.flowBridge) return;

    document.addEventListener('click', function(e) {
      try {
        const a = e.target && e.target.closest ? e.target.closest('a') : null;
        if (!a) return;
        const href = a.getAttribute('href') || '';
        if (!href.startsWith('blob:')) return;

        // Prevent the browser's internal handling (which often no-ops in Qt).
        e.preventDefault();
        e.stopPropagation();

        const filename = a.getAttribute('download') || a.getAttribute('data-filename') || 'download';

        fetch(href).then(r => r.blob()).then(blob => {
          const reader = new FileReader();
          reader.onloadend = function() {
            try {
              window.flowBridge.saveBlob(reader.result, filename);
            } catch (err) {
              window.flowBridge.saveBlobError(String(err));
            }
          };
          reader.onerror = function() {
            window.flowBridge.saveBlobError('FileReader failed');
          };
          reader.readAsDataURL(blob);
        }).catch(err => {
          window.flowBridge.saveBlobError(String(err));
        });
      } catch (err) {
        if (window.flowBridge) window.flowBridge.saveBlobError(String(err));
      }
    }, true);
  }

  // Ensure qwebchannel.js is available and bind window.flowBridge.
  function setupWebChannel() {
    if (window.flowBridge) {
      install();
      return;
    }
    if (!window.qt || !qt.webChannelTransport) {
      return;
    }
    new QWebChannel(qt.webChannelTransport, function(channel) {
      window.flowBridge = channel.objects.flowBridge;
      install();
    });
  }

  if (typeof QWebChannel === 'undefined') {
    const s = document.createElement('script');
    s.src = 'qrc:///qtwebchannel/qwebchannel.js';
    s.onload = setupWebChannel;
    document.documentElement.appendChild(s);
  } else {
    setupWebChannel();
  }
})();
"""
        try:
            web_view.page().runJavaScript(js)
        except Exception as e:
            print(f"Failed to install blob hook: {e}")

    def _looks_like_download_url(self, url: QUrl) -> bool:
        # Heuristic. There is no perfect way to detect "download buttons" without
        # site-specific logic or deeper JS integration.
        path = (url.path() or "").lower()
        query = (url.query() or "").lower()

        exts = (
            ".zip",
            ".7z",
            ".rar",
            ".tar",
            ".gz",
            ".bz2",
            ".xz",
            ".jar",
            ".exe",
            ".msi",
            ".apk",
            ".dmg",
            ".iso",
            ".pdf",
        )

        if any(path.endswith(ext) for ext in exts):
            return True

        # Common download-ish paths/queries.
        if "/download" in path or "/downloads" in path:
            return True
        if "download" in query:
            return True

        return False

    def download_current_url(self):
        """Force-download the current tab's URL using Chromium's downloader."""
        current_tab = self.tabs.currentWidget()
        if not current_tab or not hasattr(current_tab, "web_view"):
            return

        url = current_tab.web_view.url()
        if not url.isValid():
            return

        current_tab.web_view.page().download(url, url.fileName())
    
    def _tab_index_for_view(self, view):
        for i in range(self.tabs.count()):
            w = self.tabs.widget(i)
            if hasattr(w, "web_view") and w.web_view is view:
                return i
        return -1

    def on_tab_changed(self, index):
        current_tab = self.tabs.widget(index)
        if not current_tab or not hasattr(current_tab, "web_view"):
            return

        # Sync omnibox + nav buttons to the newly selected tab
        self.url_bar.setText(current_tab.web_view.url().toString())
        self.update_nav_buttons(view=current_tab.web_view)

    def update_tab_title(self, title, view=None):
        index = self.tabs.currentIndex() if view is None else self._tab_index_for_view(view)
        if index >= 0:
            self.tabs.setTabText(index, title)

    def update_url_bar(self, url, view=None):
        # Only update the URL bar if the signal is from the active tab
        current_tab = self.tabs.currentWidget()
        if current_tab and hasattr(current_tab, "web_view"):
            if view is not None and view is not current_tab.web_view:
                return
        self.url_bar.setText(url.toString())

    def update_nav_buttons(self, *args, view=None):
        current_tab = self.tabs.currentWidget()
        if current_tab and hasattr(current_tab, "web_view"):
            if view is not None and view is not current_tab.web_view:
                return
            self.back_btn.setEnabled(current_tab.web_view.history().canGoBack())
            self.forward_btn.setEnabled(current_tab.web_view.history().canGoForward())
    
    def add_to_history(self):
        current_tab = self.tabs.currentWidget()
        if current_tab:
            url = current_tab.web_view.url().toString()
            title = current_tab.web_view.title()
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.history.append({"url": url, "title": title, "timestamp": timestamp})
    
    def handle_new_window(self, request):
        url = request.requestedUrl()

        # The sender is the page that triggered window.open / target=_blank.
        sender_page = self.sender()
        if not isinstance(sender_page, QWebEnginePage):
            sender_page = None

        # Handle blob popups directly: fetch blob bytes in the sender page's context.
        if url.isValid() and url.scheme() == "blob":
            try:
                self._download_blob_from_page(sender_page or self.tabs.currentWidget().web_view.page(), url.toString())
            except Exception as e:
                print(f"handle_new_window blob error: {e}")
            return

        if url.isValid() and self._looks_like_download_url(url):
            # Force download instead of opening a new tab.
            try:
                if sender_page is not None:
                    sender_page.download(url, url.fileName())
                else:
                    current_tab = self.tabs.currentWidget()
                    if current_tab and hasattr(current_tab, "web_view"):
                        current_tab.web_view.page().download(url, url.fileName())
            except Exception as e:
                print(f"handle_new_window download error: {e}")
            return

        # Open a real new tab, but keep a reference to the opener page so blob downloads
        # that redirect through about:blank can still be fetched from the correct origin.
        new_view = self.add_new_tab(opener_page=sender_page)
        request.openIn(new_view.page())
    
    def handle_full_screen(self, request):
        if request.toggleOn():
            self.showFullScreen()
        else:
            self.showNormal()
        request.accept()
    
    def handle_feature_permission(self, url, feature):
        self.sender().setFeaturePermission(url, feature, QWebEnginePage.PermissionPolicy.PermissionGrantedByUser)
    
    def open_devtools(self):
        current_tab = self.tabs.currentWidget()
        if not current_tab or not hasattr(current_tab, "web_view"):
            return

        # If DevTools is already open for this tab, focus it.
        existing = getattr(current_tab, "_devtools_tab", None)
        if existing is not None:
            existing_idx = self.tabs.indexOf(existing)
            if existing_idx >= 0:
                self.tabs.setCurrentIndex(existing_idx)
                return

        dev_tab = QWidget()
        dev_tab.is_devtools = True
        dev_tab._inspected_tab = current_tab

        layout = QVBoxLayout(dev_tab)
        layout.setContentsMargins(0, 0, 0, 0)
        dev_view = QWebEngineView()
        layout.addWidget(dev_view)
        dev_tab.web_view = dev_view

        # Make this page show DevTools UI for the inspected page.
        dev_view.page().setInspectedPage(current_tab.web_view.page())

        title = (current_tab.web_view.title() or "")
        tab_title = f"Inspect: {title}" if title else "Inspect"
        idx = self.tabs.addTab(dev_tab, tab_title)
        self.tabs.setCurrentIndex(idx)

        # Keep linkage so closing either side can clean up.
        current_tab._devtools_tab = dev_tab

        # Update the DevTools tab title when the inspected page title changes.
        current_tab.web_view.titleChanged.connect(
            lambda t, devtab=dev_tab: self._update_devtools_tab_title(devtab, t)
        )

    def _update_devtools_tab_title(self, devtools_tab, inspected_title: str):
        idx = self.tabs.indexOf(devtools_tab)
        if idx >= 0:
            self.tabs.setTabText(idx, f"Inspect: {inspected_title}" if inspected_title else "Inspect")

    def close_tab(self, index):
        if self.tabs.count() <= 1:
            return

        tab = self.tabs.widget(index)
        if tab is None:
            return

        # If closing an inspected page, also close its DevTools tab.
        devtools = getattr(tab, "_devtools_tab", None)
        if devtools is not None:
            dev_idx = self.tabs.indexOf(devtools)
            if dev_idx >= 0:
                self.tabs.removeTab(dev_idx)

        # If closing DevTools, clear the linkage on the inspected tab.
        if getattr(tab, "is_devtools", False):
            inspected = getattr(tab, "_inspected_tab", None)
            if inspected is not None and getattr(inspected, "_devtools_tab", None) is tab:
                inspected._devtools_tab = None

        self.tabs.removeTab(index)
    
    def load_url(self):
        url = self.url_bar.text().strip()
        
        # Detect if input is a search query or a URL
        if not url.startswith("http"):
            # Has URL-like characters (scheme, path, or @) -> treat as URL
            if "://" in url or "/" in url or "@" in url:
                url = url if url.startswith("http") else "https://" + url
            # Has spaces -> likely a search query
            elif " " in url:
                search_query = url.replace(" ", "+")
                url = f"https://www.startpage.com/sp/search?q={search_query}"
            # Has a dot and no spaces -> likely a domain
            elif "." in url:
                url = "https://" + url
            # No spaces, no dots -> search query
            else:
                url = f"https://www.startpage.com/sp/search?q={url}"
        
        current_tab = self.tabs.currentWidget()
        if current_tab:
            current_tab.web_view.load(QUrl(url))
    
    def show_settings(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Settings")
        dialog.setGeometry(200, 200, 400, 300)
        
        layout = QVBoxLayout()
        
        # Theme setting
        theme_layout = QHBoxLayout()
        theme_layout.addWidget(QLabel("Theme:"))
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["Light", "Dark"])
        self.theme_combo.setCurrentText("Light" if self.current_theme == "light" else "Dark")
        self.theme_combo.currentTextChanged.connect(self.change_theme_setting)
        theme_layout.addWidget(self.theme_combo)
        layout.addLayout(theme_layout)
        
        # Home page setting
        home_layout = QHBoxLayout()
        home_layout.addWidget(QLabel("Home Page:"))
        self.home_edit = QLineEdit("https://www.startpage.com")
        home_layout.addWidget(self.home_edit)
        layout.addLayout(home_layout)
        
        dialog.setLayout(layout)
        dialog.exec()

    def change_theme_setting(self, theme):
        self.current_theme = theme.lower()
        self.apply_theme()
        # Apply theme logic here if needed

    def _cookies_dir(self) -> Path:
        # Store cookies next to flow.py (repo root), in ./flow-cookies
        return Path(__file__).resolve().parent / "flow-cookies"

    def _cookies_storage_path(self) -> Path:
        # Store cookies in a JSON file for easy inspection and export
        return self._cookies_dir() / "cookies.json"

    def _load_cookies_from_disk(self) -> dict:
        """Load cookies from disk. Returns dict mapping domain -> list of cookies."""
        cookies_file = self._cookies_storage_path()
        if not cookies_file.exists():
            return {}

        try:
            with open(cookies_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            print(f"Error loading cookies: {e}")
            return {}

    def _save_cookies_to_disk(self, cookies_data: dict) -> None:
        """Save cookies to disk in JSON format."""
        cookies_dir = self._cookies_dir()
        cookies_dir.mkdir(parents=True, exist_ok=True)

        try:
            with open(self._cookies_storage_path(), "w", encoding="utf-8") as f:
                json.dump(cookies_data, f, indent=2, ensure_ascii=False)
        except IOError as e:
            print(f"Error saving cookies: {e}")

    def _extract_cookies_from_profile(self) -> dict:
        """Extract cookies from the WebEngine profile."""
        profile = _get_persistent_profile()
        cookie_store = profile.cookieStore()

        cookies_data = {}

        # Qt doesn't expose a direct way to enumerate cookies, so we store them
        # when they're set. This is a limitation we'll document.
        # For now, return the stored cookies from disk.
        return self._load_cookies_from_disk()

    def _sync_cookies_on_load(self) -> None:
        """Sync cookies from storage to the web profile on startup."""
        # This is a placeholder - Qt WebEngine handles cookie persistence
        # automatically to a default location. Manual sync would require
        # using Qt's cookie store API which has limited access.
        pass

    def _bookmarks_dir(self) -> Path:
        # Store bookmarks next to flow.py (repo root), in ./flow-bookmarks
        return Path(__file__).resolve().parent / "flow-bookmarks"

    def _bookmark_files(self) -> list[tuple[int, Path]]:
        bookmarks_dir = self._bookmarks_dir()
        if not bookmarks_dir.exists():
            return []

        numbered: list[tuple[int, Path]] = []
        for p in bookmarks_dir.glob("bk*.txt"):
            m = re.fullmatch(r"bk(\d+)\.txt", p.name, flags=re.IGNORECASE)
            if not m:
                continue
            numbered.append((int(m.group(1)), p))

        numbered.sort(key=lambda t: t[0])
        return numbered

    def _load_bookmarks_from_disk(self) -> None:
        # Ensure the folder exists so users can drop files in here manually.
        self._bookmarks_dir().mkdir(parents=True, exist_ok=True)

        self.bookmarks = []
        for idx, p in self._bookmark_files():
            try:
                url = p.read_text(encoding="utf-8").strip()
            except UnicodeDecodeError:
                url = p.read_text(encoding="utf-8", errors="ignore").strip()

            if not url:
                continue

            # Files store URL only; show a stable label based on the filename.
            self.bookmarks.append({"title": f"bk{idx}", "url": url})

    def _save_bookmarks_to_disk(self) -> None:
        bookmarks_dir = self._bookmarks_dir()
        bookmarks_dir.mkdir(parents=True, exist_ok=True)

        # Keep only valid URLs.
        self.bookmarks = [b for b in self.bookmarks if (b.get("url") or "").strip()]

        # Remove existing bk*.txt files.
        for p in bookmarks_dir.glob("bk*.txt"):
            m = re.fullmatch(r"bk(\d+)\.txt", p.name, flags=re.IGNORECASE)
            if not m:
                continue
            try:
                p.unlink()
            except FileNotFoundError:
                pass

        # Write sequential files (bk1.txt, bk2.txt, ...)
        for i, bookmark in enumerate(self.bookmarks, start=1):
            url = (bookmark.get("url") or "").strip()
            (bookmarks_dir / f"bk{i}.txt").write_text(url + "\n", encoding="utf-8")

    def show_bookmarks(self):
        # Reload from disk each time so the dialog always reflects the folder.
        self._load_bookmarks_from_disk()

        dialog = QDialog(self)
        dialog.setWindowTitle("Bookmarks")
        dialog.setGeometry(200, 200, 500, 400)
        
        layout = QVBoxLayout()
        
        # Bookmarks list
        self.bookmarks_list = QListWidget()  # Removed redundant import
        for bookmark in self.bookmarks:
            self.bookmarks_list.addItem(f"{bookmark['title']} - {bookmark['url']}")
        self.bookmarks_list.itemDoubleClicked.connect(lambda item: self.open_bookmark())
        layout.addWidget(self.bookmarks_list)
        
        # Buttons
        button_layout = QHBoxLayout()  # Removed redundant import
        add_btn = QPushButton("Add Current Page")  # Removed redundant import
        add_btn.clicked.connect(lambda: self.add_bookmark(dialog))
        button_layout.addWidget(add_btn)
        
        open_btn = QPushButton("Open Selected")
        open_btn.clicked.connect(lambda: self.open_bookmark())
        button_layout.addWidget(open_btn)
        
        remove_btn = QPushButton("Remove Selected")
        remove_btn.clicked.connect(lambda: self.remove_bookmark())
        button_layout.addWidget(remove_btn)
        
        layout.addLayout(button_layout)
        dialog.setLayout(layout)
        dialog.exec()  # Updated from exec_() to exec()

    def add_bookmark(self, dialog):
        current_tab = self.tabs.currentWidget()
        if current_tab:
            web_view = current_tab.web_view
            url = web_view.url().toString().strip()
            title = web_view.title() or "Untitled"

            if not url:
                return

            self.bookmarks.append({"title": title, "url": url})
            self._save_bookmarks_to_disk()
            self.bookmarks_list.addItem(f"{title} - {url}")

    def open_bookmark(self):
        selected = self.bookmarks_list.currentRow()
        if selected >= 0:
            bookmark = self.bookmarks[selected]
            self.add_new_tab(bookmark["url"])

    def remove_bookmark(self):
        selected = self.bookmarks_list.currentRow()
        if selected >= 0:
            del self.bookmarks[selected]
            self._save_bookmarks_to_disk()
            self.bookmarks_list.takeItem(selected)

    def show_history(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("History")
        dialog.setGeometry(200, 200, 600, 400)
        
        layout = QVBoxLayout()
        
        # History list
        self.history_list = QListWidget()  # Removed redundant import
        for entry in reversed(self.history[-50:]):  # Show last 50 entries
            self.history_list.addItem(f"{entry['timestamp']} - {entry['title']} - {entry['url']}")
        self.history_list.itemDoubleClicked.connect(lambda item: self.open_history_item())
        layout.addWidget(self.history_list)
        
        # Buttons
        button_layout = QHBoxLayout()  # Removed redundant import
        open_btn = QPushButton("Open Selected")  # Removed redundant import
        open_btn.clicked.connect(lambda: self.open_history_item())
        button_layout.addWidget(open_btn)
        
        clear_btn = QPushButton("Clear History")
        clear_btn.clicked.connect(lambda: self.clear_history(dialog))
        button_layout.addWidget(clear_btn)
        
        layout.addLayout(button_layout)
        dialog.setLayout(layout)
        dialog.exec()  # Updated from exec_() to exec()

    def open_history_item(self):
        selected = self.history_list.currentRow()
        if selected >= 0:
            entry = list(reversed(self.history[-50:]))[selected]
            self.add_new_tab(entry["url"])

    def clear_history(self, dialog):
        self.history.clear()
        self.history_list.clear()
        dialog.accept()

    def _downloads_dir(self) -> Path:
        # Best-effort default downloads location.
        return Path.home() / "Downloads"

    def _sanitize_filename(self, filename: str) -> str:
        # Windows forbids: < > : " / \ | ? *
        bad = '<>:"/\\|?*'
        cleaned = "".join(("_" if c in bad else c) for c in (filename or "download"))
        cleaned = cleaned.strip().strip(".")  # avoid trailing dots/spaces on Windows
        return cleaned or "download"

    def _unique_download_filename(self, directory: Path, filename: str) -> str:
        filename = self._sanitize_filename(Path(filename).name)
        base = Path(filename).stem
        suffix = Path(filename).suffix

        candidate = directory / filename
        if not candidate.exists():
            return filename

        i = 1
        while True:
            alt = directory / f"{base} ({i}){suffix}"
            if not alt.exists():
                return alt.name
            i += 1

    def _format_download_item(self, d: dict) -> str:
        received = int(d.get("received", 0) or 0)
        total = int(d.get("total", 0) or 0)

        # QWebEngine-driven downloads store a DownloadState in d["state"].
        # Forced HTTP downloads store a human-readable d["status"].
        state = d.get("state")
        if state is None:
            status = d.get("status") or ("Completed" if d.get("completed") else "In Progress")
        elif state == QWebEngineDownloadRequest.DownloadState.DownloadCompleted:
            status = "Completed"
        elif state == QWebEngineDownloadRequest.DownloadState.DownloadCancelled:
            status = "Cancelled"
        elif state == QWebEngineDownloadRequest.DownloadState.DownloadInterrupted:
            reason = (d.get("interrupt_str") or "").strip()
            status = f"Interrupted: {reason}" if reason else "Interrupted"
        else:
            status = "In Progress"

        if total > 0:
            pct = int((received / total) * 100)
            progress = f"{pct}% ({received}/{total} bytes)"
        elif received > 0:
            progress = f"{received} bytes"
        else:
            progress = ""

        parts = [d.get("filename", "download"), status]
        if progress:
            parts.append(progress)
        parts.append(d.get("url", ""))
        return " - ".join(parts)

    def _refresh_downloads_list(self):
        if self.downloads_list is None:
            return

        # The dialog can be closed while downloads are still in progress; in that case
        # the Qt widget is deleted and touching it raises RuntimeError.
        try:
            self.downloads_list.clear()
            for d in self.downloads:
                self.downloads_list.addItem(self._format_download_item(d))
        except RuntimeError:
            self.downloads_list = None

    def _on_download_updated(self, request: QWebEngineDownloadRequest):
        for d in self.downloads:
            if d.get("request") is request:
                d["received"] = int(request.receivedBytes())
                d["total"] = int(request.totalBytes())
                d["state"] = request.state()
                d["interrupt"] = request.interruptReason()
                d["interrupt_str"] = request.interruptReasonString()
                d["completed"] = bool(request.isFinished())

                if d["completed"]:
                    print(
                        f"Download finished: url={d.get('url')} state={d.get('state')} interrupt={d.get('interrupt_str')}"
                    )
                break

        # If the Downloads dialog is open, keep it live.
        self._refresh_downloads_list()

    def _on_download_requested(self, request: QWebEngineDownloadRequest):
        directory = self._downloads_dir()
        try:
            directory.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            print(f"Error creating downloads directory {directory}: {e}")

        suggested = request.suggestedFileName() or request.downloadFileName() or "download"
        filename = self._unique_download_filename(directory, suggested)

        request.setDownloadDirectory(str(directory))
        request.setDownloadFileName(filename)

        entry = {
            "request": request,
            "filename": filename,
            "url": request.url().toString(),
            "path": str(directory / filename),
            "received": int(request.receivedBytes()),
            "total": int(request.totalBytes()),
            "state": request.state(),
            "interrupt": request.interruptReason(),
            "interrupt_str": request.interruptReasonString(),
            "completed": bool(request.isFinished()),
        }
        self.downloads.append(entry)

        print(
            f"Download requested: url={request.url().toString()} mime={request.mimeType()} suggested={request.suggestedFileName()}"
        )

        # Live updates
        request.receivedBytesChanged.connect(lambda *_: self._on_download_updated(request))
        request.totalBytesChanged.connect(lambda *_: self._on_download_updated(request))
        request.stateChanged.connect(lambda *_: self._on_download_updated(request))
        request.interruptReasonChanged.connect(lambda *_: self._on_download_updated(request))
        request.isFinishedChanged.connect(lambda *_: self._on_download_updated(request))

        # Trigger initial UI refresh and start the download.
        self._refresh_downloads_list()
        request.accept()

    def _on_downloads_dialog_finished(self, *_):
        self._downloads_dialog = None
        self.downloads_list = None

    def show_downloads(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Downloads")
        dialog.setGeometry(200, 200, 600, 400)

        self._downloads_dialog = dialog
        dialog.finished.connect(self._on_downloads_dialog_finished)
        
        layout = QVBoxLayout()
        
        # Downloads list
        self.downloads_list = QListWidget()  # Removed redundant import
        layout.addWidget(self.downloads_list)
        self._refresh_downloads_list()
        
        # Buttons
        button_layout = QHBoxLayout()  # Removed redundant import
        open_btn = QPushButton("Open File Location")  # Removed redundant import
        open_btn.clicked.connect(lambda: self.open_download_location())
        button_layout.addWidget(open_btn)
        
        remove_btn = QPushButton("Remove Selected")
        remove_btn.clicked.connect(lambda: self.remove_download())
        button_layout.addWidget(remove_btn)
        
        layout.addLayout(button_layout)
        dialog.setLayout(layout)
        dialog.exec()  # Updated from exec_() to exec()

    def open_download_location(self):
        """Open the selected download's location (or Downloads folder if none selected)."""
        # Default to the Downloads folder.
        target_dir = str(self._downloads_dir())

        selected = -1
        if self.downloads_list is not None:
            selected = self.downloads_list.currentRow()

        try:
            if selected is not None and selected >= 0 and selected < len(self.downloads):
                path = self.downloads[selected].get("path")
                if path and os.path.exists(path):
                    if platform.system() == "Windows":
                        # explorer expects: /select,"C:\path\to\file"
                        subprocess.Popen(["explorer", f'/select,"{path}"'])
                        return
                    # macOS/Linux: open the directory
                    target_dir = str(Path(path).parent)

            if platform.system() == "Windows":
                subprocess.Popen(["explorer", target_dir])
            elif platform.system() == "Darwin":
                subprocess.Popen(["open", target_dir])
            else:
                subprocess.Popen(["xdg-open", target_dir])
        except Exception as e:
            print(f"Error opening download location: {e}")

    def remove_download(self):
        if not self.downloads_list:
            return

        selected = self.downloads_list.currentRow()
        if selected >= 0 and selected < len(self.downloads):
            d = self.downloads[selected]
            req = d.get("request")
            try:
                # If it's still running, cancel before removing.
                if req and req.state() == QWebEngineDownloadRequest.DownloadState.DownloadInProgress:
                    req.cancel()
            except Exception:
                pass

            del self.downloads[selected]
            self._refresh_downloads_list()

    def show_cookies(self):
        """Display and manage cookies from the flow-cookies directory."""
        # Load cookies from disk
        cookies_data = self._load_cookies_from_disk()

        dialog = QDialog(self)
        dialog.setWindowTitle("Cookies")
        dialog.setGeometry(200, 200, 700, 500)

        layout = QVBoxLayout()

        # Cookies list
        cookies_list = QListWidget()
        if cookies_data:
            for domain, cookies in cookies_data.items():
                for cookie in cookies:
                    cookie_name = cookie.get("name", "Unknown")
                    cookie_value = cookie.get("value", "")
                    expires = cookie.get("expires", "Session")
                    cookies_list.addItem(f"{domain} | {cookie_name}={cookie_value[:30]}{'...' if len(cookie_value) > 30 else ''} (expires: {expires})")
        else:
            cookies_list.addItem("No cookies stored")
        layout.addWidget(cookies_list)

        # Buttons
        button_layout = QHBoxLayout()
        
        open_folder_btn = QPushButton("Open Cookies Folder")
        open_folder_btn.clicked.connect(lambda: self._open_cookies_folder())
        button_layout.addWidget(open_folder_btn)

        clear_btn = QPushButton("Clear All Cookies")
        clear_btn.clicked.connect(lambda: self._clear_all_cookies(dialog, cookies_list))
        button_layout.addWidget(clear_btn)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(lambda: self._refresh_cookies_list(dialog, cookies_list))
        button_layout.addWidget(refresh_btn)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dialog.accept)
        button_layout.addWidget(close_btn)

        layout.addLayout(button_layout)
        dialog.setLayout(layout)
        dialog.exec()

    def _open_cookies_folder(self):
        """Open the flow-cookies folder in the file explorer."""
        cookies_dir = str(self._cookies_dir())
        cookies_dir_path = Path(cookies_dir)
        cookies_dir_path.mkdir(parents=True, exist_ok=True)

        try:
            if platform.system() == "Windows":
                subprocess.Popen(["explorer", cookies_dir])
            elif platform.system() == "Darwin":
                subprocess.Popen(["open", cookies_dir])
            else:
                subprocess.Popen(["xdg-open", cookies_dir])
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not open cookies folder: {e}")

    def _clear_all_cookies(self, dialog, cookies_list):
        """Clear all cookies and update the UI."""
        reply = QMessageBox.question(
            dialog,
            "Clear All Cookies",
            "Are you sure you want to delete all stored cookies?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            # Clear the stored cookies file
            self._save_cookies_to_disk({})
            
            # Also try to clear WebEngine cookies
            profile = _get_persistent_profile()
            profile.cookieStore().deleteAllCookies()
            
            # Update the list
            cookies_list.clear()
            cookies_list.addItem("No cookies stored")
            QMessageBox.information(dialog, "Success", "All cookies have been cleared.")

    def _refresh_cookies_list(self, dialog, cookies_list):
        """Refresh the cookies list from disk."""
        cookies_data = self._load_cookies_from_disk()
        cookies_list.clear()

        if cookies_data:
            for domain, cookies in cookies_data.items():
                for cookie in cookies:
                    cookie_name = cookie.get("name", "Unknown")
                    cookie_value = cookie.get("value", "")
                    expires = cookie.get("expires", "Session")
                    cookies_list.addItem(f"{domain} | {cookie_name}={cookie_value[:30]}{'...' if len(cookie_value) > 30 else ''} (expires: {expires})")
        else:
            cookies_list.addItem("No cookies stored")

    # ...existing code...

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())