# wifi_device_status_worker.py
from PyQt6.QtCore import QObject, pyqtSignal
import requests


class WifiDeviceStatusWorker(QObject):

    poll_requested = pyqtSignal()
    status_result = pyqtSignal(bool, object)

    def __init__(self, device_host):
        super().__init__()
        self.device_host = device_host
        self._busy = False
        self.poll_requested.connect(self.poll)

    def poll(self):
        if self._busy:
            return  # a request is already in flight, don't stack another

        if not self.device_host:
            self.status_result.emit(False, None)
            return

        self._busy = True
        try:
            response = requests.get(
                f"http://{self.device_host}.local/status",
                timeout=0.6,  # LAN round trip should be ms; 2s was way too generous
            )
            response.raise_for_status()
            data = response.json()

            esp_connected = data.get("connected", False)
            esp_ssid = data.get("ssid", None)

            self.status_result.emit(esp_connected, esp_ssid)

        except Exception:
            self.status_result.emit(False, None)
        finally:
            self._busy = False