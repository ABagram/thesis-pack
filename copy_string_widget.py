from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton
from PyQt6.QtGui import QFont, QGuiApplication
from PyQt6.QtCore import Qt, QTimer
from toast_widget import ToastNotification

class CopyStringWidget(QFrame):
    def __init__(self, text_content="", parent=None):
        super().__init__(parent)
        self.text_content = text_content
        
        self.reset_timer = QTimer(self)
        self.reset_timer.setSingleShot(True)
        self.reset_timer.timeout.connect(self.reset_feedback_visuals)

        # Optimization 1: Instantiate the toast ONCE. Reuse it infinitely.
        self.toast = ToastNotification(subheading="Copied to clipboard!", duration_ms=1500)

        self.init_ui()

    def init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(8)

        self.setToolTip("Copy to clipboard")
        
        self.text_label = QLabel(self.text_content)
        self.text_label.setStyleSheet("background: transparent; border: none; color: #166534; font-size: 12px")
        self.text_label.setFont(QFont("Poppins", 12))
        layout.addWidget(self.text_label)

        self.icon_button = QPushButton("\ue14d")
        self.icon_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.icon_button.setToolTip("Copy to clipboard")
        self.icon_button.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                color: #166534;
                font-family: "Material Symbols Rounded";
                text-align: right;
            }
            QPushButton:hover {
                color: #80166534;
            }
        """)
        layout.addWidget(self.icon_button)

        # Optimization 2: Set up a single base stylesheet using dynamic properties ([state="success"])
        self.setStyleSheet("""
            CopyStringWidget {
                background-color: #0d166534;
                color: #166534;
                border: 1px solid #1a166534;
                border-radius: 5px;
            }
            CopyStringWidget:hover {
                border-color: #166534;
            }
            /* High-performance visual state switch */
            CopyStringWidget[state="success"] {
                background-color: #0d166534;
                color: #80166534;    
                border: 1px solid #80166534;
            }
        """)
        
        # Set the initial default property state
        self.setProperty("state", "default")
        self.icon_button.clicked.connect(self.copy_to_clipboard)

    def update_text(self, new_text):
        self.text_content = new_text
        self.text_label.setText(new_text)

    def copy_to_clipboard(self):
        if self.text_content and self.text_content not in ["No Wi-Fi", "Unavailable"]:
            # Clipboard operation (Instant)
            clipboard = QGuiApplication.clipboard()
            clipboard.setText(self.text_content)
        
            self.icon_button.setText("\ue86c") # check_circle
            
            # Optimization 3: Change properties smoothly instead of rewriting style blocks
            self.setProperty("state", "success")
            self.style().unpolish(self)  # Forces Qt to quickly refresh stylesheet matching rules
            self.style().polish(self)
            
            # Fire the cached toast instantly
            self.toast.show_toast(self.window())
            self.reset_timer.start(1500)

    def reset_feedback_visuals(self):
        self.text_label.setText(self.text_content)
        self.icon_button.setText("\ue14d")
        
        # Snap back to default property state instantly
        self.setProperty("state", "default")
        self.style().unpolish(self)
        self.style().polish(self)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.copy_to_clipboard()
            super().mousePressEvent(event)