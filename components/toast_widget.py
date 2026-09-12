import sys
from PyQt6.QtCore import Qt, QTimer, QPoint, QSize
from PyQt6.QtWidgets import (QApplication, QMainWindow, QPushButton, QWidget,
                             QLabel, QHBoxLayout, QVBoxLayout, QFrame)
from PyQt6.QtGui import QIcon
from load_icon import load_icon

class ToastNotification(QWidget):
    def __init__(self, icon_path=None, heading=None, subheading=None, 
                 duration_ms=2500, heading_bg_color=None,
                 subheading_bg_color=None, icon_color="#ffffff",
                 show_dismiss_button=True, heading_text_color="#ffffff",
                 subheading_text_color="#b3b3b3", timeout_duration_ms=None,
                 timeout_condition=None, parent=None):
        super().__init__(parent)
        
        self.setWindowFlags(Qt.WindowType.ToolTip | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        self.has_subheading = bool(subheading)
        self.is_expanded = False
        self.duration_ms = (
            duration_ms
            if timeout_duration_ms is None
            else timeout_duration_ms
        )
        self.timeout_condition = timeout_condition

        # Main top-level layout
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        
        # Main visual container frame
        self.container = QFrame()
        self.container.setObjectName("ToastContainer")
        
        container_layout = QVBoxLayout(self.container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)
        
        # 1. Heading Section (Always visible, icon is permanently aligned here)
        self.heading_frame = QFrame()
        self.heading_frame.setObjectName("HeadingFrame")
        
        heading_style = "border-top-left-radius: 8px; border-top-right-radius: 8px;"
        if heading_bg_color:
            heading_style += f" background-color: {heading_bg_color};"
        self.heading_frame.setStyleSheet(heading_style)
        
        heading_layout = QHBoxLayout(self.heading_frame)
        heading_layout.setContentsMargins(15, 10, 15, 10)
        heading_layout.setSpacing(12)
        
        # Icon
        if icon_path:
            icon_label = QLabel()
            icon_label.setPixmap(
                load_icon(icon_path, size=18, color=icon_color)
            )
            heading_layout.addWidget(icon_label, alignment=Qt.AlignmentFlag.AlignVCenter)
        
        # Heading text
        self.heading_label = QLabel(heading or "Notification")
        self.heading_label.setStyleSheet(
            f"color: {heading_text_color}; font-weight: bold; "
            "font-size: 14px; background: transparent;"
        )
        heading_layout.addWidget(self.heading_label, stretch=1, alignment=Qt.AlignmentFlag.AlignVCenter)
        
        # Expand/Collapse Button (Only added if a subheading exists)
        if self.has_subheading:
            self.expand_btn = QPushButton()
            self.expand_btn.setFixedSize(24, 24)
            self.expand_btn.setIcon(
                QIcon(load_icon("icons/circle_down.svg", size=18,
                                color=subheading_text_color))
            )
            self.expand_btn.setIconSize(QSize(18, 18))
            self.expand_btn.setStyleSheet("""
                QPushButton { background: transparent; color: #b3b3b3; border: none; font-weight: bold; }
                QPushButton:hover { color: #ffffff; }
            """)
            self.expand_btn.clicked.connect(self.toggle_expand)
            heading_layout.addWidget(self.expand_btn, alignment=Qt.AlignmentFlag.AlignVCenter)
        
        if show_dismiss_button:
            self.dismiss_btn = QPushButton()
            self.dismiss_btn.setFixedSize(24, 24)
            self.dismiss_btn.setIcon(
                QIcon(load_icon("icons/close.svg", size=18,
                                color=subheading_text_color))
            )
            self.dismiss_btn.setIconSize(QSize(18, 18))
            self.dismiss_btn.clicked.connect(self.close)
            self.dismiss_btn.setToolTip("Dismiss")
            heading_layout.addWidget(
                self.dismiss_btn,
                alignment=Qt.AlignmentFlag.AlignVCenter
            )
        
        container_layout.addWidget(self.heading_frame)
        
        # 2. Subheading Section (Collapsible)
        if self.has_subheading:
            self.subheading_frame = QFrame()
            self.subheading_frame.setObjectName("SubheadingFrame")
            
            sub_style = "border-bottom-left-radius: 8px; border-bottom-right-radius: 8px;"
            if subheading_bg_color:
                sub_style += f" background-color: {subheading_bg_color};"
            self.subheading_frame.setStyleSheet(sub_style)
            
            subheading_layout = QVBoxLayout(self.subheading_frame)
            subheading_layout.setContentsMargins(15, 0, 15, 12)
            
            self.subheading_label = QLabel(subheading)
            self.subheading_label.setStyleSheet(
                f"color: {subheading_text_color}; font-size: 12px; "
                "background: transparent;"
            )
            self.subheading_label.setWordWrap(True)
            self.subheading_label.setTextFormat(Qt.TextFormat.RichText)
            self.subheading_label.setMaximumWidth(420)
            subheading_layout.addWidget(self.subheading_label)
            
            container_layout.addWidget(self.subheading_frame)
            self.subheading_frame.setVisible(False) # Start collapsed by default
            
        outer_layout.addWidget(self.container)
        
        # Base container stylesheet
        self.setStyleSheet("""
            QFrame#ToastContainer {
                background-color: #2b2b2b;
                border-radius: 8px;
            }
            QLabel {
                font-family: 'Segoe UI', Arial, sans-serif;
            }
        """)
        
        self.adjustSize()
        
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.close)

        self.condition_timer = QTimer(self)
        self.condition_timer.setInterval(500)
        self.condition_timer.timeout.connect(self._check_timeout_condition)

    def _check_timeout_condition(self):
        if self.timeout_condition is not None and not self.timeout_condition():
            self.close()

    def toggle_expand(self):
            if not self.has_subheading:
                return
                
            # Capture the current bottom position before changing state
            current_bottom = self.y() + self.height()
            
            self.is_expanded = not self.is_expanded
            self.subheading_frame.setVisible(self.is_expanded)
            icon_path = "icons/circle_up.svg" if self.is_expanded else "icons/circle_down.svg"
            self.expand_btn.setIcon(
                QIcon(load_icon(icon_path, size=18, color="#b3b3b3"))
            )
            
            # Force layout invalidation and explicit size refresh for translucent window
            self.layout().invalidate()
            self.adjustSize()
            self.resize(self.sizeHint())
            
            # Re-anchor the bottom edge to the exact same screen height coordinate
            new_y = current_bottom - self.height()
            self.move(self.x(), new_y)
            
            # Force the OS window surface to repaint and clear old background remnants
            self.update()
            
            # Pause auto-dismiss timer while expanded so the user can read comfortably
            if self.is_expanded:
                self.timer.stop()
            else:
                if self.duration_ms and self.duration_ms > 0:
                    self.timer.start(self.duration_ms)
    def mousePressEvent(self, event):
        if self.has_subheading and event.button() == Qt.MouseButton.LeftButton:
            self.toggle_expand()
        super().mousePressEvent(event)

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
        
        if self.duration_ms and self.duration_ms > 0 and not self.is_expanded:
            self.timer.start(self.duration_ms)

        if self.timeout_condition is not None:
            self.condition_timer.start()

    def closeEvent(self, event):
        self.timer.stop()
        self.condition_timer.stop()
        super().closeEvent(event)