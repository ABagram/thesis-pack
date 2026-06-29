import sys
from PyQt6.QtCore import Qt, QTimer, QPoint, QSize
from PyQt6.QtWidgets import QApplication, QMainWindow, QPushButton, QWidget, QLabel, QHBoxLayout, QVBoxLayout, QFrame
from PyQt6.QtGui import QIcon, QPixmap

class ToastNotification(QWidget):
    def __init__(self, icon_path=None, heading=None, subheading=None, duration_ms=2500, parent=None):
        super().__init__(parent)
        
        # 1. CRITICAL: Turn translucency back on so the OS window background doesn't clip the corners
        self.setWindowFlags(Qt.WindowType.ToolTip | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # Main top-level layout
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0) # No padding around the container
        
        # 2. Use a QFrame as the actual visual box. QFrame natively respects stylesheets/borders!
        self.container = QFrame()
        self.container.setObjectName("ToastContainer")
        
        # Content Layout inside the frame
        main_layout = QHBoxLayout(self.container)
        main_layout.setContentsMargins(15, 10, 20, 10)
        main_layout.setSpacing(12)
        
        # 1. Handle Icon
        if icon_path:
            icon_label = QLabel()
            pixmap = QPixmap(icon_path)
            if not pixmap.isNull():
                icon_label.setPixmap(pixmap.scaled(24, 24, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
                main_layout.addWidget(icon_label, alignment=Qt.AlignmentFlag.AlignVCenter)
        
        # 2. Handle Text
        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)
        
        has_text = False
        if heading:
            heading_label = QLabel(heading)
            heading_label.setStyleSheet("color: #ffffff; font-weight: bold; font-size: 14px;")
            text_layout.addWidget(heading_label)
            has_text = True
            
        if subheading:
            subheading_label = QLabel(subheading)
            subheading_label.setStyleSheet("color: #b3b3b3; font-size: 12px;")
            text_layout.addWidget(subheading_label)
            has_text = True
            
        if not has_text:
            fallback_label = QLabel("Notification")
            fallback_label.setStyleSheet("color: #ffffff; font-size: 14px;")
            text_layout.addWidget(fallback_label)

        main_layout.addLayout(text_layout)
        
        # Add the styled container to our main layout
        outer_layout.addWidget(self.container)
        
        # 3. Target the QFrame by its object name to style the container correctly
        self.setStyleSheet("""
            QFrame#ToastContainer {
                background-color: #2b2b2b; /* Changed back to dark so white text shows, change to white if needed */
                border: 1px solid #3d3d3d;
                border-radius: 8px;
            }
            QLabel {
                background: transparent;
                font-family: 'Segoe UI', Arial, sans-serif;
            }
        """)
        
        self.adjustSize()
        
        self.duration_ms = duration_ms
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.close)

    def show_toast(self, parent_window):
        screen = QApplication.screenAt(parent_window.geometry().center())
        if not screen:
            screen = QApplication.primaryScreen()
        
        screen_geo = screen.availableGeometry()
        
        margin = 20
        x = screen_geo.x() + screen_geo.width() - self.width() - margin
        y = screen_geo.y() + screen_geo.height() - self.height() - margin
        
        self.move(QPoint(x, y))
        self.show()
        self.timer.start(self.duration_ms)