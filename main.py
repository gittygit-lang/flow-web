import sys
from PyQt6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QLineEdit, QPushButton, QHBoxLayout, QTabWidget, QListWidget, QSplitter, QDialog, QLabel, QFormLayout, QComboBox, QCheckBox, QToolBar, QMenuBar
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
        
        # Menu bar
        file_menu = self.menuBar().addMenu("File")
        file_menu.addAction("New Tab", self.add_new_tab)
        file_menu.addAction("Close Tab", self.close_current_tab)
        
        view_menu = self.menuBar().addMenu("View")
        view_menu.addAction("Bookmarks", self.show_bookmarks)
        view_menu.addAction("History", self.show_history)
        view_menu.addAction("Downloads", self.show_downloads)
        view_menu.addAction("Settings", self.show_settings)
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # Top row: buttons and URL bar
        top_layout = QHBoxLayout()
        
        # Buttons container
        button_widget = QWidget()
        button_layout = QHBoxLayout(button_widget)
        button_layout.setContentsMargins(0, 0, 0, 0)
        self.back_btn = QPushButton("←")
        self.back_btn.clicked.connect(self.go_back)
        button_layout.addWidget(self.back_btn)
        
        self.forward_btn = QPushButton("→")
        self.forward_btn.clicked.connect(self.go_forward)
        button_layout.addWidget(self.forward_btn)
        
        self.refresh_btn = QPushButton("↻")
        self.refresh_btn.clicked.connect(self.refresh_page)
        button_layout.addWidget(self.refresh_btn)
        
        self.home_btn = QPushButton("Home")
        self.home_btn.clicked.connect(self.go_home)
        button_layout.addWidget(self.home_btn)

        top_layout.addWidget(button_widget, 1)
        
        # URL bar
        self.url_bar = QLineEdit()
        self.url_bar.returnPressed.connect(self.load_url)
        top_layout.addWidget(self.url_bar, 3)  # URL bar takes 75%
        
        layout.addLayout(top_layout)
        
        # Tab widget
        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.tabs.currentChanged.connect(self.update_nav_buttons)
        layout.addWidget(self.tabs)
        
        # Add initial tab
        self.add_new_tab()
        self.apply_theme()

        
    
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
            palette = QPalette()
            palette.setColor(QPalette.ColorRole.Window, Qt.GlobalColor.black)
            palette.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.white)
            palette.setColor(QPalette.ColorRole.Base, Qt.GlobalColor.black)
            palette.setColor(QPalette.ColorRole.AlternateBase, QColor(30, 30, 30))
            palette.setColor(QPalette.ColorRole.ToolTipBase, Qt.GlobalColor.black)
            palette.setColor(QPalette.ColorRole.ToolTipText, Qt.GlobalColor.white)
            palette.setColor(QPalette.ColorRole.Text, Qt.GlobalColor.white)
            palette.setColor(QPalette.ColorRole.Button, QColor(30, 30, 30))
            palette.setColor(QPalette.ColorRole.ButtonText, Qt.GlobalColor.white)
            palette.setColor(QPalette.ColorRole.BrightText, Qt.GlobalColor.red)
            palette.setColor(QPalette.ColorRole.Link, QColor(42, 130, 218))
            palette.setColor(QPalette.ColorRole.Highlight, QColor(42, 130, 218))
            palette.setColor(QPalette.ColorRole.HighlightedText, Qt.GlobalColor.black)
            self.setPalette(palette)
        else:
            # Light theme with white background
            palette = QPalette()
            palette.setColor(QPalette.ColorRole.Window, Qt.GlobalColor.white)
            palette.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.black)
            palette.setColor(QPalette.ColorRole.Base, Qt.GlobalColor.white)
            palette.setColor(QPalette.ColorRole.AlternateBase, QColor(240, 240, 240))
            palette.setColor(QPalette.ColorRole.ToolTipBase, Qt.GlobalColor.white)
            palette.setColor(QPalette.ColorRole.ToolTipText, Qt.GlobalColor.black)
            palette.setColor(QPalette.ColorRole.Text, Qt.GlobalColor.black)
            palette.setColor(QPalette.ColorRole.Button, QColor(240, 240, 240))
            palette.setColor(QPalette.ColorRole.ButtonText, Qt.GlobalColor.black)
            palette.setColor(QPalette.ColorRole.BrightText, Qt.GlobalColor.red)
            palette.setColor(QPalette.ColorRole.Link, QColor(0, 0, 255))
            palette.setColor(QPalette.ColorRole.Highlight, QColor(0, 120, 215))
            palette.setColor(QPalette.ColorRole.HighlightedText, Qt.GlobalColor.white)
            self.setPalette(palette)
    
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
        web_view.titleChanged.connect(lambda title: self.update_tab_title(title))
        web_view.urlChanged.connect(lambda url: self.update_url_bar(url))
        web_view.urlChanged.connect(self.update_nav_buttons)
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
    
    def update_tab_title(self, title):
        index = self.tabs.currentIndex()
        self.tabs.setTabText(index, title)
    
    def update_url_bar(self, url):
        self.url_bar.setText(url.toString())
    
    def update_nav_buttons(self):
        current_tab = self.tabs.currentWidget()
        if current_tab:
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
        # Implement opening file location
        pass

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