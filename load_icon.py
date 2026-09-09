from functools import lru_cache
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPainter, QColor, QPixmap
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import QLabel


@lru_cache(maxsize=256)
def _cached_load_icon(path_str: str, size: int, color_str: str | None) -> QPixmap:
    icon_path = Path(path_str)

    if not icon_path.exists():
        raise FileNotFoundError(f"Icon file not found: {path_str}")

    renderer = QSvgRenderer(str(icon_path))

    if not renderer.isValid():
        raise ValueError(f"Invalid SVG icon: {path_str}")

    # Render at 3x resolution for high-DPI displays.
    scale = 3
    render_size = size * scale

    pixmap = QPixmap(render_size, render_size)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

    renderer.render(painter)
    painter.end()

    # Tint after rendering.
    if color_str:
        painter = QPainter(pixmap)
        painter.setCompositionMode(
            QPainter.CompositionMode.CompositionMode_SourceIn
        )
        painter.fillRect(pixmap.rect(), QColor(color_str))
        painter.end()

    # Tell Qt that this is a high-DPI pixmap.
    pixmap.setDevicePixelRatio(scale)

    return pixmap


def load_icon(path, size=20, color=None):
    """Load an SVG icon as a high-DPI QPixmap."""
    if not path:
        return QPixmap()

    path_str = str(path)
    color_str = str(color) if color else None

    return _cached_load_icon(path_str, size, color_str)

def set_label_icon(
    label: QLabel,
    *,
    icon_path=None,
    glyph=None,
    size=20,
    color="#E2E8F0",
    font_family="Material Symbols Rounded",
    fallback_text="?",
):
    """Set either an SVG asset or a Material Symbols fallback glyph on a QLabel.

    Use icon_path when the app has an SVG asset; otherwise pass glyph for the current
    Material Symbols TTF fallback. This keeps the UI ready for SVG migration without
    rewriting every widget later.
    """
    if not isinstance(label, QLabel):
        raise TypeError("set_label_icon expects a QLabel instance")

    label.setText("")
    label.setPixmap(QPixmap())

    if icon_path:
        try:
            label.setPixmap(load_icon(icon_path, size=size, color=color))
            return
        except FileNotFoundError:
            pass

    if glyph:
        label.setText(glyph)
        label.setStyleSheet(
            f"font-family: '{font_family}'; font-size: {size}px; color: {color};"
        )
        return

    label.setText(fallback_text)
    label.setStyleSheet(f"font-size: {size}px; color: {color};")