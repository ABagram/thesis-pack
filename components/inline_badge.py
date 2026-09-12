from PyQt6.QtCore import Qt, QSize, QSizeF, QObject, QRectF
from PyQt6.QtWidgets import QTextEdit, QSizePolicy
from PyQt6.QtGui import QPainter, QColor, QFont, QPen, QTextCharFormat, QTextCursor, QTextDocument, QTextFormat, QTextObjectInterface, QFontMetrics, QPixmap
from load_icon import load_icon

INLINE_BADGE_OBJECT_TYPE = QTextFormat.ObjectTypes.UserObject
INLINE_BADGE_PROPERTY = QTextFormat.Property.UserProperty
INLINE_BADGE_WITH_ICON_OBJECT_TYPE = (
    QTextFormat.ObjectTypes.UserObject + 1
)

INLINE_BADGE_WITH_ICON_TEXT_PROPERTY = 0x100001
INLINE_BADGE_WITH_ICON_PATH_PROPERTY = 0x100002

class InlineBadgeParagraphWrapper(QTextEdit):
    def __init__(
        self,
        parent=None,
        text_font_family="Segoe UI",
        text_font_size=12,
        text_font_color="#ffffff",
        badge_font_family="Consolas",
        badge_font_color="#64748B",
        badge_bg_color="#ffffff",
        badge_horizontal_padding=5,
        badge_vertical_padding=2,
        badge_border_radius=6,
        badge_border_width=1,
        badge_border_color="#e2e8f0",
        badge_border_style=Qt.PenStyle.SolidLine,
        badge_icon_color="#64748B",
        ):
        super().__init__(parent)

        self.text_font_family = text_font_family
        self.text_font_size = text_font_size
        self.text_font_color = text_font_color
        self.badge_icon_color = badge_icon_color

        self.setReadOnly(True)
        self.setFrameShape(QTextEdit.Shape.NoFrame)

        self.setMinimumSize(0, 0)
        self.setSizePolicy(
            QSizePolicy.Policy.Fixed,
            QSizePolicy.Policy.Fixed,
        )

        self.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

        self.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

        self.setContentsMargins(0, 0, 0, 0)

        self.document().setDocumentMargin(0)

        self.setStyleSheet("""
            QTextEdit {
                background: transparent;
                border: none;
                padding: 0px;
            }
        """)

        text_font = QFont(
            self.text_font_family
        )

        text_font.setPixelSize(
            self.text_font_size
        )

        self.setFont(text_font)
        self.cursor = QTextCursor(self.document())

        badge_font_size = max(
            1,
            self.text_font_size - 3
        )

        self.badge_renderer = InlineBadgeRenderer(
            font_family=badge_font_family,
            font_size=badge_font_size,
            font_color=badge_font_color,
            background_color=badge_bg_color,
            horizontal_padding=badge_horizontal_padding,
            vertical_padding=badge_vertical_padding,
            border_radius=badge_border_radius,
            border_width=badge_border_width,
            border_color=badge_border_color,
            border_style=badge_border_style,
        )

        self.badge_with_icon_renderer = InlineBadgeWithIconRenderer(
            font_family=badge_font_family,
            font_size=badge_font_size,
            font_color=badge_font_color,
            background_color=badge_bg_color,
            horizontal_padding=badge_horizontal_padding,
            vertical_padding=badge_vertical_padding,
            border_radius=badge_border_radius,
            border_width=badge_border_width,
            border_color=badge_border_color,
            border_style=badge_border_style,
            icon_color=badge_icon_color,
        )

        self.document().documentLayout().registerHandler(
            INLINE_BADGE_OBJECT_TYPE,
            self.badge_renderer,
        )

        self.document().documentLayout().registerHandler(
            INLINE_BADGE_WITH_ICON_OBJECT_TYPE,
            self.badge_with_icon_renderer,
        )

    def insert_badge(self, text):

        format = QTextCharFormat()

        format.setObjectType(
            INLINE_BADGE_OBJECT_TYPE
        )

        format.setVerticalAlignment(QTextCharFormat.VerticalAlignment.AlignMiddle)

        format.setProperty(
            INLINE_BADGE_PROPERTY,
            text,
        )

        self.cursor.insertText(
            "\uFFFC",
            format,
        )
        
    def insert_badge_with_icon(
        self,
        text,
        icon_path,
    ):
        format = QTextCharFormat()

        format.setObjectType(
            INLINE_BADGE_WITH_ICON_OBJECT_TYPE
        )

        format.setVerticalAlignment(QTextCharFormat.VerticalAlignment.AlignMiddle)
        

        format.setProperty(
            INLINE_BADGE_WITH_ICON_TEXT_PROPERTY,
            str(text),
        )

        format.setProperty(
            INLINE_BADGE_WITH_ICON_PATH_PROPERTY,
            str(icon_path),
        )

        self.cursor.insertText(
            "\uFFFC",
            format,
        )
        
    def insert_text(self, text):

        text_format = QTextCharFormat()

        font = QFont(
            self.text_font_family
        )

        font.setPixelSize(
            self.text_font_size
        )

        text_format.setFont(
            font
        )

        text_format.setForeground(
            QColor(self.text_font_color)
        )

        self.cursor.insertText(
            text,
            text_format,
        )

    def insert_block(self):

        self.cursor.insertBlock()
        
    def sizeHint(self):

        document_size = (
            self.document()
            .documentLayout()
            .documentSize()
        )

        return QSize(
            int(document_size.width()) + 1,
            int(document_size.height()) + 1,
        )

    def update_document_size(self, width):
        width = max(1, width)

        self.document().setTextWidth(width)

        document_height = (
            self.document()
            .documentLayout()
            .documentSize()
            .height()
        )

        self.setFixedSize(
            width,
            int(document_height) + 2,
        )

class InlineBadgeRenderer(QObject, QTextObjectInterface):
    def __init__(
        self,
        font_family="Consolas",
        font_size=10,
        font_color="#ffffff",
        background_color="#ffffff",
        horizontal_padding=5,
        vertical_padding=2,
        border_radius=6,
        border_width=1,
        border_color="#e2e8f0",
        border_style=Qt.PenStyle.SolidLine,
        parent=None,
    ):
        super().__init__(parent)

        self.font_family = font_family
        self.font_size = font_size
        self.font_color = font_color
        self.background_color = background_color
        self.horizontal_padding = horizontal_padding
        self.vertical_padding = vertical_padding
        self.border_radius = border_radius
        self.border_width = border_width
        self.border_color = border_color
        self.border_style = border_style

    def intrinsicSize(self, document, pos_in_document, format):
        badge_text = format.property(INLINE_BADGE_PROPERTY)

        if badge_text is None:
            badge_text = ""

        badge_text = str(badge_text)

        font = QFont(self.font_family)
        font.setPixelSize(self.font_size)

        metrics = QFontMetrics(font)

        badge_height = (
                    metrics.height()
                    + self.vertical_padding * 2
                )

        width = (
            metrics.horizontalAdvance(badge_text)
            + self.horizontal_padding * 2
        )

        height = (
            metrics.height()
            + self.vertical_padding * 2
        )

        return QSizeF(float(width), float(height))

    def drawObject(self, painter, rect, document, pos_in_document, format):
        badge_text = format.property(INLINE_BADGE_PROPERTY)

        if badge_text is None:
            badge_text = ""

        badge_text = str(badge_text)

        painter.save()

        painter.setRenderHint(
            QPainter.RenderHint.Antialiasing
        )

        # Background
        if self.border_width > 0:
            pen = QPen(
                QColor(self.border_color),
                self.border_width,
                self.border_style,
            )
        else:
            pen = QPen(Qt.PenStyle.NoPen)

        painter.setPen(pen)
        painter.setBrush(QColor(self.background_color))
        painter.drawRoundedRect(
            rect,
            self.border_radius,
            self.border_radius,
        )

        # Text
        font = QFont(self.font_family)
        font.setPixelSize(self.font_size)

        painter.setFont(font)
        painter.setPen(QColor(self.font_color))

        painter.drawText(
            rect,
            Qt.AlignmentFlag.AlignCenter,
            badge_text,
        )

        painter.restore()

class InlineBadgeWithIconRenderer(QObject, QTextObjectInterface):
    def __init__(
        self,
        font_family="Consolas",
        font_size=10,
        font_color="#ffffff",
        background_color="#ffffff",
        horizontal_padding=5,
        vertical_padding=2,
        border_radius=6,
        border_width=1,
        border_color="#e2e8f0",
        border_style=Qt.PenStyle.SolidLine,
        icon_size=10,
        icon_spacing=4,
        icon_color="#64748B",
        parent=None,
    ):
        super().__init__(parent)

        self.font_family = font_family
        self.font_size = font_size
        self.font_color = font_color
        self.background_color = background_color
        self.horizontal_padding = horizontal_padding
        self.vertical_padding = vertical_padding
        self.border_radius = border_radius
        self.border_width = border_width
        self.border_color = border_color
        self.border_style = border_style
        self.icon_size = icon_size
        self.icon_spacing = icon_spacing
        self.icon_color = icon_color

    def intrinsicSize(
        self,
        document,
        pos_in_document,
        format,
    ):
        badge_text = format.property(
            INLINE_BADGE_WITH_ICON_TEXT_PROPERTY
        )

        icon_path = format.property(
            INLINE_BADGE_WITH_ICON_PATH_PROPERTY
        )

        if badge_text is None:
            badge_text = ""

        if icon_path is None:
            icon_path = ""

        badge_text = str(badge_text)
        icon_path = str(icon_path)

        font = QFont(self.font_family)
        font.setPixelSize(self.font_size)

        metrics = QFontMetrics(font)

        text_width = metrics.horizontalAdvance(
            badge_text
        )

        icon_width = 0
        spacing = 0

        if icon_path:
            icon_width = self.icon_size
            spacing = self.icon_spacing

        width = (
            text_width
            + icon_width
            + spacing
            + self.horizontal_padding * 2
        )

        height = max(
            metrics.height(),
            self.icon_size,
        ) + self.vertical_padding * 2

        return QSizeF(
            float(width),
            float(height),
        )

    def drawObject(
        self,
        painter,
        rect,
        document,
        pos_in_document,
        format,
    ):
        badge_text = format.property(
            INLINE_BADGE_WITH_ICON_TEXT_PROPERTY
        )

        icon_path = format.property(
            INLINE_BADGE_WITH_ICON_PATH_PROPERTY
        )

        if badge_text is None:
            badge_text = ""

        if icon_path is None:
            icon_path = ""

        badge_text = str(badge_text)
        icon_path = str(icon_path)

        painter.save()

        painter.setRenderHint(
            QPainter.RenderHint.Antialiasing
        )
        painter.setRenderHint(
            QPainter.RenderHint.SmoothPixmapTransform
        )

        # Badge background
        if self.border_width > 0:
            pen = QPen(
                QColor(self.border_color),
                self.border_width,
                self.border_style,
            )
        else:
            pen = QPen(Qt.PenStyle.NoPen)

        painter.setPen(pen)
        painter.setBrush(QColor(self.background_color))

        painter.drawRoundedRect(
            rect,
            self.border_radius,
            self.border_radius,
        )

        # Text font
        font = QFont(self.font_family)
        font.setPixelSize(self.font_size)
        painter.setFont(font)
        painter.setPen(
            QColor(self.font_color)
        )

        metrics = QFontMetrics(font)

        text_width = metrics.horizontalAdvance(
            badge_text
        )

        # Load icon
        icon_pixmap = QPixmap()

        if icon_path:
            try:
                icon_pixmap = load_icon(
                    icon_path,
                    size=self.icon_size,
                    color=self.icon_color,
                )
            except (
                FileNotFoundError,
                ValueError,
            ):
                icon_pixmap = QPixmap()

        has_icon = not icon_pixmap.isNull()

        # Calculate content width
        icon_width = (
            self.icon_size
            if has_icon
            else 0
        )

        spacing = (
            self.icon_spacing
            if has_icon
            else 0
        )

        content_width = (
            icon_width
            + spacing
            + text_width
        )

        content_left = (
            rect.left()
            + (
                rect.width()
                - content_width
            ) / 2
        )

        # Vertically center icon
        if has_icon:
            icon_rect = QRectF(
                content_left,
                rect.top()
                + (
                    rect.height()
                    - self.icon_size
                ) / 2,
                self.icon_size,
                self.icon_size,
            )

            painter.drawPixmap(
                icon_rect,
                icon_pixmap,
                QRectF(
                    icon_pixmap.rect()
                ),
            )

        # Draw text
        text_left = (
            content_left
            + icon_width
            + spacing
        )

        text_rect = QRectF(
            text_left,
            rect.top(),
            text_width,
            rect.height(),
        )

        painter.drawText(
            text_rect,
            Qt.AlignmentFlag.AlignVCenter
            | Qt.AlignmentFlag.AlignLeft,
            badge_text,
        )

        painter.restore()