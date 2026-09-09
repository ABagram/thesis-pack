import json

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtNetwork import QHostAddress, QUdpSocket

UDP_STATUS_PORT = 4210


class WifiUdpListener(QObject):
    status_received = pyqtSignal(str, bool, object)

    def __init__(self, port=UDP_STATUS_PORT, parent=None):
        super().__init__(parent)

        self.socket = QUdpSocket(self)
        self.socket.readyRead.connect(self._read_pending_datagrams)

        if not self.socket.bind(
            QHostAddress.SpecialAddress.AnyIPv4,
            port,
            QUdpSocket.BindFlag.ShareAddress
            | QUdpSocket.BindFlag.ReuseAddressHint,
        ):
            raise RuntimeError(
                f"Could not bind UDP status listener to port {port}: "
                f"{self.socket.errorString()}"
            )

    def _read_pending_datagrams(self):
        while self.socket.hasPendingDatagrams():
            datagram = self.socket.receiveDatagram()

            try:
                payload = json.loads(
                    bytes(datagram.data()).decode("utf-8")
                )
            except (UnicodeDecodeError, json.JSONDecodeError):
                continue

            device = payload.get("device")
            if not device:
                continue

            self.status_received.emit(
                str(device),
                bool(payload.get("connected", False)),
                payload.get("ssid"),
            )
