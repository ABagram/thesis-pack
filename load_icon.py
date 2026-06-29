from PyQt6.QtGui import QIcon, QPainter, QColor

def load_icon(path, size=14, color=None):
    """Load icon for QLabel
    Example: self.connect_status.setPixmap(load_icon(ICON_OFFLINE, color="#DC2626"))"""
    
    icon = QIcon(path)
    pixmap = icon.pixmap(size, size)

    if color:
        painter = QPainter(pixmap)
        painter.setCompositionMode(
            QPainter.CompositionMode.CompositionMode_SourceIn
        )
        painter.fillRect(
            pixmap.rect(),
            QColor(color)
        )
        painter.end()

    return pixmap