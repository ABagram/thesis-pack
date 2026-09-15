from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout
from PyQt6.QtCore import Qt, QPoint
from PyQt6.QtGui import QPainter, QPen, QColor
from branding import *

class OrgChartContainer(QWidget):
    """A container that arranges widgets in a hierarchical tree layout 
    and automatically draws connecting lines between parents and children.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.tiers = [] # List of lists containing widgets per hierarchy level
        self._main_layout = QVBoxLayout(self)
        self._main_layout.setContentsMargins(20, 20, 20, 20)
        self._main_layout.setSpacing(40) # Vertical spacing between hierarchies

    def add_tier(self, widgets):
        """Adds a full horizontal tier of widgets representing a hierarchy level."""
        self.tiers.append(widgets)
        tier_container = QWidget()
        tier_layout = QHBoxLayout(tier_container)
        tier_layout.setContentsMargins(0, 0, 0, 0)
        tier_layout.setSpacing(30) # Horizontal spacing between siblings
        tier_layout.addStretch()
        for w in widgets:
            tier_layout.addWidget(w)
        tier_layout.addStretch()
        
        self._main_layout.addWidget(tier_container)

    def paintEvent(self, event):
        super().paintEvent(event)
        if len(self.tiers) < 2:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        pen = QPen(QColor(f"{bg_slate_400}"), 2, Qt.PenStyle.SolidLine)
        painter.setPen(pen)

        parent_tier = self.tiers[0]
        
        for parent_widget in parent_tier:
            # Map parent geometry coordinates to OrgChartContainer space
            p_top_left = parent_widget.mapTo(self, parent_widget.rect().topLeft())
            p_bottom_right = parent_widget.mapTo(self, parent_widget.rect().bottomRight())
            
            parent_bottom_center = QPoint(
                p_top_left.x() + (p_bottom_right.x() - p_top_left.x()) // 2, 
                p_bottom_right.y()
            )
            
            for child_tier in self.tiers[1:]:
                for child_widget in child_tier:
                    # Map child geometry coordinates to OrgChartContainer space
                    c_top_left = child_widget.mapTo(self, child_widget.rect().topLeft())
                    c_bottom_right = child_widget.mapTo(self, child_widget.rect().bottomRight())
                    
                    child_top_center = QPoint(
                        c_top_left.x() + (c_bottom_right.x() - c_top_left.x()) // 2, 
                        c_top_left.y()
                    )

                    # Draw orthogonal branching tree lines
                    mid_y = parent_bottom_center.y() + (child_top_center.y() - parent_bottom_center.y()) // 2
                    
                    painter.drawLine(parent_bottom_center, QPoint(parent_bottom_center.x(), mid_y))
                    painter.drawLine(QPoint(parent_bottom_center.x(), mid_y), QPoint(child_top_center.x(), mid_y))
                    painter.drawLine(QPoint(child_top_center.x(), mid_y), child_top_center)