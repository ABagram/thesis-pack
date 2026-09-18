from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
)

from load_icon import load_icon
from branding import *


class _SidebarButton(QPushButton):
    """Custom button handling dynamic icon recoloring, states, and text expansion."""

    COLLAPSED_SIZE = 36
    EXPANDED_WIDTH = 110
    ICON_SIZE = 18

    def __init__(self, icon_path, text, tooltip, parent=None):
        super().__init__(parent)

        self.icon_path = icon_path
        self.tab_text = text

        self.setCheckable(True)
        self.setFixedSize(self.COLLAPSED_SIZE, self.COLLAPSED_SIZE)
        self.setToolTip(tooltip)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setObjectName("NavigationSidebarButton")

        self.color_normal = text_white_85
        self.color_hover = text_white_85
        self.color_checked = bg_brand_accent

        self._update_icon(self.color_normal)
        self.toggled.connect(self._on_toggled)

        self.setStyleSheet(f"""
            QPushButton#NavigationSidebarButton {{
                background: transparent;
                border: none;
                border-radius: 18px;
                padding: 0px 10px;
                text-align: center;
                color: {text_white_85};
                font-size: 13px;
            }}

            QPushButton#NavigationSidebarButton:hover {{
                background: {bg_white_10};
            }}

            QPushButton#NavigationSidebarButton:checked {{
                background: {bg_white_10};
            }}
        """)

    def _update_icon(self, color):
        self.setIcon(
            QIcon(
                load_icon(
                    self.icon_path,
                    size=self.ICON_SIZE,
                    color=color,
                )
            )
        )
        self.setIconSize(QSize(self.ICON_SIZE, self.ICON_SIZE))

    def expand(self):
        self.setText(f"  {self.tab_text}")
        self.setFixedSize(self.EXPANDED_WIDTH, self.COLLAPSED_SIZE)

        self.setStyleSheet(
            self.styleSheet().replace(
                "text-align: center;",
                "text-align: left;",
            )
        )

    def collapse(self):
        self.setText("")
        self.setFixedSize(
            self.COLLAPSED_SIZE,
            self.COLLAPSED_SIZE,
        )

        self.setStyleSheet(
            self.styleSheet().replace(
                "text-align: left;",
                "text-align: center;",
            )
        )

    def enterEvent(self, event):
        super().enterEvent(event)

        if not self.isChecked():
            self._update_icon(self.color_hover)

    def leaveEvent(self, event):
        super().leaveEvent(event)

        if not self.isChecked():
            self._update_icon(self.color_normal)

    def _on_toggled(self, checked):
        if checked:
            self._update_icon(self.color_checked)
        else:
            self._update_icon(self.color_normal)


class NavigationSidebar(QFrame):
    """Icon-only navigation rail that expands on hover to reveal tab names."""

    view_selected = pyqtSignal(str)

    COLLAPSED_WIDTH = 52
    EXPANDED_WIDTH = 126

    def __init__(self, position="left", parent=None):
        super().__init__(parent)

        position = position.lower()

        if position not in {"left", "right", "top", "bottom"}:
            raise ValueError(
                "position must be one of: left, right, top, bottom"
            )

        self.position = position
        self.is_horizontal = position in {"top", "bottom"}

        self.setObjectName("NavigationSidebar")
        self.setProperty("position", position)

        # Sidebar background only.
        # Do NOT use margin here.
        self.setStyleSheet(f"""
            QFrame#NavigationSidebar {{
                background-color: {bg_brand_dark};
                border-radius: 26px;
            }}
        """)

        layout_type = QHBoxLayout if self.is_horizontal else QVBoxLayout

        self.layout_container = layout_type(self)
        self.layout_container.setContentsMargins(8, 8, 8, 8)
        self.layout_container.setSpacing(8)

        if self.is_horizontal:
            self.layout_container.setAlignment(
                Qt.AlignmentFlag.AlignLeft
                | Qt.AlignmentFlag.AlignVCenter
            )

            self.setFixedHeight(52)

        else:
            self.layout_container.setAlignment(
                Qt.AlignmentFlag.AlignLeft
                | Qt.AlignmentFlag.AlignTop
            )

            self.setFixedWidth(self.COLLAPSED_WIDTH)
            self.setSizePolicy(
                QSizePolicy.Policy.Fixed,
                QSizePolicy.Policy.Fixed,
            )

            self.setFixedWidth(self.COLLAPSED_WIDTH)

        self.button_group = QButtonGroup(self)
        self.button_group.setExclusive(True)
        self.button_group.idClicked.connect(
            self._handle_button_clicked
        )

        self.add_view(
            "network",
            "icons/devices.svg",
            "Check remote systems status",
            "Devices",
        )

        self.add_view(
            "pipeline",
            "icons/order_approve.svg",
            "View order queue and order status",
            "Orders",
        )

        self.add_view(
            "custom",
            "icons/package_2.svg",
            "Define custom box",
            "Custom Box"
        )

        self._buttons["network"].setChecked(True)

    @property
    def _buttons(self):
        if not hasattr(self, "_view_buttons"):
            self._view_buttons = {}

        return self._view_buttons

    def add_view(self, view_id, icon_path, tooltip, label=""):
        button = _SidebarButton(
            icon_path,
            label,
            tooltip,
            self,
        )

        self.button_group.addButton(
            button,
            len(self._buttons),
        )

        self._buttons[view_id] = button
        self.layout_container.addWidget(button)

    def enterEvent(self, event):
        super().enterEvent(event)

        # Only left/right sidebars expand horizontally.
        if not self.is_horizontal:
            self.setFixedWidth(self.EXPANDED_WIDTH)

            for btn in self._buttons.values():
                btn.expand()

    def leaveEvent(self, event):
        super().leaveEvent(event)

        if not self.is_horizontal:
            self.setFixedWidth(self.COLLAPSED_WIDTH)

            for btn in self._buttons.values():
                btn.collapse()

    def _handle_button_clicked(self, button_id):
        view_id = list(self._buttons)[button_id]
        self.view_selected.emit(view_id)
