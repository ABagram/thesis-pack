import ctypes
from ctypes import wintypes
import subprocess
import re
import threading
import time

from PyQt6.QtCore import QThread, pyqtSignal


# ============================================================
# Windows WLAN API
# ============================================================

wlanapi = ctypes.WinDLL("wlanapi.dll")

WLAN_CLIENT_VERSION_LONGHORN = 2

WLAN_NOTIFICATION_SOURCE_ACM = 0x00000008
WLAN_NOTIFICATION_SOURCE_MSM = 0x00000010

WLAN_NOTIFICATION_ACM_SCAN_COMPLETE = 7
WLAN_NOTIFICATION_ACM_SCAN_FAIL = 8

WLAN_NOTIFICATION_ACM_CONNECTION_COMPLETE = 10
WLAN_NOTIFICATION_ACM_DISCONNECTED = 12
WLAN_NOTIFICATION_ACM_CONNECTION_ATTEMPT_FAIL = 11


# ============================================================
# Structures
# ============================================================

class GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", wintypes.DWORD),
        ("Data2", wintypes.WORD),
        ("Data3", wintypes.WORD),
        ("Data4", wintypes.BYTE * 8),
    ]


class WLAN_NOTIFICATION_DATA(ctypes.Structure):
    _fields_ = [
        ("NotificationSource", wintypes.DWORD),
        ("NotificationCode", wintypes.DWORD),
        ("InterfaceGuid", GUID),
        ("dwDataSize", wintypes.DWORD),
        ("pData", ctypes.c_void_p),
    ]


class WLAN_INTERFACE_INFO(ctypes.Structure):
    _fields_ = [
        ("InterfaceGuid", GUID),
        ("strInterfaceDescription", wintypes.WCHAR * 256),
        ("isState", wintypes.DWORD),
    ]


class WLAN_INTERFACE_INFO_LIST(ctypes.Structure):
    _fields_ = [
        ("dwNumberOfItems", wintypes.DWORD),
        ("dwIndex", wintypes.DWORD),
        ("InterfaceInfo", WLAN_INTERFACE_INFO * 1),
    ]


WLAN_NOTIFICATION_CALLBACK = ctypes.WINFUNCTYPE(
    None,
    ctypes.POINTER(WLAN_NOTIFICATION_DATA),
    ctypes.c_void_p
)


# ============================================================
# Wi-Fi Monitor
# ============================================================

class WifiNetworkMonitor(QThread):
    """
    Background Windows Wi-Fi monitor.

    Responsibilities:
        - Detect PC Wi-Fi connection changes.
        - Optionally perform periodic WLAN scans.
        - Detect configured ESP setup APs.
        - Never block the Qt GUI thread.
    """

    network_changed = pyqtSignal(str)
    setup_ap_detected = pyqtSignal(str)

    def __init__(self, setup_ssids=None, parent=None):
        super().__init__(parent)

        self.setup_ssids = setup_ssids or []

        self._client_handle = wintypes.HANDLE()

        self._notification_event = None
        self._running = True

        self._scanning_enabled = False
        self._scan_interval = 5
        self._last_scan_time = 0
        self._detected_setup_ssid = None

        self._last_notification_code = None

        self._callback = WLAN_NOTIFICATION_CALLBACK(
            self._wlan_notification_callback
        )

    # ========================================================
    # PC Wi-Fi
    # ========================================================

    def get_connected_ssid(self):
        try:
            result = subprocess.check_output(
                [
                    "netsh",
                    "wlan",
                    "show",
                    "interfaces"
                ],
                text=True,
                encoding="utf-8",
                errors="ignore"
            )

            match = re.search(
                r"^\s*SSID\s*:\s(.+)$",
                result,
                re.MULTILINE
            )

            if match:
                ssid = match.group(1).strip()

                if ssid and ssid.lower() != "ssid":
                    return ssid

        except Exception as e:
            print("SSID Error:", e)

        return "No Wi-Fi"

    # ========================================================
    # Setup AP detection
    # ========================================================

    def check_for_setup_ap(self):
        """
        Check Windows' current WLAN scan results for one of
        our ESP setup networks.
        """

        try:
            result = subprocess.run(
                [
                    "netsh",
                    "wlan",
                    "show",
                    "networks"
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="ignore"
            )

            visible_networks = result.stdout

            for ssid in self.setup_ssids:

                if ssid and ssid in visible_networks:

                    if ssid == self._detected_setup_ssid:
                        return True

                    print(
                        f"Setup AP detected: {ssid}"
                    )

                    self._detected_setup_ssid = ssid
                    self._scanning_enabled = False

                    self.setup_ap_detected.emit(ssid)

                    return True

            self._detected_setup_ssid = None

        except Exception as e:
            print(
                "Setup AP detection error:",
                e
            )

        return False

    # ========================================================
    # Windows WLAN scan
    # ========================================================

    def request_wlan_scan(self):
        """
        Ask Windows to perform a wireless scan.

        This only requests the scan. Windows performs the
        actual scan asynchronously.
        """

        try:
            interface_list = (
                ctypes.POINTER(
                    WLAN_INTERFACE_INFO_LIST
                )()
            )

            result = wlanapi.WlanEnumInterfaces(
                self._client_handle,
                None,
                ctypes.byref(interface_list)
            )

            if result != 0:
                print(
                    "WlanEnumInterfaces failed:",
                    result
                )
                return

            count = (
                interface_list.contents.dwNumberOfItems
            )

            if count == 0:
                return

            array_type = (
                WLAN_INTERFACE_INFO * count
            )

            interfaces = ctypes.cast(
                ctypes.addressof(
                    interface_list.contents.InterfaceInfo
                ),
                ctypes.POINTER(array_type)
            ).contents

            for interface in interfaces:

                result = wlanapi.WlanScan(
                    self._client_handle,
                    ctypes.byref(
                        interface.InterfaceGuid
                    ),
                    None,
                    None,
                    None
                )

                print(
                    "WlanScan returned:",
                    result
                )

        except Exception as e:
            print(
                "WLAN scan request error:",
                e
            )

    # ========================================================
    # WLAN notification callback
    # ========================================================

    def _wlan_notification_callback(
        self,
        notification_data,
        context
    ):
        if not notification_data:
            return

        data = notification_data.contents

        if data.NotificationSource not in (
            WLAN_NOTIFICATION_SOURCE_ACM,
            WLAN_NOTIFICATION_SOURCE_MSM,
        ):
            return

        if data.NotificationCode in (
            WLAN_NOTIFICATION_ACM_SCAN_COMPLETE,
            WLAN_NOTIFICATION_ACM_SCAN_FAIL,
            WLAN_NOTIFICATION_ACM_CONNECTION_COMPLETE,
            WLAN_NOTIFICATION_ACM_DISCONNECTED,
            WLAN_NOTIFICATION_ACM_CONNECTION_ATTEMPT_FAIL,
        ):

            if self._notification_event is not None:

                self._last_notification_code = (
                    data.NotificationCode
                )

                self._notification_event.set()

    # ========================================================
    # WLAN handle
    # ========================================================

    def _open_wlan_handle(self):

        negotiated_version = wintypes.DWORD()

        result = wlanapi.WlanOpenHandle(
            WLAN_CLIENT_VERSION_LONGHORN,
            None,
            ctypes.byref(
                negotiated_version
            ),
            ctypes.byref(
                self._client_handle
            )
        )

        if result != 0:
            raise RuntimeError(
                f"WlanOpenHandle failed with error {result}"
            )

    def _register_notifications(self):

        previous_source = wintypes.DWORD()

        result = wlanapi.WlanRegisterNotification(
            self._client_handle,
            (
                WLAN_NOTIFICATION_SOURCE_ACM
                |
                WLAN_NOTIFICATION_SOURCE_MSM
            ),
            False,
            self._callback,
            None,
            None,
            ctypes.byref(previous_source)
        )

        if result != 0:
            raise RuntimeError(
                f"WlanRegisterNotification failed "
                f"with error {result}"
            )

    def _unregister_notifications(self):

        if self._client_handle:

            wlanapi.WlanRegisterNotification(
                self._client_handle,
                0,
                False,
                None,
                None,
                None,
                None
            )

    def _close_wlan_handle(self):

        if self._client_handle:

            wlanapi.WlanCloseHandle(
                self._client_handle,
                None
            )

            self._client_handle = None

    # ========================================================
    # Thread
    # ========================================================

    def run(self):

        try:

            self._notification_event = (
                threading.Event()
            )

            self._open_wlan_handle()

            self._register_notifications()

            # ------------------------------------------------
            # Initial PC network
            # ------------------------------------------------

            initial_ssid = (
                self.get_connected_ssid()
            )

            self.network_changed.emit(
                initial_ssid
            )

            print(
                "Wi-Fi monitor started. "
                f"Current network: {initial_ssid}"
            )

            # ------------------------------------------------
            # Main monitor loop
            # ------------------------------------------------

            while self._running:

                # --------------------------------------------
                # Periodic WLAN scan
                # --------------------------------------------

                if self._scanning_enabled:

                    current_time = time.time()

                    if (
                        current_time
                        - self._last_scan_time
                        >= self._scan_interval
                    ):

                        print(
                            "Requesting WLAN scan..."
                        )

                        self.request_wlan_scan()

                        self._last_scan_time = (
                            current_time
                        )

                # --------------------------------------------
                # Wait for Windows notification
                #
                # Short timeout allows the periodic scan
                # timer above to be checked without blocking
                # indefinitely.
                # --------------------------------------------

                self._notification_event.wait(
                    timeout=0.5
                )

                if not self._running:
                    break

                if not self._notification_event.is_set():
                    continue

                self._notification_event.clear()

                notification_code = (
                    self._last_notification_code
                )

                # --------------------------------------------
                # Wi-Fi connection changed
                # --------------------------------------------

                if notification_code in (
                    WLAN_NOTIFICATION_ACM_CONNECTION_COMPLETE,
                    WLAN_NOTIFICATION_ACM_DISCONNECTED,
                    WLAN_NOTIFICATION_ACM_CONNECTION_ATTEMPT_FAIL,
                ):

                    ssid = (
                        self.get_connected_ssid()
                    )

                    print(
                        f"Wi-Fi network changed: {ssid}"
                    )

                    self.network_changed.emit(
                        ssid
                    )

                # --------------------------------------------
                # WLAN scan completed
                # --------------------------------------------

                elif (
                    notification_code
                    == WLAN_NOTIFICATION_ACM_SCAN_COMPLETE
                ):

                    if self._scanning_enabled:

                        self.check_for_setup_ap()

                # --------------------------------------------
                # Scan failed
                # --------------------------------------------

                elif (
                    notification_code
                    == WLAN_NOTIFICATION_ACM_SCAN_FAIL
                ):

                    print(
                        "Windows WLAN scan failed."
                    )

        except Exception as e:

            print(
                "Wi-Fi monitor error:",
                e
            )

        finally:

            try:
                self._unregister_notifications()
            except Exception:
                pass

            self._close_wlan_handle()

            self._notification_event = None

    # ========================================================
    # Public scanner control
    # ========================================================

    def start_scanning(self):

        if self._scanning_enabled:
            return

        print(
            "Starting periodic WLAN scanning."
        )

        self._scanning_enabled = True

        # Allow the first scan immediately.
        self._last_scan_time = 0

    def stop_scanning(self):

        if not self._scanning_enabled:
            return

        print(
            "Stopping periodic WLAN scanning."
        )

        self._scanning_enabled = False

    # ========================================================
    # Stop thread
    # ========================================================

    def stop(self):

        self._running = False

        if self._notification_event is not None:
            self._notification_event.set()

        self.wait()