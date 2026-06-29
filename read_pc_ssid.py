import subprocess, re

def read_pc_ssid():
    """Return the SSID the PC is currently connected to, or None.
    Shared helper used by both WifiStatusWidget and SetupOverlay.
    """
    try:
        result = subprocess.check_output(
            ["netsh", "wlan", "show", "interfaces"],
            text=True,
            encoding="utf-8",
            errors="ignore"
        )

        match = re.search(r"^\s*SSID\s*:\s(.+)$", result, re.MULTILINE)
        if match:
            ssid = match.group(1).strip()
            if ssid.lower() != "ssid":
                return ssid
    except Exception:
        return None

    return None
