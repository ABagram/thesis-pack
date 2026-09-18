#include <WiFi.h>
#include <esp_now.h>
#include "esp_mac.h"
#include <HTTPClient.h>
#include "esp_camera.h"

// ESP32-S3 EYE camera pins
#define PWDN_GPIO_NUM     -1
#define RESET_GPIO_NUM    -1
#define XCLK_GPIO_NUM     15
#define SIOD_GPIO_NUM     4
#define SIOC_GPIO_NUM     5

#define Y2_GPIO_NUM       11
#define Y3_GPIO_NUM       9
#define Y4_GPIO_NUM       8
#define Y5_GPIO_NUM       10
#define Y6_GPIO_NUM       12
#define Y7_GPIO_NUM       18
#define Y8_GPIO_NUM       17
#define Y9_GPIO_NUM       16

#define VSYNC_GPIO_NUM    6
#define HREF_GPIO_NUM     7
#define PCLK_GPIO_NUM     13

typedef struct {
    uint8_t msgType;
    char ssid[32];
    char pass[64];
    char laptopIp[16];
    char orderId[32];
    char role[8];
} EspNowPacket;

struct CameraIdentity {
    const char* macStr;
    const char* role;
};

const CameraIdentity CAMERA_TABLE[] = {
    {"c0:4e:30:2f:28:94", "back"},
    {"28:84:85:a0:c2:9c", "side"},
    {"84:fc:e6:5f:6f:cc", "top"}
};

String myRole = "unknown";

char savedSsid[32] = "";
char savedPass[64] = "";
char savedLaptopIp[16] = "";

bool hasCredentials = false;

char activeOrderId[32] = "";

volatile bool triggerReceived = false;

uint8_t broadcastAddr[] = {
    0xFF, 0xFF, 0xFF,
    0xFF, 0xFF, 0xFF
};

void identifySelf() {
    Serial.println("IDENTIFY START");

    uint8_t mac[6];
    esp_read_mac(mac, ESP_MAC_WIFI_STA);

    char macStr[18];

    snprintf(
        macStr,
        sizeof(macStr),
        "%02x:%02x:%02x:%02x:%02x:%02x",
        mac[0], mac[1], mac[2],
        mac[3], mac[4], mac[5]
    );

    Serial.print("Current Board MAC: ");
    Serial.println(macStr);

    myRole = "unknown";

    for (auto &cam : CAMERA_TABLE) {
        if (strcmp(macStr, cam.macStr) == 0) {
            myRole = cam.role;
            break;
        }
    }

    Serial.print("This board's role: ");
    Serial.println(myRole);

    Serial.println("IDENTIFY COMPLETE");
}

void onDataRecv(const esp_now_recv_info *info, const uint8_t *incomingData, int len) {

    if (len < sizeof(EspNowPacket)) {
        Serial.printf("PACKET TOO SHORT: %d bytes\n", len);
        return;
    }

    EspNowPacket pkt;
    memcpy(&pkt, incomingData, sizeof(pkt));

    Serial.printf("PACKET PROCESSED: msgType=%d\n", pkt.msgType);

    if (pkt.msgType == 0) {

        strncpy(savedSsid, pkt.ssid, sizeof(savedSsid));
        savedSsid[sizeof(savedSsid) - 1] = '\0';

        strncpy(savedPass, pkt.pass, sizeof(savedPass));
        savedPass[sizeof(savedPass) - 1] = '\0';

        strncpy(savedLaptopIp, pkt.laptopIp, sizeof(savedLaptopIp));
        savedLaptopIp[sizeof(savedLaptopIp) - 1] = '\0';

        hasCredentials = true;

        Serial.println("Received updated Wi-Fi credentials from Master.");

    } else if (pkt.msgType == 1) {

        strncpy(activeOrderId, pkt.orderId, sizeof(activeOrderId) - 1);
        activeOrderId[sizeof(activeOrderId) - 1] = '\0';

        Serial.printf("Order start received: %s\n", activeOrderId);

    } else if (pkt.msgType == 2) {

        Serial.printf("Grant role: [%s]\n", pkt.role);
        Serial.printf("My role:    [%s]\n", myRole.c_str());

        Serial.printf("Grant order: [%s]\n", pkt.orderId);
        Serial.printf("Active order:[%s]\n", activeOrderId);

        if (strcmp(pkt.role, myRole.c_str()) == 0 &&
            strcmp(pkt.orderId, activeOrderId) == 0) {

            Serial.println("Capture grant received from Master!");
            triggerReceived = true;

        } else {
            Serial.println("Capture grant DOES NOT MATCH.");
        }
    }
}

void sendCaptureComplete() {

    EspNowPacket pkt = {};

    pkt.msgType = 3;

    strncpy(pkt.orderId, activeOrderId, sizeof(pkt.orderId) - 1);
    strncpy(pkt.role, myRole.c_str(), sizeof(pkt.role) - 1);

    esp_err_t result = esp_now_send(
        broadcastAddr,
        (uint8_t*)&pkt,
        sizeof(pkt)
    );

    if (result == ESP_OK) {
        Serial.printf(
            "CAPTURE COMPLETE SENT: role=%s, order=%s\n",
            pkt.role,
            pkt.orderId
        );
    } else {
        Serial.printf(
            "CAPTURE COMPLETE SEND FAILED: 0x%x\n",
            result
        );
    }
}

void setup() {
    Serial.begin(115200);
    delay(1000);

    Serial.println("BOOT OK");

    camera_config_t config = {};

    config.ledc_channel = LEDC_CHANNEL_0;
    config.ledc_timer = LEDC_TIMER_0;

    config.pin_d0 = Y2_GPIO_NUM;
    config.pin_d1 = Y3_GPIO_NUM;
    config.pin_d2 = Y4_GPIO_NUM;
    config.pin_d3 = Y5_GPIO_NUM;
    config.pin_d4 = Y6_GPIO_NUM;
    config.pin_d5 = Y7_GPIO_NUM;
    config.pin_d6 = Y8_GPIO_NUM;
    config.pin_d7 = Y9_GPIO_NUM;

    config.pin_xclk = XCLK_GPIO_NUM;
    config.pin_pclk = PCLK_GPIO_NUM;
    config.pin_vsync = VSYNC_GPIO_NUM;
    config.pin_href = HREF_GPIO_NUM;

    config.pin_sccb_sda = SIOD_GPIO_NUM;
    config.pin_sccb_scl = SIOC_GPIO_NUM;

    config.pin_pwdn = PWDN_GPIO_NUM;
    config.pin_reset = RESET_GPIO_NUM;

    config.xclk_freq_hz = 10000000;
    config.pixel_format = PIXFORMAT_JPEG;

    // IMPORTANT: Since PSRAM is disabled, start conservatively.
    config.frame_size = FRAMESIZE_VGA;
    config.jpeg_quality = 12;
    config.fb_count = 1;
    config.fb_location = CAMERA_FB_IN_DRAM;
    config.grab_mode = CAMERA_GRAB_WHEN_EMPTY;

    Serial.println("CAMERA INIT START");

    esp_err_t err = esp_camera_init(&config);

    if (err != ESP_OK) {
        Serial.printf("CAMERA INIT FAILED: 0x%x\n", err);
        return;
    }

    Serial.println("CAMERA INIT OK");

    Serial.println("WIFI INIT START");

    WiFi.mode(WIFI_STA);

    identifySelf();

    WiFi.setTxPower(WIFI_POWER_8_5dBm);
    WiFi.disconnect();
    WiFi.setSleep(false);

    Serial.println("WIFI INIT OK");
    Serial.println("ESPNOW INIT START");

    if (esp_now_init() != ESP_OK) {
        Serial.println("ESPNOW INIT FAILED");
        return;
    }

    Serial.println("ESPNOW INIT OK");

    esp_now_peer_info_t peerInfo = {};

    memcpy(peerInfo.peer_addr, broadcastAddr, 6);
    peerInfo.channel = 0;
    peerInfo.encrypt = false;

    if (!esp_now_is_peer_exist(broadcastAddr)) {

        esp_err_t result = esp_now_add_peer(&peerInfo);

        if (result == ESP_OK) {
            Serial.println("BROADCAST PEER ADDED");
        } else {
            Serial.printf(
                "BROADCAST PEER ADD FAILED: 0x%x\n",
                result
            );
        }
    }

    esp_now_register_recv_cb(onDataRecv);

    Serial.println("ESPNOW RECEIVE READY");
}

void loop() {

    if (triggerReceived) {

        Serial.println("=== CAPTURE TRIGGERED ===");

        triggerReceived = false;

        camera_fb_t *fb = esp_camera_fb_get();

        if (!fb) {
            Serial.println("FRAME CAPTURE FAILED");
        } else {
            Serial.printf("TRIGGERED FRAME OK: %u bytes\n", fb->len);
            esp_camera_fb_return(fb);
        }

        Serial.println("=== CAPTURE COMPLETE ===");

        // Tell Master that this camera finished
        sendCaptureComplete();
    }

    delay(10);
}