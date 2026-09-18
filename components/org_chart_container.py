from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QSizePolicy
from PyQt6.QtCore import Qt, QPoint
from PyQt6.QtGui import QPainter, QPen, QColor
from PyQt6 import sip
from branding import *

class OrgChartContainer(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.connections = {}

        self.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Preferred)

        self._main_layout = QVBoxLayout(self)
        self._main_layout.setContentsMargins(20, 20, 20, 20)
        
        self.grid_layout = QGridLayout()
        self.grid_layout.setContentsMargins(0, 0, 0, 0)
        self.grid_layout.setHorizontalSpacing(40)
        self.grid_layout.setVerticalSpacing(40)
        
        self._main_layout.addLayout(self.grid_layout)

    def set_connections(self, connection_dict):
        """Sets all connections at once to prevent repetitive layout teardowns."""
        self.connections = connection_dict
        self._rebuild_layout()

    def _rebuild_layout(self):
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)

        all_children = [c for kids in self.connections.values() for c in kids]
        roots = [p for p in self.connections.keys() if p not in all_children]

        if not roots:
            return

        root = roots[0]
        tier1 = self.connections.get(root, [])
        col_span = max(1, len(tier1))

        # Reset stretch factors and column minimums
        for i in range(col_span):
            self.grid_layout.setColumnStretch(i, 1)
            self.grid_layout.setColumnMinimumWidth(i, 0)

        self.grid_layout.addWidget(root, 0, 0, 1, col_span, Qt.AlignmentFlag.AlignHCenter)

        col_widgets = []
        for i, child in enumerate(tier1):
            self.grid_layout.addWidget(child, 1, i, Qt.AlignmentFlag.AlignHCenter)
            
            tier2_children = self.connections.get(child, [])
            if tier2_children:
                tier2_container = QWidget()
                tier2_layout = QHBoxLayout(tier2_container)
                tier2_layout.setContentsMargins(0, 0, 0, 0)
                tier2_layout.setSpacing(15)
                
                for grandchild in tier2_children:
                    tier2_layout.addWidget(grandchild, alignment=Qt.AlignmentFlag.AlignHCenter)
                
                self.grid_layout.addWidget(tier2_container, 2, i, Qt.AlignmentFlag.AlignHCenter)
                col_widgets.append((child, tier2_container))
            else:
                col_widgets.append((child, None))

        # Calculate maximum column width and equalize all grid columns
        self.adjustSize()
        max_col_w = 0
        for child, t2_cont in col_widgets:
            w = child.sizeHint().width()
            if t2_cont:
                w = max(w, t2_cont.sizeHint().width())
            max_col_w = max(max_col_w, w)

        for i in range(col_span):
            self.grid_layout.setColumnMinimumWidth(i, max_col_w)

        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        if not self.connections:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        pen = QPen(QColor(f"{bg_slate_400}"), 1, Qt.PenStyle.SolidLine)
        painter.setPen(pen)

        for parent_widget, children in self.connections.items():
            if not parent_widget or sip.isdeleted(parent_widget):
                continue

            valid_children = [c for c in children if c and not sip.isdeleted(c)]
            if not valid_children:
                continue

            p_rect = parent_widget.rect()
            parent_bottom_center = parent_widget.mapTo(
                self, QPoint(p_rect.center().x(), p_rect.bottom())
            )

            child_points = []
            for child_widget in valid_children:
                c_rect = child_widget.rect()
                pt = child_widget.mapTo(self, QPoint(c_rect.center().x(), c_rect.top()))
                child_points.append(pt)

            avg_child_y = sum(pt.y() for pt in child_points) // len(child_points)
            mid_y = parent_bottom_center.y() + (avg_child_y - parent_bottom_center.y()) // 2

            # Snap middle child X to parent X for odd child counts
            if len(valid_children) % 2 == 1:
                mid_idx = len(valid_children) // 2
                if abs(child_points[mid_idx].x() - parent_bottom_center.x()) <= 5:
                    child_points[mid_idx].setX(parent_bottom_center.x())

            # 1. Single stem down from parent
            painter.drawLine(parent_bottom_center, QPoint(parent_bottom_center.x(), mid_y))

            # 2. Horizontal bus bar
            min_x = min([pt.x() for pt in child_points] + [parent_bottom_center.x()])
            max_x = max([pt.x() for pt in child_points] + [parent_bottom_center.x()])
            if min_x != max_x:
                painter.drawLine(QPoint(min_x, mid_y), QPoint(max_x, mid_y))

            # 3. Vertical drop lines to each child
            for pt in child_points:
                painter.drawLine(QPoint(pt.x(), mid_y), pt)