import sys
from PyQt6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QLineEdit, QPushButton, QHBoxLayout, QTabWidget, QListWidget, QSplitter, QDialog, QLabel, QFormLayout, QComboBox, QCheckBox, QToolBar, QMenu
from PyQt6.QtGui import QAction, QPalette, QColor
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEnginePage, QWebEngineSettings
from PyQt6.QtCore import QUrl, Qt

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.current_theme = "dark"
        self.web_dark_mode = False
        self.bookmarks = []
        self.history = []
        self.downloads = []
        
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
        self.app_menu.addSeparator()

        # Former "View" actions
        self.app_menu.addAction("Bookmarks", self.show_bookmarks)
        self.app_menu.addAction("History", self.show_history)
        self.app_menu.addAction("Downloads", self.show_downloads)
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
        
        # Home button: keep text, but make it wider so it doesn't clip
        self.home_btn = QPushButton("Home")
        self.home_btn.setToolTip("Home")
        self.home_btn.setProperty("chromeNav", True)
        self.home_btn.setProperty("homeButton", True)  # Specific property for home button styling
        self.home_btn.setFixedHeight(34)
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
  
    def add_new_tab(self, url="https://www.startpage.com"):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        web_view = QWebEngineView()
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
        
        # Handle new windows (like popups or new tabs from links)
        web_view.page().newWindowRequested.connect(self.handle_new_window)
        web_view.page().fullScreenRequested.connect(self.handle_full_screen)
        web_view.page().featurePermissionRequested.connect(self.handle_feature_permission)
        
        # Connect signals
        web_view.titleChanged.connect(lambda title, view=web_view: self.update_tab_title(title, view))
        web_view.urlChanged.connect(lambda url, view=web_view: self.update_url_bar(url, view))
        web_view.urlChanged.connect(lambda _url, view=web_view: self.update_nav_buttons(view=view))
        web_view.loadFinished.connect(self.add_to_history)
        
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
        new_view = self.add_new_tab()
        request.openIn(new_view.page())
    
    def handle_full_screen(self, request):
        if request.toggleOn():
            self.showFullScreen()
        else:
            self.showNormal()
        request.accept()
    
    def handle_feature_permission(self, url, feature):
        self.sender().setFeaturePermission(url, feature, QWebEnginePage.PermissionPolicy.PermissionGrantedByUser)
    
    def close_tab(self, index):
        if self.tabs.count() > 1:
            self.tabs.removeTab(index)
    
    def load_url(self):
        url = self.url_bar.text()
        if not url.startswith("http"):
            url = "https://" + url
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

    def show_bookmarks(self):
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
            url = web_view.url().toString()
            title = web_view.title() or "Untitled"
            self.bookmarks.append({"title": title, "url": url})
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

    def show_downloads(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Downloads")
        dialog.setGeometry(200, 200, 600, 400)
        
        layout = QVBoxLayout()
        
        # Downloads list
        self.downloads_list = QListWidget()  # Removed redundant import
        for download in self.downloads:
            status = "Completed" if download.get('completed', False) else "In Progress"
            self.downloads_list.addItem(f"{download['filename']} - {status} - {download['url']}")
        layout.addWidget(self.downloads_list)
        
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
        """Open the Downloads folder in the system file manager."""
        import subprocess
        import platform
        import os
        from pathlib import Path
        
        # Get Downloads folder path
        if sys.platform == "win32":
            downloads_path = Path.home() / "Downloads"
        elif sys.platform == "darwin":
            downloads_path = Path.home() / "Downloads"
        else:
            downloads_path = Path.home() / "Downloads"
        
        downloads_path = str(downloads_path)
        
        try:
            if platform.system() == "Windows":
                subprocess.Popen(f'explorer "{downloads_path}"')
            elif platform.system() == "Darwin":
                subprocess.Popen(["open", downloads_path])
            else:
                subprocess.Popen(["xdg-open", downloads_path])
        except Exception as e:
            print(f"Error opening Downloads folder: {e}")

    def remove_download(self):
        selected = self.downloads_list.currentRow()
        if selected >= 0:
            del self.downloads[selected]
            self.downloads_list.takeItem(selected)

    # ...existing code... (open_download_location, remove_download, and the rest of the file remain unchanged)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())