import subprocess
import re


class WifiCredentialManager:
    """
    Retrieves Wi-Fi credentials from Windows' saved WLAN profiles.

    This class does not permanently store Wi-Fi passwords.
    """

    @staticmethod
    def get_password(ssid):
        """
        Return the password stored by Windows for the given SSID.

        Returns:
            str: Wi-Fi password if available.
            None: If the profile does not exist or the password
                  cannot be retrieved.
        """

        if not ssid or ssid == "No Wi-Fi":
            return None

        try:
            result = subprocess.run(
                [
                    "netsh",
                    "wlan",
                    "show",
                    "profile",
                    f"name={ssid}",
                    "key=clear"
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="ignore"
            )

            if result.returncode != 0:
                print(
                    "Could not read Wi-Fi profile:",
                    result.stderr.strip()
                )
                return None

            match = re.search(
                r"Key Content\s*:\s*(.+)",
                result.stdout
            )

            if match:
                return match.group(1).strip()

            return None

        except Exception as e:
            print("Wi-Fi credential error:", e)
            return None