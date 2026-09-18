import re
import subprocess

from PyQt6.QtCore import QTimer, pyqtSignal
from PyQt6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from branding import *
from components.anchored_tooltip import AnchoredTooltip
from components.inline_badge import InlineBadgeParagraphWrapper
from components.org_chart_container import OrgChartContainer
from components.slave_mac_widget import SlaveMacWidget
from esp_wifi_guidance import show_esp_wifi_guidance
from load_icon import load_icon
from new_order import OrderManager
from wifi_credential_manager import WifiCredentialManager
from wifi_network_monitor import WifiNetworkMonitor
from wifi_status_widget import WifiStatusWidget
from wifi_udp_listener import WifiUdpListener


class DeviceMonitoringTab(QWidget):
    order_created = pyqtSignal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_wifi_band = "Unknown"
        self.current_wifi_is_5ghz = False
        self.current_ssid = None
        self.wifi_band_tooltip = None
        self._build_ui()
        self._start_services()

    def _build_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        device_page_frame = QFrame()
        root_layout.addWidget(device_page_frame)
        network_main_layout = QHBoxLayout(device_page_frame)
        network_main_layout.setContentsMargins(12, 10, 12, 10)
        network_main_layout.setSpacing(20)

        credentials_widget = QWidget()
        credentials_layout = QGridLayout(credentials_widget)
        credentials_layout.setContentsMargins(0, 0, 0, 0)
        credentials_layout.setHorizontalSpacing(8)
        credentials_layout.setVerticalSpacing(6)
        self.ssid_icon = QLabel()
        self.ssid_icon.setPixmap(load_icon(ICON_WIFI, size=14, color="#64748b"))
        self.ssid_label = QLabel("SSID:")
        self.ssid_label.setStyleSheet("font-weight: bold; color: #475569; font-size: 12px")

        wifi_ssid = self.get_connected_ssid()
        wifi_pw = self.get_wifi_password(wifi_ssid) if wifi_ssid != "No Wi-Fi" else "Unavailable"
        hierarchy = OrgChartContainer()
        self.pc_widget = WifiStatusWidget(
            system_name="This PC", icon_path=ICON_PC, ap_ssid=None, temp_pw=None,
            target_ssid=wifi_ssid, target_pw=wifi_pw, is_esp=False
        )
        self.oss_master_status_widget = WifiStatusWidget(
            system_name="Order Scanning Station", icon_path=ICON_CAMERA, temp_pw="SST@2002",
            target_ssid=wifi_ssid, target_pw=wifi_pw, device_host="OSS-MASTER",
            ap_ssid="OSS_MASTER_SETUP_AP", mac_address="68:09:47:37:81:24",
            udp_device_id="oss-master",
            disabled_tooltip="Camera captive portal setup broadcast cannot be found near laptop."
        )
        self.oss_slave_x_widget = SlaveMacWidget(
            system_name="Back Camera", axis="X", mac_address="c0:4e:30:2f:28:94"
        )
        self.oss_slave_y_widget = SlaveMacWidget(
            system_name="Left Camera", axis="Y", mac_address="28:84:85:a0:c2:9c"
        )
        self.oss_slave_z_widget = SlaveMacWidget(
            system_name="Top Camera", axis="Z", mac_address="84:fc:e6:68:41:28"
        )
        self.cnc_widget = WifiStatusWidget(
            system_name="Cutting and Creasing Plotter", icon_path=ICON_BOX, temp_pw="SST@2002",
            target_ssid=wifi_ssid, target_pw=wifi_pw, device_host="CCP-MASTER",
            ap_ssid="CCP_MASTER_SETUP_AP", udp_device_id="cnc"
        )
        hierarchy.set_connections({
            self.pc_widget: [self.oss_master_status_widget, self.cnc_widget],
            self.oss_master_status_widget: [
                self.oss_slave_x_widget, self.oss_slave_y_widget, self.oss_slave_z_widget
            ]
        })
        network_main_layout.addWidget(hierarchy)

        self.update_wifi_band()
        self.wifi_band_timer = QTimer(self)
        self.wifi_band_timer.timeout.connect(self.update_wifi_band)
        self.wifi_band_timer.start(3000)

    def _start_services(self):
        self.network_monitor = WifiNetworkMonitor(
            setup_ssids=["OSS_MASTER_SETUP_AP", "CCP_MASTER_SETUP_AP"]
        )
        self.network_monitor.network_changed.connect(self.handle_network_changed)
        self.network_monitor.setup_ap_detected.connect(self.handle_setup_ap_detected)
        self.udp_listener = WifiUdpListener()
        self.udp_listener.status_received.connect(self.handle_udp_status)
        self.udp_listener.order_triggered.connect(self.handle_order_pressed)
        self.oss_master_status_widget.device_online_changed.connect(
            lambda online: self.handle_device_online_changed("oss-master", online)
        )
        self.cnc_widget.device_online_changed.connect(
            lambda online: self.handle_device_online_changed("cnc", online)
        )
        self.network_monitor.start_scanning()
        self.network_monitor.start()

    def get_connected_ssid(self):
        try:
            result = subprocess.check_output(
                ["netsh", "wlan", "show", "interfaces"],
                text=True, encoding="utf-8", errors="ignore"
            )
            match = re.search(r"^\s*SSID\s*:\s(.+)$", result, re.MULTILINE)
            if match and match.group(1).strip().lower() != "ssid":
                return match.group(1).strip()
        except Exception as error:
            print("SSID Error:", error)
        return "No Wi-Fi"

    def get_connected_wifi_channel(self):
        try:
            result = subprocess.check_output(
                ["netsh", "wlan", "show", "interfaces"],
                text=True, encoding="utf-8", errors="ignore"
            )
            match = re.search(r"^\s*Channel\s*:\s*(\d+)", result, re.MULTILINE)
            return int(match.group(1)) if match else None
        except (OSError, ValueError):
            return None

    def get_connected_wifi_band(self):
        channel = self.get_connected_wifi_channel()
        if channel is None:
            return "Unknown"
        if 1 <= channel <= 14:
            return "2.4 GHz"
        if channel >= 36:
            return "5 GHz"
        return "Other"

    def get_wifi_password(self, ssid):
        password = WifiCredentialManager.get_password(ssid)
        return password if password is not None else "Unavailable"

    def update_wifi_band(self):
        band = self.get_connected_wifi_band()
        self.current_wifi_band = band
        self.current_wifi_is_5ghz = band == "5 GHz"
        self.pc_widget.set_laptop_band(self.current_wifi_is_5ghz)
        if band == "2.4 GHz":
            self.clear_wifi_band_tooltip()
        elif band in ("5 GHz", "Other"):
            self.show_wifi_band_tooltip()

    def show_wifi_band_tooltip(self):
        if self.wifi_band_tooltip is not None:
            return
        content = InlineBadgeParagraphWrapper(
            text_font_color="#ffffff", badge_font_color="#991b1b",
            badge_bg_color="#fee2e2", badge_border_color="#fecaca",
            badge_icon_color="#991b1b"
        )
        content.insert_text("Switch the ")
        content.insert_badge_with_icon("PC", ICON_PC)
        content.insert_text(" to a ")
        content.insert_badge_with_icon("2.4 GHz", ICON_WIFI_CHANNEL)
        content.insert_text(" Wi-Fi network.")
        self.wifi_band_tooltip = AnchoredTooltip(
            content=content, target=self.pc_widget, position="left", tooltip_color="#991b1b"
        )
        self.wifi_band_tooltip.show()

    def clear_wifi_band_tooltip(self):
        tooltip = self.wifi_band_tooltip
        self.wifi_band_tooltip = None
        if tooltip is not None:
            tooltip.close()
            tooltip.deleteLater()

    def handle_network_changed(self, ssid):
        self.refresh_network_status(ssid)

    def refresh_network_status(self, ssid=None):
        ssid = ssid or self.get_connected_ssid()
        self.update_wifi_band()
        if ssid != self.current_ssid:
            self.current_ssid = ssid
            password = self.get_wifi_password(ssid) if ssid != "No Wi-Fi" else "Unavailable"
            for widget in (self.pc_widget, self.oss_master_status_widget, self.cnc_widget):
                widget.target_ssid = ssid
                widget.target_pw = password
            for widget in (self.oss_master_status_widget, self.cnc_widget):
                widget.heartbeat_received = False
                widget.heartbeat_matches_pc = False
                self.clear_esp_wifi_guidance(widget)
        self.sync_esp_wifi_guidance()
        self.pc_widget.set_online_status(ssid != "No Wi-Fi")
        self.pc_widget.set_connected_network(ssid)

    def handle_udp_status(self, device_id, is_connected, esp_ssid):
        pc_ssid = self.current_ssid or self.get_connected_ssid()
        for widget in (self.oss_master_status_widget, self.cnc_widget):
            if widget.udp_device_id == device_id:
                widget.handle_udp_status(device_id, is_connected, esp_ssid, pc_ssid)
        self.sync_esp_wifi_guidance()

    def sync_esp_wifi_guidance(self):
        pc_ssid = self.current_ssid or self.get_connected_ssid()
        for widget in (self.oss_master_status_widget, self.cnc_widget):
            esp_ssid = getattr(widget, "_heartbeat_ssid", None)
            if getattr(widget, "heartbeat_received", False) and esp_ssid and esp_ssid != pc_ssid:
                show_esp_wifi_guidance(self, widget, esp_ssid)
            else:
                self.clear_esp_wifi_guidance(widget)

    def clear_esp_wifi_guidance(self, widget):
        tooltip = getattr(self, "esp_wifi_tooltips", {}).pop(widget, None)
        if tooltip is not None:
            tooltip.close()
            tooltip.deleteLater()

    def handle_device_online_changed(self, system_name, is_online):
        devices_online = all(
            getattr(widget, "_device_online", False)
            for widget in (self.oss_master_status_widget, self.cnc_widget)
        )
        if devices_online:
            self.network_monitor.stop_scanning()
        else:
            self.network_monitor.start_scanning()

    def handle_setup_ap_detected(self, ssid):
        widgets = {
            "OSS_MASTER_SETUP_AP": self.oss_master_status_widget,
            "CCP_MASTER_SETUP_AP": self.cnc_widget,
        }
        widget = widgets.get(ssid)
        if widget is None or getattr(widget, "_setup_running", False):
            return
        self.network_monitor.stop_scanning()
        widget._setup_running = True
        widget.start_setup_overlay()

    def handle_order_pressed(self, device_name, payload):
        order_id, order_path = OrderManager().create_new_order(payload.get("order_id"))
        if order_id:
            self.order_created.emit(order_id, order_path)
            print(f"Ready to accept slave camera uploads at: {order_path}")

    def close(self):
        self.clear_wifi_band_tooltip()
        if hasattr(self, "network_monitor"):
            self.network_monitor.stop()
        super().close()