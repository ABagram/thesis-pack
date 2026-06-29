from PyQt6.QtWidgets import QWidget, QFrame, QHBoxLayout, QVBoxLayout, QLabel, QPushButton, QToolTip
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QObject, QThread, QRect
import time
import requests
import subprocess
from read_pc_ssid import read_pc_ssid

class WifiProvisionManager(QObject):
    finished = pyqtSignal(bool)
    step_changed = pyqtSignal(int)

    def __init__(self,
                 temp_ssid,
                 temp_pw,
                 target_ssid,
                 target_pw):
        super().__init__()

        self.temp_ssid = temp_ssid
        self.temp_pw = temp_pw
        self.target_ssid = target_ssid
        self.target_pw = target_pw
    
    def wait_for_ssid(self, ssid, timeout=20):
        start = time.time()

        while time.time() - start < timeout:
            current = read_pc_ssid()

            print("Current:", current)

            if current == ssid:
                return True

            time.sleep(1)

        return False
   
    def connect_to_wifi(self, ssid, password=None):
        try:
            print(f"Connecting to {ssid}")

            security_block = ""

            if password:
                security_block = f"""
                <MSM>
                    <security>
                        <authEncryption>
                            <authentication>WPA2PSK</authentication>
                            <encryption>AES</encryption>
                            <useOneX>false</useOneX>
                        </authEncryption>

                        <sharedKey>
                            <keyType>passPhrase</keyType>
                            <protected>false</protected>
                            <keyMaterial>{password}</keyMaterial>
                        </sharedKey>
                    </security>
                </MSM>
                """

            config = f"""<?xml version="1.0"?>
    <WLANProfile xmlns="http://www.microsoft.com/networking/WLAN/profile/v1">

        <name>{ssid}</name>

        <SSIDConfig>
            <SSID>
                <name>{ssid}</name>
            </SSID>
        </SSIDConfig>

        <connectionType>ESS</connectionType>
        <connectionMode>auto</connectionMode>

        {security_block}

    </WLANProfile>
    """

            profile_path = (
                f"{ssid}_profile.xml"
            )

            with open(
                profile_path,
                "w",
                encoding="utf-8"
            ) as file:
                file.write(config)

            subprocess.run(
                ["netsh", "wlan", "add", "profile", f"filename={profile_path}"],
                capture_output=True
            )

            subprocess.run(
                ["netsh", "wlan", "connect", f"name={ssid}"],
                capture_output=True
            )

            if self.wait_for_ssid(ssid):
                print(f"Connected to {ssid}")
                return True

            print(f"Failed to connect to {ssid}")

        except Exception as e:
            print(
                "WiFi connect error:",
                e
            )

        return False
    
    def submit_portal_credentials(self):
        try:
            payload = {
                "s": self.target_ssid,
                "p": self.target_pw
            }

            print(
                "Sending WiFi credentials..."
            )

            response = requests.post(
                "http://192.168.4.1/wifisave",
                data=payload,
                timeout=10
            )

            print(
                "Submitting:",
                self.target_ssid,
                self.target_pw,
                "Response Status Code:",
                response.status_code
            )

            return (
                response.status_code
                == 200
            )

        except Exception as e:
            print(
                "Portal submit failed:",
                e
            )
            return False
    
    def run(self):
        
        print("==== WIFI PROVISION MANAGER STARTED ====")
        
        success = False

        try:
            # STEP 1
            self.step_changed.emit(0)

            print("Scanning for setup AP...")

            if not self.scan_for_setup_ap():
                raise Exception("Setup AP never appeared")

            print("Found setup AP")

            if not self.connect_to_wifi(
                self.temp_ssid,
                self.temp_pw
            ):
                raise Exception(
                    f"Could not connect to {self.temp_ssid}"
                )

            # STEP 2
            self.step_changed.emit(1)
            time.sleep(2)

            # STEP 3
            self.step_changed.emit(2)

            if (
                read_pc_ssid()
                != self.temp_ssid
            ):
                raise Exception(
                    "Not connected to "
                    "portal Wi-Fi"
                )

            # STEP 4
            self.step_changed.emit(3)

            if not (
                self.submit_portal_credentials()
            ):
                raise Exception(
                    "Failed sending "
                    "credentials to ESP"
                )

            print(
                "Waiting for ESP reboot..."
            )

            time.sleep(8)

            # STEP 5
            self.step_changed.emit(4)

            if not self.connect_to_wifi(
                self.target_ssid,
                self.target_pw
            ):
                raise Exception(
                    "Could not reconnect"
                )

            success = True

        except Exception as e:
            print("Setup Error:", e)

        self.finished.emit(success)

    def scan_for_setup_ap(self):
        
        while True:
            result = subprocess.run(
                ["netsh", "wlan", "show", "networks"],
                capture_output=True,
                text=True
            )
            
            print("stdout: ", result.stdout)
            print("stderr: ", result.stderr)
            
            if self.temp_ssid in result.stdout:
                return True
            time.sleep(1)