from PyQt6.QtWidgets import QWidget, QFrame, QHBoxLayout, QVBoxLayout, QLabel, QPushButton, QToolTip
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QObject, QThread, QRect
from PyQt6.QtGui import QFont, QIcon, QPixmap
from PyQt6 import sip
from typing import Any, cast
import qtawesome, qtmdi
import requests, time
from load_icon import load_icon
from read_pc_ssid import read_pc_ssid
from wifi_provision_manager import WifiProvisionManager

class WifiSetupOverlay(QWidget):
    setup_completed = pyqtSignal(bool)
    step_changed = pyqtSignal(int)

    def __init__(self, temp_ssid, temp_pw, target_ssid, target_pw, system_name):
        
        print("OVERLAY CREATED")
        
        super().__init__()

        self.temp_ssid = temp_ssid
        self.temp_pw = temp_pw
        self.target_ssid = target_ssid
        self.target_pw = target_pw
        self.system_name = system_name
        
        self.steps = [
                        (
                            f'Scanning for '
                            f'<span style="color:#166534; font-weight:600;">'
                            f'{temp_ssid}</span>'
                        ),

                        "Automatically entering password",

                        (
                            f'Connecting to PC to detect '
                            f'<span style="color:#2563EB; font-weight:600;">'
                            f'{target_ssid}</span>'
                        ),

                        (
                            f'Send '
                            f'<span style="color:#2563EB; font-weight:600;">'
                            f'{target_ssid}</span>'
                            f' and password to {system_name}'
                        ),

                        (
                            f'Reconnecting PC back to '
                            f'<span style="color:#2563EB; font-weight:600;">'
                            f'{target_ssid}</span>'
                        )
                    ]
        
        self.current_step = 0
        self.step_labels = []
        
        self.init_ui()
        
        # Set up thread architecture safely
        self.provision_thread = QThread()
        self.worker = WifiProvisionManager(
            self.temp_ssid, self.temp_pw, self.target_ssid, self.target_pw
        )
        self.worker.moveToThread(self.provision_thread)
        
        # Hook up asynchronous signals
        self.provision_thread.started.connect(self.worker.run)
        
        self.worker.step_changed.connect(self.update_step)
        self.worker.finished.connect(self.handle_worker_finished)
        
        # Cleanup links to prevent memory leaks
        self.worker.finished.connect(self.provision_thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.provision_thread.finished.connect(self.provision_thread.deleteLater)
        
        # Start execution flow safely off-thread after a short ui stabilization frame
        print("Starting thread...")
        QTimer.singleShot(300, self.provision_thread.start)

    def init_ui(self):
        # Fill whole parent viewport
        parent = self.parentWidget()
        if parent is not None:
            self.setFixedWidth(parent.width())
            # ``badge`` is supplied by the overlay's parent widget, rather
            # than being part of QWidget's public interface.
            badge = getattr(cast(Any, parent), "badge", None)
            badge_height = badge.height() if badge is not None else 0
            self.move(0, badge_height)
                                
        self.setStyleSheet("background-color: rgba(15, 23, 42, 0.85);") # Tailwind slate-900 transparent fallback
        
        main_layout = QVBoxLayout(self)
        main_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        card = QFrame()
        card.setFixedWidth(450)
        card.setStyleSheet("background-color: white; border-radius: 12px; padding: 10px;")
        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(14)
        
        title = QLabel(f"Configuring Wi-Fi for {self.system_name}")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #0F172A; padding-bottom: 8px;")
        card_layout.addWidget(title)
        
        # Build out Step Progress UI
        for step_text in self.steps:
            step_row = QHBoxLayout()
            
            # Step indicator icon
            indicator = QLabel("⚪") # Pending
            indicator.setStyleSheet("font-size: 12px;")
            
            label = QLabel(step_text)
            label.setStyleSheet("font-size: 13px; color: #94A3B8;") # Muted gray color
            label.setWordWrap(True)
            
            step_row.addWidget(indicator)
            step_row.addWidget(label, 1)
            card_layout.addLayout(step_row)
            
            self.step_labels.append((indicator, label))
            
        main_layout.addWidget(card)
        self.update_progress_ui()

    def update_progress_ui(self):
        for i, (indicator, label) in enumerate(self.step_labels):
            if i < self.current_step:
                indicator.setText("\ue86c")
                label.setStyleSheet("font-size: 13px; color: #16A34A; font-weight: bold;") # Completed Green
            elif i == self.current_step:
                indicator.setText("⏳")
                label.setStyleSheet("font-size: 13px; color: #2563EB; font-weight: bold;") # Active Blue
            else:
                indicator.setText("⚪")
                label.setStyleSheet("font-size: 13px; color: #94A3B8;") # Locked Gray

    def update_step(self, step):
        self.current_step = step
        self.update_progress_ui()
    
    def handle_worker_finished(self, success):
        self.setup_completed.emit(success)
        self.close()