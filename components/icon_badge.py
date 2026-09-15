from load_icon import load_icon
from PyQt6.QtWidgets import QWidget, QFrame, QLabel, QHBoxLayout
from PyQt6.QtCore import Qt

class IconBadge(QWidget):
    def __init__(
        self,
        icon_path: str,
        icon_size: int = 16,
        icon_color: str = "#ffffff",
        badge_color: str = "#2d2d2d",
        badge_border_width: int = 0,
        badge_border_color: str | None = None,
        shape: str = "square",
    ):
        super().__init__()
        self.icon_path = icon_path
        self.icon_size = icon_size
        self.icon_color = icon_color
        self.badge_color = badge_color
        self.badge_border_width = badge_border_width
        self.badge_border_color = badge_border_color
        self.shape = shape.lower()
        
        self.init_ui()

    def init_ui(self):
        badge_size = int(self.icon_size * 2.5)
        
        if self.shape == "circle":
            border_radius = int(badge_size / 2)
        else:
            border_radius = int(self.icon_size * 0.5)

        self.badge = QFrame(self)
        self.badge.setObjectName("BadgeFrame")
        self.badge.setFixedSize(badge_size, badge_size)
        
        self.badge.setStyleSheet(f"""
            QFrame#BadgeFrame {{
                background-color: {self.badge_color};
                border: {self.badge_border_width}px solid {self.badge_border_color};
                border-radius: {border_radius}px;
            }}
        """)

        self.icon_label = QLabel()
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_label.setPixmap(
            load_icon(
                path=self.icon_path,
                size=self.icon_size,
                color=self.icon_color
            )
        )

        badge_layout = QHBoxLayout(self.badge)
        badge_layout.setContentsMargins(0, 0, 0, 0)
        badge_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge_layout.addWidget(self.icon_label)

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(self.badge)

    def update_badge(
        self,
        icon_path: str,
        icon_color: str,
        badge_color: str,
        badge_border_color: str | None = None,
    ):
        self.icon_path = icon_path
        self.icon_color = icon_color
        self.badge_color = badge_color
        self.badge_border_color = badge_border_color

        badge_size = int(self.icon_size * 2.5)
        border_radius = (
            int(badge_size / 2)
            if self.shape == "circle"
            else int(self.icon_size * 0.5)
        )

        self.badge.setStyleSheet(f"""
            QFrame#BadgeFrame {{
                background-color: {self.badge_color};
                border: {self.badge_border_width}px solid {self.badge_border_color};
                border-radius: {border_radius}px;
            }}
        """)

        self.icon_label.setPixmap(
            load_icon(
                path=self.icon_path, size=self.icon_size, color=self.icon_color
            )
        )