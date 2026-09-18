import json

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtNetwork import QHostAddress, QUdpSocket

UDP_STATUS_PORT = 4210

class WifiUdpListener(QObject):
    status_received = pyqtSignal(str, bool, object)  # device, connected, ssid
    order_triggered = pyqtSignal(str, dict)            # device name, event payload

    def __init__(self, port=UDP_STATUS_PORT, parent=None):
        super().__init__(parent)

        self.socket = QUdpSocket(self)
        self.socket.readyRead.connect(self._read_pending_datagrams)

        if not self.socket.bind(
            QHostAddress("0.0.0.0"),
            port,
            QUdpSocket.BindFlag.ShareAddress
            | QUdpSocket.BindFlag.ReuseAddressHint,
        ):
            raise RuntimeError(
                f"Could not bind UDP status listener to port {port}: "
                f"{self.socket.errorString()}"
            )

        print(f"UDP listener active on IPv4 port {port}")

    def _read_pending_datagrams(self):
        while self.socket.hasPendingDatagrams():
            datagram = self.socket.receiveDatagram()
            sender_addr = datagram.senderAddress()
            sender_port = datagram.senderPort()

            try:
                payload = json.loads(bytes(datagram.data()).decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                print("Ignored malformed UDP datagram")
                continue

            device = payload.get("device")
            if not device:
                print("Ignored UDP datagram without device id:", payload)
                continue

            # Send ACK so ESP32 learns this machine's IP address
            if device == "oss-master":
                ack = json.dumps({"type": "discovery_ack"}).encode("utf-8")
                self.socket.writeDatagram(ack, sender_addr, sender_port)

            # 1. Handle Event Notifications
            if payload.get("event") == "order_button_pressed":
                print(f"UDP order notification received from device={device}")
                self.order_triggered.emit(str(device), payload)
                continue

            # 2. Handle Status Heartbeats
            if "connected" in payload:
                print(
                    f"UDP heartbeat accepted: device={device}, "
                    f"connected={payload.get('connected')}, "
                    f"ssid={payload.get('ssid')}"
                )
                self.status_received.emit(
                    str(device),
                    bool(payload.get("connected", False)),
                    payload.get("ssid"),
                )