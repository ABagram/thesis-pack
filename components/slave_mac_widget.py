from PyQt6.QtWidgets import QWidget, QFrame, QHBoxLayout, QVBoxLayout, QLabel, QPushButton, QToolTip, QGridLayout, QSizePolicy
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QRect
from PyQt6.QtGui import QFont, QIcon, QPixmap
from PyQt6 import sip
from load_icon import load_icon
from read_pc_ssid import read_pc_ssid
from wifi_setup_overlay import WifiSetupOverlay
from wifi_credential_manager import WifiCredentialManager
from components.icon_badge import IconBadge
from branding import *

STATUS_ICON_SIZE = 14

class SlaveMacWidget(QWidget):

    def __init__(
        self,
        system_name: str,
        axis: str,
        mac_address=None,
        parent=None
    ):
        super().__init__(parent)
        
        self.system_name = system_name
        self.axis = axis
        self._mac_address_val = mac_address

        self.setSizePolicy(
            QSizePolicy.Policy.Preferred, 
            QSizePolicy.Policy.Maximum
        )
                
        self.init_ui()

    def init_ui(self):
        root_layout = QVBoxLayout(self)  # Fixed: changed from QGridLayout to QVBoxLayout
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        self.status_widget = QFrame(self)
        self.status_widget.setObjectName("WifiStatusWidget")
        root_layout.addWidget(self.status_widget)

        badge_layout = QVBoxLayout(self.status_widget)
        badge_layout.setContentsMargins(8, 6, 8, 6)
        badge_layout.setSpacing(6)

        top_row = QHBoxLayout()
        top_row.setAlignment(Qt.AlignmentFlag.AlignLeft)

        self.system_name_label = QLabel()
        self.system_name_label.setText(f'<p style="line-height: 80%; width: 30px">{self.system_name}</p>')
        self.system_name_label.setWordWrap(True)
        self.system_name_label.setObjectName("SystemName")

        self.icon_badge = QLabel()
        self.icon_badge.setObjectName("SlaveAxisBadge")

        top_row.addWidget(self.system_name_label)
        top_row.addStretch()
        top_row.addWidget(self.icon_badge)

        bottom_row = QVBoxLayout()
        bottom_row.setAlignment(Qt.AlignmentFlag.AlignLeft)

        mac_address_title = QLabel("MAC:")
        mac_address_title.setStyleSheet(f"""
                font-size: 10px;
                color: {text_slate_600};
            """)
        self.mac_address_label = QLabel(self._mac_address_val or "N/A")
        self.mac_address_label.setStyleSheet("font-size: 10px; font-family: Consolas")
        
        # Nest the QGridLayout inside the bottom vertical layout
        self.device_details_layout = QGridLayout()
        self.device_details_layout.addWidget(mac_address_title, 0, 0)
        self.device_details_layout.addWidget(self.mac_address_label, 0, 1)

        bottom_row.addLayout(self.device_details_layout)

        # Add rows to badge
        badge_layout.addLayout(top_row)
        badge_layout.addLayout(bottom_row)
