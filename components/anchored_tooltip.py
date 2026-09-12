from PyQt6.QtCore import Qt, QPoint
from PyQt6.QtWidgets import QWidget, QVBoxLayout
from PyQt6.QtGui import QPainter, QColor, QPolygon

class AnchoredTooltip(QWidget):
    VALID_POSITIONS = {"up", "down", "left", "right"}

    def __init__(
        self,
        content,
        target=None,
        position="up",
        tooltip_color="#2b2b2b",
        gap=8,
        parent=None,
    ):
        super().__init__(parent)

        if not isinstance(content, QWidget):
            raise TypeError(
                "AnchoredTooltip content must be a QWidget."
            )

        position = position.lower()

        if position not in self.VALID_POSITIONS:
            raise ValueError(
                f"Invalid tooltip position '{position}'. "
                f"Choose from: "
                f"{', '.join(sorted(self.VALID_POSITIONS))}"
            )

        self.content = content
        self.target = target
        self.position = position
        self.tooltip_color = tooltip_color
        self.gap = gap

        self.setWindowFlags(
            Qt.WindowType.ToolTip
            | Qt.WindowType.FramelessWindowHint
        )

        self.setAttribute(
            Qt.WidgetAttribute.WA_TranslucentBackground
        )

        layout = QVBoxLayout(self)

        if self.position == "up":
            layout.setContentsMargins(
                14, # left
                8, # top
                14, # right
                12, # bottom
            )

        elif self.position == "down":
            layout.setContentsMargins(
                14,
                12,
                14,
                1,
            )

        elif self.position == "left":
            layout.setContentsMargins(
                14,
                8,
                18,
                8,
            )

        else:  # right
            layout.setContentsMargins(
                18, # left
                8, # top
                14, # right
                8, # bottom
            )

        layout.setSpacing(0)
        layout.addWidget(self.content)

    def position_relative_to_target(self):
        if self.target is None:
            return

        if not self.target.isVisible():
            return

        target_rect = self.target.rect()

        # --------------------------------------------------------
        # Limit tooltip width to target width
        # --------------------------------------------------------

        # --------------------------------------------------------
        # Determine natural content width
        # --------------------------------------------------------

        available_width = max(
            1,
            self.target.width() - 28
        )

        if hasattr(self.content, "document"):

            document = self.content.document()

            # Remove any previous wrapping constraint.
            document.setTextWidth(-1)

            natural_width = (
                document.documentLayout()
                .documentSize()
                .width()
            )

            content_width = min(
                int(natural_width) + 1,
                available_width
            )

            self.content.update_document_size(
                content_width
            )

        else:

            self.content.adjustSize()

            content_width = min(
                self.content.sizeHint().width(),
                available_width
            )

            self.content.setFixedWidth(
                content_width
            )

        self.adjustSize()

        # --------------------------------------------------------
        # Target geometry in global coordinates
        # --------------------------------------------------------

        top_left = self.target.mapToGlobal(
            target_rect.topLeft()
        )

        bottom_right = self.target.mapToGlobal(
            target_rect.bottomRight()
        )

        target_left = top_left.x()
        target_top = top_left.y()
        target_right = bottom_right.x()
        target_bottom = bottom_right.y()

        target_center_x = (
            target_left + target_right
        ) // 2

        target_center_y = (
            target_top + target_bottom
        ) // 2

        tooltip_width = self.width()
        tooltip_height = self.height()

        # --------------------------------------------------------
        # Position
        # --------------------------------------------------------

        if self.position == "up":

            x = (
                target_center_x
                - tooltip_width // 2
            )

            y = (
                target_top
                - tooltip_height
                - self.gap
            )

        elif self.position == "down":

            x = (
                target_center_x
                - tooltip_width // 2
            )

            y = (
                target_bottom
                + self.gap
            )

        elif self.position == "left":

            x = (
                target_left
                - tooltip_width
                - self.gap
            )

            y = (
                target_center_y
                - tooltip_height // 2
            )

        else:  # right

            x = (
                target_right
                + self.gap
            )

            y = (
                target_center_y
                - tooltip_height // 2
            )

        self.move(x, y)

    def show(self):
        self.position_relative_to_target()

        super().show()

        self.raise_()
        self.activateWindow()

    def paintEvent(self, event):
        painter = QPainter(self)

        painter.setRenderHint(
            QPainter.RenderHint.Antialiasing
        )

        painter.setBrush(
            QColor(self.tooltip_color)
        )

        painter.setPen(
            Qt.PenStyle.NoPen
        )

        arrow_width = 16
        arrow_height = 8

        if self.position == "up":

            body_rect = self.rect().adjusted(
                0,
                0,
                0,
                -arrow_height,
            )

            painter.drawRoundedRect(
                body_rect,
                8,
                8,
            )

            center_x = self.width() // 2

            arrow = QPolygon([
                QPoint(
                    center_x - arrow_width // 2,
                    self.height() - arrow_height,
                ),
                QPoint(
                    center_x,
                    self.height(),
                ),
                QPoint(
                    center_x + arrow_width // 2,
                    self.height() - arrow_height,
                ),
            ])

            painter.drawPolygon(arrow)

        elif self.position == "down":

            body_rect = self.rect().adjusted(
                0,
                arrow_height,
                0,
                0,
            )

            painter.drawRoundedRect(
                body_rect,
                8,
                8,
            )

            center_x = self.width() // 2

            arrow = QPolygon([
                QPoint(
                    center_x - arrow_width // 2,
                    arrow_height,
                ),
                QPoint(
                    center_x,
                    0,
                ),
                QPoint(
                    center_x + arrow_width // 2,
                    arrow_height,
                ),
            ])

            painter.drawPolygon(arrow)

        elif self.position == "left":

            body_rect = self.rect().adjusted(
                0,
                0,
                -arrow_height,
                0,
            )

            painter.drawRoundedRect(
                body_rect,
                8,
                8,
            )

            center_y = self.height() // 2

            arrow = QPolygon([
                QPoint(
                    self.width() - arrow_height,
                    center_y - arrow_width // 2,
                ),
                QPoint(
                    self.width(),
                    center_y,
                ),
                QPoint(
                    self.width() - arrow_height,
                    center_y + arrow_width // 2,
                ),
            ])

            painter.drawPolygon(arrow)

        else:  # right

            body_rect = self.rect().adjusted(
                arrow_height,
                0,
                0,
                0,
            )

            painter.drawRoundedRect(
                body_rect,
                8,
                8,
            )

            center_y = self.height() // 2

            arrow = QPolygon([
                QPoint(
                    arrow_height,
                    center_y - arrow_width // 2,
                ),
                QPoint(
                    0,
                    center_y,
                ),
                QPoint(
                    arrow_height,
                    center_y + arrow_width // 2,
                ),
            ])

            painter.drawPolygon(arrow)

        painter.end()