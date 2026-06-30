import ctypes
from ctypes import wintypes

wlanapi = ctypes.WinDLL("wlanapi.dll")

HANDLE = wintypes.HANDLE
DWORD = wintypes.DWORD

WlanOpenHandle = wlanapi.WlanOpenHandle
WlanOpenHandle.argtypes = [
    DWORD,
    ctypes.c_void_p,
    ctypes.POINTER(DWORD),
    ctypes.POINTER(HANDLE)
]

WlanEnumInterfaces = wlanapi.WlanEnumInterfaces
WlanScan = wlanapi.WlanScan
WlanCloseHandle = wlanapi.WlanCloseHandle


class WLAN_INTERFACE_INFO(ctypes.Structure):
    _fields_ = [
        ("InterfaceGuid", ctypes.c_byte * 16),
        ("strInterfaceDescription", ctypes.c_wchar * 256),
        ("isState", DWORD),
    ]


class WLAN_INTERFACE_INFO_LIST(ctypes.Structure):
    _fields_ = [
        ("dwNumberOfItems", DWORD),
        ("dwIndex", DWORD),
        ("InterfaceInfo", WLAN_INTERFACE_INFO * 1),
    ]


def force_wifi_scan():
    negotiated = DWORD()
    client = HANDLE()

    if WlanOpenHandle(
        2,
        None,
        ctypes.byref(negotiated),
        ctypes.byref(client)
    ) != 0:
        return False

    interface_list = ctypes.POINTER(WLAN_INTERFACE_INFO_LIST)()

    if WlanEnumInterfaces(
        client,
        None,
        ctypes.byref(interface_list)
    ) != 0:
        WlanCloseHandle(client, None)
        return False

    count = interface_list.contents.dwNumberOfItems

    array_type = WLAN_INTERFACE_INFO * count

    interfaces = ctypes.cast(
        ctypes.addressof(interface_list.contents.InterfaceInfo),
        ctypes.POINTER(array_type)
    ).contents

    for interface in interfaces:
        result = WlanScan(
            client,
            ctypes.byref(interface.InterfaceGuid),
            None,
            None,
            None
        )
        
        print("WlanScan returned:", result)

    WlanCloseHandle(client, None)
    return True