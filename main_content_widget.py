import os

from PyQt6.QtCore import QTimer, pyqtSignal
from PyQt6.QtWidgets import QStackedWidget, QVBoxLayout, QWidget

from tabs.custom_box_making_tab import CustomBoxMakingTab
from tabs.device_monitoring_tab import DeviceMonitoringTab
from tabs.order_monitoring_tab import OrderMonitoringTab
from new_order import OrderManager


class MainContentWidget(QWidget):
    hardware_trigger_clicked = pyqtSignal()

    def __init__(self, default_batch_directory=None, order_queue_position="right"):
        super().__init__()
        self.default_batch_directory = default_batch_directory or OrderManager().get_current_batch_directory()
        os.makedirs(self.default_batch_directory, exist_ok=True)

        self.view_stack = QStackedWidget(self)
        self.device_monitoring_tab = DeviceMonitoringTab()
        self.order_monitoring_tab = OrderMonitoringTab(
            self.default_batch_directory, order_queue_position
        )
        self.custom_box_making_tab = CustomBoxMakingTab()
        self.view_stack.addWidget(self.device_monitoring_tab)
        self.view_stack.addWidget(self.order_monitoring_tab)
        self.view_stack.addWidget(self.custom_box_making_tab)

        self.order_queue = self.order_monitoring_tab.order_queue
        self.order_state_updated = self.order_monitoring_tab.order_state_updated
        self.order_state_updated.connect(self._sync_order_widget_state)
        self.device_monitoring_tab.order_created.connect(self._handle_order_created)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(15)
        layout.addWidget(self.view_stack)

        self.scan_timer = QTimer(self)
        self.scan_timer.timeout.connect(self.order_queue.scan_active_subdirectories)
        self.scan_timer.start(1000)

    def _sync_order_widget_state(self, order_id, state_data):
        self.order_queue.sync_order_widget_state(order_id)

    def _handle_order_created(self, order_id, order_path):
        batch_directory = os.path.dirname(order_path)
        self.order_queue.active_main_directory = batch_directory
        self.order_queue.update_path_display(batch_directory)
        self.order_monitoring_tab.handle_order_created(order_id, order_path)
        self.order_queue.scan_active_subdirectories()

    def show_view(self, view_id):
        view_map = {
            "network": self.device_monitoring_tab,
            "pipeline": self.order_monitoring_tab,
            "orders": self.order_monitoring_tab,
            "custom": self.custom_box_making_tab,
        }
        view = view_map.get(view_id)
        if view is not None:
            self.view_stack.setCurrentWidget(view)

    def closeEvent(self, a0):
        self.scan_timer.stop()
        self.device_monitoring_tab.close()
        super().closeEvent(a0)
