from PyQt6.QtCore import Qt, QPoint, QEvent, QTimer
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
        gap=4,
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
        self._watched_window = None
        self._requested_visible = False
        self.arrow_width = 16
        self.arrow_height = 8
        self.vertical_margin = 6
        self.horizontal_margin = 10

        self.setWindowFlags(
            Qt.WindowType.ToolTip
            | Qt.WindowType.FramelessWindowHint
        )

        self.setAttribute(
            Qt.WidgetAttribute.WA_TranslucentBackground
        )

        layout = QVBoxLayout(self)

        vertical_margin = self.vertical_margin
        horizontal_margin = self.horizontal_margin
        arrow_height = self.arrow_height

        if self.position == "up":
            layout.setContentsMargins(
                horizontal_margin,
                vertical_margin,
                horizontal_margin,
                vertical_margin + arrow_height,
            )

        elif self.position == "down":
            layout.setContentsMargins(
                horizontal_margin,
                vertical_margin + arrow_height,
                horizontal_margin,
                vertical_margin,
            )

        elif self.position == "left":
            layout.setContentsMargins(
                horizontal_margin,
                vertical_margin,
                horizontal_margin + arrow_height,
                vertical_margin,
            )

        else:  # right
            layout.setContentsMargins(
                horizontal_margin + arrow_height,
                vertical_margin,
                horizontal_margin,
                vertical_margin,
            )
        layout.setSpacing(0)
        layout.addWidget(self.content)

    def _install_window_event_filter(self):
        if self.target is None:
            return

        window = self.target.window()

        if window is not None:
            window.installEventFilter(self)
            self._watched_window = window

    def _remove_window_event_filter(self):
        window = getattr(self, "_watched_window", None)

        if window is not None:
            window.removeEventFilter(self)
            self._watched_window = None

    def eventFilter(self, obj, event):

        if event.type() in (
            QEvent.Type.Move,
            QEvent.Type.Resize,
        ):
            if self.isVisible():
                self.position_relative_to_target()

        elif event.type() in (
            QEvent.Type.ActivationChange,
            QEvent.Type.WindowActivate,
            QEvent.Type.WindowDeactivate,
            QEvent.Type.WindowStateChange,
            QEvent.Type.Hide,
            QEvent.Type.Show,
        ):
            QTimer.singleShot(
                0,
                self._sync_with_watched_window
            )

        return super().eventFilter(obj, event)

    def _sync_with_watched_window(self):
        window = self._watched_window
        if window is None or not self._requested_visible:
            return

        window_visible = (
            window.isVisible()
            and not window.isMinimized()
            and window.isActiveWindow()
        )

        if window_visible:
            super().show()
            self.position_relative_to_target()
            self.raise_()
        else:
            super().hide()

    def position_relative_to_target(self):
        if self.target is None:
            return

        if not self.target.isVisible():
            return

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

        top_left = self.target.mapToGlobal(
            QPoint(0, 0)
        )

        target_left = top_left.x()
        target_top = top_left.y()

        target_right = (
            target_left
            + self.target.width()
        )

        target_bottom = (
            target_top
            + self.target.height()
        )

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

            x = (target_center_x - tooltip_width // 2)
            y = (target_top - tooltip_height - self.gap)

        elif self.position == "down":

            x = (target_center_x - tooltip_width // 2)
            y = (target_bottom + self.gap)

        elif self.position == "left":

            x = (target_left - tooltip_width - self.gap)
            y = (target_center_y - tooltip_height // 2)

        else:  # right

            x = (target_right + self.gap)
            y = (target_center_y - tooltip_height // 2)

        self.move(x, y)

    def show(self):

        self._install_window_event_filter()
        self._requested_visible = True

        super().show()

        self.position_relative_to_target()

        self.raise_()

    def hide(self):
        self._requested_visible = False
        super().hide()

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

        arrow_width = self.arrow_width
        arrow_height = self.arrow_height

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

    def closeEvent(self, event):
        self._remove_window_event_filter()
        super().closeEvent(event)