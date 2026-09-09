from PyQt6.QtCore import QEvent, QObject, QSize, Qt, QTimer
from PyQt6.QtGui import QFont, QGuiApplication, QIcon, QPixmap
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton
from load_icon import load_icon
from toast_widget import ToastNotification


# 1. Create a tiny helper subclass for the button to cleanly handle hover events
class HoverIconButton(QPushButton):

  def __init__(self, default_pixmap, hover_pixmap, parent=None):
    super().__init__(parent)
    self.default_pixmap = default_pixmap
    self.hover_pixmap = hover_pixmap

  def enterEvent(self, event):
    # Check the parent widget's state instead of the top-level window
    if self.parent() and self.parent().property("state") == "default":
      self.setIcon(QIcon(self.hover_pixmap))
    super().enterEvent(event)

  def leaveEvent(self, event):
    if self.parent() and self.parent().property("state") == "default":
      self.setIcon(QIcon(self.default_pixmap))
    super().leaveEvent(event)

class CopyStringWidget(QFrame):

  def __init__(self, text_content="", parent=None):
    super().__init__(parent)
    self.text_content = text_content

    self.reset_timer = QTimer(self)
    self.reset_timer.setSingleShot(True)
    self.reset_timer.timeout.connect(self.reset_feedback_visuals)

    self.toast = ToastNotification(
        subheading="Copied to clipboard!", duration_ms=1500
    )

    # Preload pixmaps
    self.default_pixmap = load_icon(
        "icons/content_copy.svg", size=14, color="#166534"
    )
    self.hover_pixmap = load_icon(
        "icons/content_copy.svg", size=14, color="#16A34A"
    )
    self.success_pixmap = load_icon(
        "icons/check_circle.svg", size=14, color="#166534"
    )

    self.init_ui()

  def init_ui(self):
    layout = QHBoxLayout(self)
    layout.setContentsMargins(6, 4, 6, 4)
    layout.setSpacing(8)

    self.setToolTip("Copy to clipboard")

    self.text_label = QLabel(self.text_content)
    self.text_label.setStyleSheet(
        "background: transparent; border: none; color: #166534; font-size: 12px"
    )
    self.text_label.setFont(QFont("Poppins", 12))
    layout.addWidget(self.text_label)

    layout.addStretch()

    # 2. Use the clean HoverIconButton subclass here
    self.icon_button = HoverIconButton(
        self.default_pixmap, self.hover_pixmap
    )
    self.icon_button.setObjectName("CopyStringIconButton")
    self.icon_button.setIcon(QIcon(self.default_pixmap))
    self.icon_button.setIconSize(QSize(14, 14))
    self.icon_button.setCursor(Qt.CursorShape.PointingHandCursor)
    self.icon_button.setToolTip("Copy to clipboard")
    self.icon_button.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                padding: 0;
                text-align: center;
            }
            QPushButton:hover {
                border-radius: 3px;
            }
        """)
    layout.addWidget(self.icon_button)

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
            CopyStringWidget[state="success"] {
                background-color: #0d166534;
                color: #80166534;    
                border: 1px solid #80166534;
            }
        """)

    self.setProperty("state", "default")
    self.icon_button.clicked.connect(self.copy_to_clipboard)

  def update_text(self, new_text):
    self.text_content = new_text
    self.text_label.setText(new_text)

  def copy_to_clipboard(self):
    if self.text_content and self.text_content not in ["No Wi-Fi", "Unavailable"]:
      clipboard = QGuiApplication.clipboard()
      clipboard.setText(self.text_content)

      self.icon_button.setIcon(QIcon(self.success_pixmap))

      self.setProperty("state", "success")
      self.style().unpolish(self)
      self.style().polish(self)

      self.toast.show_toast(self.window())
      self.reset_timer.start(1500)

  def reset_feedback_visuals(self):
    self.text_label.setText(self.text_content)
    self.icon_button.setIcon(QIcon(self.default_pixmap))

    self.setProperty("state", "default")
    self.style().unpolish(self)
    self.style().polish(self)

  def mousePressEvent(self, event):
    if event.button() == Qt.MouseButton.LeftButton:
      self.copy_to_clipboard()
      super().mousePressEvent(event)