#include <WiFiManager.h>
#include <ESPmDNS.h>
#include <WebServer.h>
#include <WiFiUdp.h>
#include <ArduinoJson.h>
#include <TFT_eSPI.h>
#include <esp_now.h>

WiFiManager wm;

// buttons
const int CONFIG_WIFI_PIN = 4; // button to configure wifi network by broadcasting the temporary access point
static bool configWifiLastState = HIGH;

const int CREATE_ORDER_PIN = 22; // button: first press creates order, second press starts capture
static bool createOrderLastState = HIGH;

const int CANCEL_PIN = 13;
static bool cancelLastState = HIGH;

// tft display
const int TFT_BL = 32;
const int BL_CHANNEL = 0;
const int BL_FREQ = 5000;
const int BL_RESOLUTION = 8;

extern bool basicScreenDrawn;

// wifi related variables
unsigned long wifiLostTime = 0;
bool wifiLost = false;

unsigned long lastReconnectAttempt = 0;
unsigned long timeoutDuration = 60; // in seconds, time window to let user physically press the config wifi button in system

bool portalRunning = false;
unsigned long portalStartTime = 0;

WebServer server(80);
WiFiUDP statusUdp;
const uint16_t STATUS_UDP_PORT = 4210;
const unsigned long STATUS_BROADCAST_INTERVAL = 2500;
unsigned long lastStatusBroadcast = 0;
// Temporary diagnostic target. Replace with the laptop's current IP or make
// this configurable once unicast delivery is confirmed.
const IPAddress STATUS_LAPTOP_IP(192, 168, 0, 139);

TFT_eSPI tft = TFT_eSPI();

typedef struct {
    uint8_t msgType;      // 0=creds, 1=order, 2=cap_req, 3=cap_done, 4=up_req, 5=up_done, 6=cap_ack, 7=up_ack, 8=cancel, 9=heartbeat
    uint8_t channel;      // Current Wi-Fi channel of Master
    bool wifiConnected;   // True if slave is currently connected to Wi-Fi
    char ssid[32];
    char pass[64];
    char laptopIp[16];
    char orderId[32];
    char role[8];
} EspNowPacket;

uint8_t broadcastAddr[] = {0xFF,0xFF,0xFF,0xFF,0xFF,0xFF};
IPAddress laptopIp;
bool haveLaptopIp = false;

// order state
enum OrderState {
    READY_FOR_ORDER,
    ORDER_CREATED,
    CAPTURING,
    ORDER_COMPLETE,
    ORDER_FAILED
};

OrderState orderState = READY_FOR_ORDER;

char activeOrderId[32] = "";

// camera states
struct CameraState {

    bool captureDone;
    bool uploadDone;

    unsigned long lastCaptureRequest;
    unsigned long lastUploadRequest;

    uint8_t captureRetries;
    uint8_t uploadRetries;
};

CameraState backState = {};
CameraState sideState = {};
CameraState topState = {};

uint8_t captureStep = 0; // cam currently being processed
    // 1 = back
    // 2 = side
    // 3 = top

const unsigned long RETRY_INTERVAL = 3000;

const uint8_t MAX_RETRIES = 5;

const unsigned long FINISH_SCREEN_DURATION = 3000;
bool finishScreenActive = false;
unsigned long finishScreenStartTime = 0;

struct SlaveStatus {
    unsigned long lastSeen;
    bool wifiConnected;
};

SlaveStatus backStatus = {0, false};
SlaveStatus sideStatus = {0, false};
SlaveStatus topStatus  = {0, false};

volatile bool needDisplayRefresh = false;

void sendCaptureAck(const char* role) {

    EspNowPacket pkt = {};

    pkt.msgType = 6;

    strncpy(pkt.orderId, activeOrderId, sizeof(pkt.orderId) - 1);
    strncpy(pkt.role, role, sizeof(pkt.role) - 1);

    esp_err_t result = esp_now_send(broadcastAddr, (uint8_t*)&pkt, sizeof(pkt));

    if (result == ESP_OK) {
        Serial.printf("CAPTURE ACK SENT: %s\n", role);
    } else {
        Serial.printf("CAPTURE ACK FAILED: %s error=0x%x\n", role, result);
    }
}

void sendUploadAck(const char* role) {

    EspNowPacket pkt = {};

    pkt.msgType = 7;

    strncpy(pkt.orderId, activeOrderId, sizeof(pkt.orderId) - 1);
    strncpy(pkt.role, role, sizeof(pkt.role) - 1);

    esp_err_t result = esp_now_send(broadcastAddr, (uint8_t*)&pkt, sizeof(pkt));

    if (result == ESP_OK) {
        Serial.printf("UPLOAD ACK SENT: %s\n", role);
    } else {
        Serial.printf("UPLOAD ACK FAILED: %s error=0x%x\n", role, result);
    }
}

void onEspNowDataReceived(
    const esp_now_recv_info *info,
    const uint8_t *incomingData,
    int len
) {

    if (len < sizeof(EspNowPacket))
        return;

    EspNowPacket packet;

    memcpy(&packet, incomingData, sizeof(packet));

    // --------------------------------------------------------
    // 1. HANDLE SYSTEM STATUS / READY PACKETS FIRST (NO ORDER ID REQUIRED)
    // --------------------------------------------------------
    if (packet.msgType == 9) {
    SlaveStatus* target = nullptr;
    if (strcmp(packet.role, "back") == 0) target = &backStatus;
    else if (strcmp(packet.role, "side") == 0) target = &sideStatus;
    else if (strcmp(packet.role, "top") == 0) target = &topStatus;

    if (target) {
        bool pwrWasOn = (target->lastSeen > 0) && (millis() - target->lastSeen < 10000);
        bool wifiWasOn = target->wifiConnected;

        target->lastSeen = millis();
        target->wifiConnected = packet.wifiConnected;

        // Refresh only if power or wifi state toggled
        if ((!pwrWasOn || wifiWasOn != packet.wifiConnected) && orderState == READY_FOR_ORDER) {
            needDisplayRefresh = true;
        }
    }
    return;
}

    // --------------------------------------------------------
    // 2. IGNORE MESSAGES FROM OTHER ORDERS
    // --------------------------------------------------------
    if (
        strcmp(packet.orderId, activeOrderId) != 0
    ) {
        return;
    }

    // capture complete
    if (packet.msgType == 3) {

        Serial.printf("CAPTURE COMPLETE RECEIVED: %s\n", packet.role);

        if (strcmp(packet.role, "back") == 0) {

            backState.captureDone = true;

            backState.lastUploadRequest = millis();

            sendCaptureAck("back");
        }

        else if (strcmp(packet.role, "side") == 0) {

            sideState.captureDone = true;

            sideState.lastUploadRequest = millis();

            sendCaptureAck("side");
        }

        else if (strcmp(packet.role, "top") == 0) {

            topState.captureDone = true;

            topState.lastUploadRequest = millis();

            sendCaptureAck("top");
        }
    }

    // upload complete
    else if (packet.msgType == 5) {

        Serial.printf("UPLOAD COMPLETE RECEIVED: %s\n", packet.role);

        if (strcmp(packet.role, "back") == 0) {
            backState.uploadDone = true;
            sendUploadAck("back");
        }

        else if (strcmp(packet.role, "side") == 0) {
            sideState.uploadDone = true;
            sendUploadAck("side");
        }

        else if (strcmp(packet.role, "top") == 0) {
            topState.uploadDone = true;
            sendUploadAck("top");
        }
    }
}

void createNewOrder() {

    snprintf(activeOrderId, sizeof(activeOrderId), "order_%lu", millis());

    orderState = ORDER_CREATED;

    Serial.print("NEW ORDER CREATED");

    Serial.print("Order ID: ");
    Serial.println(activeOrderId);

    broadcastNewOrder(); // tell all slaves

    // Tell PC

    DynamicJsonDocument eventDoc(128);
    eventDoc["device"] = "oss-master";
    eventDoc["event"] = "order_button_pressed";
    eventDoc["order_id"] = activeOrderId;
    
    String eventPayload;

    serializeJson(eventDoc, eventPayload);

    statusUdp.beginPacket(
        haveLaptopIp
            ? laptopIp
            : STATUS_LAPTOP_IP,
        STATUS_UDP_PORT
    );

    statusUdp.print(eventPayload);

    statusUdp.endPacket();

    showOrderCreatedScreen();
}

void showConnectedScreen() {
    tft.fillScreen(TFT_BLACK);
    tft.setTextColor(TFT_GREEN);
    tft.setTextSize(2);
    tft.drawString("OSS MASTER", 10, 5);
    
    tft.setTextColor(TFT_WHITE);
    tft.setTextSize(2);
    tft.drawString("SSID: " + WiFi.SSID().substring(0, 10), 10, 30);
    tft.drawString("IP:   " + WiFi.localIP().toString(), 10, 55);

    // 2 Column Header
    tft.setTextColor(TFT_YELLOW);
    tft.drawString("CAM   PWR   WIFI", 10, 90);
    tft.drawString("----------------", 10, 105);
    
    auto drawSlaveRow = [](const char* name, const SlaveStatus& status, int y) {
        bool powered = (status.lastSeen > 0) && (millis() - status.lastSeen < 10000);
        
        tft.setTextColor(TFT_WHITE);
        tft.drawString(name, 10, y);
        
        // Column 1: Power Status
        tft.setTextColor(powered ? TFT_GREEN : TFT_RED);
        tft.drawString(powered ? "ON " : "OFF", 90, y);
        
        // Column 2: Wi-Fi Connection Status
        tft.setTextColor(status.wifiConnected ? TFT_GREEN : TFT_RED);
        tft.drawString(status.wifiConnected ? "OK " : "NC ", 170, y);
    };

    drawSlaveRow("BACK", backStatus, 130);
    drawSlaveRow("SIDE", sideStatus, 160);
    drawSlaveRow("TOP ", topStatus,  190);
}

void showOrderCreatedScreen() {

    tft.fillScreen(TFT_BLACK);

    tft.setTextSize(2);

    tft.setTextColor(TFT_GREEN);

    tft.drawString(
        "ORDER CREATED",
        20,
        25
    );

    tft.setTextColor(TFT_WHITE);

    tft.drawString(
        String(activeOrderId),
        20,
        65
    );

    tft.setTextColor(TFT_YELLOW);

    tft.drawString(
        "Arrange the items",
        20,
        115
    );


    tft.drawString(
        "when ready:",
        20,
        145
    );


    tft.setTextColor(TFT_WHITE);

    tft.drawString(
        "PRESS BUTTON",
        20,
        190
    );


    tft.drawString(
        "AGAIN TO CAPTURE",
        20,
        220
    );
}

void startCapture() {

    Serial.println();
    Serial.println(
        "================================"
    );

    Serial.println(
        "STARTING CAMERA CAPTURE"
    );

    Serial.println(
        "================================"
    );


    orderState = CAPTURING;


    backState = {};
    sideState = {};
    topState = {};


    captureStep = 1;


    showCaptureScreen();


    // Start with BACK

    sendCaptureRequest("back");

    backState.lastCaptureRequest =
        millis();
}

void showCaptureScreen() {

    tft.fillScreen(TFT_BLACK);

    tft.setTextSize(2);


    tft.setTextColor(TFT_YELLOW);

    tft.drawString(
        "CAPTURING ORDER",
        20,
        20
    );


    tft.setTextColor(TFT_WHITE);

    tft.drawString(
        String(activeOrderId),
        20,
        55
    );


    tft.setTextColor(TFT_WHITE);

    tft.drawString(
        "Camera Status",
        20,
        95
    );


    // BACK

    tft.setTextColor(
        backState.uploadDone
            ? TFT_GREEN
            : TFT_WHITE
    );

    if (backState.uploadDone) {

        tft.drawString(
            "BACK:  UPLOADED",
            20,
            130
        );

    }

    else if (backState.captureDone) {

        tft.drawString(
            "BACK:  WAITING UPLOAD",
            20,
            130
        );

    }

    else {

        tft.drawString(
            "BACK:  CAPTURING",
            20,
            130
        );

    }


    // SIDE

    tft.setTextColor(
        sideState.uploadDone
            ? TFT_GREEN
            : TFT_WHITE
    );

    if (sideState.uploadDone) {

        tft.drawString(
            "SIDE:  UPLOADED",
            20,
            165
        );

    }

    else if (sideState.captureDone) {

        tft.drawString(
            "SIDE:  WAITING UPLOAD",
            20,
            165
        );

    }

    else {

        tft.drawString(
            "SIDE:  WAITING",
            20,
            165
        );

    }


    // TOP

    tft.setTextColor(
        topState.uploadDone
            ? TFT_GREEN
            : TFT_WHITE
    );

    if (topState.uploadDone) {

        tft.drawString(
            "TOP:   UPLOADED",
            20,
            200
        );

    }

    else if (topState.captureDone) {

        tft.drawString(
            "TOP:   WAITING UPLOAD",
            20,
            200
        );

    }

    else {

        tft.drawString(
            "TOP:   WAITING",
            20,
            200
        );

    }
}

void finishOrder() {

    orderState = ORDER_COMPLETE;

    Serial.println("ORDER COMPLETE");
    Serial.println("ALL CAMERAS CAPTURED + UPLOADED");

    showOrderCompleteScreen();

    finishScreenActive = true;
    finishScreenStartTime = millis();
}

void processFinishScreen() {

    if (!finishScreenActive)
        return;

    if (
        millis() - finishScreenStartTime
        < FINISH_SCREEN_DURATION
    )
        return;

    finishScreenActive = false;

    memset(
        activeOrderId,
        0,
        sizeof(activeOrderId)
    );

    backState = {};
    sideState = {};
    topState = {};

    captureStep = 0;

    orderState = READY_FOR_ORDER;

    showConnectedScreen();

    Serial.println("Ready for next order.");
}

void showOrderCompleteScreen() {

    tft.fillScreen(TFT_BLACK);

    tft.setTextSize(2);


    tft.setTextColor(TFT_GREEN);

    tft.drawString(
        "ORDER COMPLETE",
        20,
        30
    );


    tft.setTextColor(TFT_WHITE);

    tft.drawString(
        "All images uploaded.",
        20,
        80
    );


    tft.drawString(
        "Ready for next order.",
        20,
        120
    );


    tft.setTextColor(TFT_YELLOW);

    tft.drawString(
        "PRESS BUTTON",
        20,
        180
    );


    tft.drawString(
        "TO CREATE NEW ORDER",
        20,
        210
    );
}

void showOrderFailedScreen(const char* reason) {

    tft.fillScreen(TFT_BLACK);

    tft.setTextSize(2);

    tft.setTextColor(TFT_RED);

    tft.drawString(
        "ORDER FAILED",
        20,
        30
    );

    tft.setTextColor(TFT_WHITE);

    tft.drawString(
        reason,
        20,
        80
    );

    tft.setTextColor(TFT_YELLOW);

    tft.drawString(
        "PRESS CANCEL",
        20,
        150
    );

    tft.drawString(
        "TO RETURN",
        20,
        180
    );
}

void processCaptureSequence() {

    if (orderState != CAPTURING)
        return;

    // back

    if (captureStep == 1) {

        if ( backState.captureDone && !backState.uploadDone) {

            if (millis() - backState.lastUploadRequest >= RETRY_INTERVAL) {

                if (backState.uploadRetries < MAX_RETRIES) {

                    backState.uploadRetries++;

                    Serial.printf(
                        "Retrying BACK upload... (%d/%d)\n",
                        backState.uploadRetries,
                        MAX_RETRIES
                    );

                    sendUploadRequest("back");

                    backState.lastUploadRequest = millis();

                }
                else {

                    Serial.println("BACK upload failed: maximum retries reached.");

                    orderState = ORDER_FAILED;
                    showOrderFailedScreen("BACK UPLOAD FAILED");

                }

            }

        }

        if (backState.captureDone && backState.uploadDone) {

            Serial.println("BACK COMPLETE");

            captureStep = 2;
            sendCaptureRequest("side");
            sideState.lastCaptureRequest = millis();

            showCaptureScreen();
        }

    }

    // side

    else if (captureStep == 2) {

        if (
            sideState.captureDone &&
            !sideState.uploadDone
        ) {

            if (
                millis() -
                sideState.lastUploadRequest
                >= RETRY_INTERVAL
            ) {

                if (sideState.uploadRetries < MAX_RETRIES) {

                    sideState.uploadRetries++;

                    Serial.printf(
                        "Retrying SIDE upload... (%d/%d)\n",
                        sideState.uploadRetries,
                        MAX_RETRIES
                    );

                    sendUploadRequest("side");

                    sideState.lastUploadRequest = millis();

                }
                else {

                    Serial.println(
                        "SIDE upload failed: maximum retries reached."
                    );

                    orderState = ORDER_FAILED;

                    showOrderFailedScreen("SIDE UPLOAD FAILED");

                }

            }

        }


        if (
            sideState.captureDone &&
            sideState.uploadDone
        ) {

            Serial.println(
                "SIDE COMPLETE"
            );

            captureStep = 3;

            sendCaptureRequest("top");

            topState.lastCaptureRequest =
                millis();

            showCaptureScreen();
        }

    }

    // top

    else if (captureStep == 3) {

        if (
            topState.captureDone &&
            !topState.uploadDone
        ) {

            if (
                millis() -
                topState.lastUploadRequest
                >= RETRY_INTERVAL
            ) {

                if (topState.uploadRetries < MAX_RETRIES) {

                    topState.uploadRetries++;

                    Serial.printf(
                        "Retrying TOP upload... (%d/%d)\n",
                        topState.uploadRetries,
                        MAX_RETRIES
                    );

                    sendUploadRequest("top");

                    topState.lastUploadRequest = millis();

                }
                else {

                    Serial.println(
                        "TOP upload failed: maximum retries reached."
                    );

                    orderState = ORDER_FAILED;

                    showOrderFailedScreen("TOP UPLOAD FAILED");

                }

            }

        }
        if (
            topState.captureDone &&
            topState.uploadDone
        ) {

            Serial.println(
                "TOP COMPLETE"
            );

            finishOrder();
        }

    }
}

void processCaptureRetries() {

    if (orderState != CAPTURING)
        return;


    if (captureStep == 1) {

        if (
            !backState.captureDone &&
            millis() -
            backState.lastCaptureRequest
            >= RETRY_INTERVAL
        ) {

            if (backState.captureRetries < MAX_RETRIES) {

                Serial.println("Retrying BACK capture...");

                sendCaptureRequest("back");

                backState.lastCaptureRequest =
                    millis();

                backState.captureRetries++;

            }
            else {

                Serial.println(
                    "BACK capture failed: maximum retries reached."
                );

                orderState = ORDER_FAILED;

                showOrderFailedScreen(
                    "BACK CAPTURE FAILED"
                );
            }
        }
    }


    else if (captureStep == 2) {

        if (
            !sideState.captureDone &&
            millis() -
            sideState.lastCaptureRequest
            >= RETRY_INTERVAL
        ) {

            if (
                sideState.captureRetries
                < MAX_RETRIES
            ) {

                Serial.println(
                    "Retrying SIDE capture..."
                );

                sendCaptureRequest("side");

                sideState.lastCaptureRequest =
                    millis();

                sideState.captureRetries++;

            }
            else {

                Serial.println(
                    "SIDE capture failed: maximum retries reached."
                );

                orderState = ORDER_FAILED;

                showOrderFailedScreen(
                    "SIDE CAPTURE FAILED"
                );
            }
        }
    }

    else if (captureStep == 3) {

        if (
            !topState.captureDone &&
            millis() -
            topState.lastCaptureRequest
            >= RETRY_INTERVAL
        ) {

            if (
                topState.captureRetries
                < MAX_RETRIES
            ) {

                Serial.println(
                    "Retrying TOP capture..."
                );

                sendCaptureRequest("top");

                topState.lastCaptureRequest =
                    millis();

                topState.captureRetries++;

            }
            else {

                Serial.println(
                    "TOP capture failed: maximum retries reached."
                );

                orderState = ORDER_FAILED;

                showOrderFailedScreen(
                    "TOP CAPTURE FAILED"
                );
            }
        }
    }
}

void showPortalScreen(int secondsLeft) {
    static bool basicScreenDrawn = false;
    
    // Reset background draw flag if starting new portal session or timed out
    if (secondsLeft == timeoutDuration || secondsLeft <= 0) {
        basicScreenDrawn = false;
    }

    if (!basicScreenDrawn) {
        tft.fillScreen(TFT_BLACK);
        tft.setTextColor(TFT_YELLOW);
        tft.setTextSize(2);
        tft.drawString("WiFi Setup Mode", 20, 20);
        tft.setTextColor(TFT_WHITE);
        tft.drawString("Connect to:", 20, 60);
        tft.drawString("OSS_MASTER_SETUP_AP", 20, 85);
        tft.drawString("Password:", 20, 120);
        tft.drawString("SST@2002", 20, 145);
        tft.drawString("Open: 192.168.4.1", 20, 180);
        basicScreenDrawn = true;
    }

    // Erase only the previous timer area
    tft.fillRect(20, 220, 280, 30, TFT_BLACK); 
    
    // Draw active countdown
    tft.setTextColor(TFT_RED);
    tft.drawString("Timeout in: " + String(secondsLeft) + "s", 20, 220);
}

void setupEspNow() {
    if (esp_now_init() != ESP_OK) {
        Serial.println("ESP-NOW init failed");
        return;
    }
    if (!esp_now_is_peer_exist(broadcastAddr)) {
        esp_now_peer_info_t peer = {};
        memcpy(peer.peer_addr, broadcastAddr, 6);
        peer.channel = 0;   // use whatever channel STA is currently on
        peer.encrypt = false;
        if (esp_now_add_peer(&peer) != ESP_OK) {
            Serial.println("Failed to add ESP-NOW broadcast peer");
        }
    }
}

void broadcastCreds() {

    if (WiFi.status() != WL_CONNECTED)return;
 
    EspNowPacket pkt = {};
    
    pkt.msgType = 0;
    
    pkt.channel = WiFi.channel();

    strncpy(pkt.ssid, WiFi.SSID().c_str(), sizeof(pkt.ssid) - 1);
    strncpy(pkt.pass, WiFi.psk().c_str(), sizeof(pkt.pass) - 1);

    IPAddress destinationLaptopIp = haveLaptopIp ? laptopIp : STATUS_LAPTOP_IP;
    strncpy(pkt.laptopIp, destinationLaptopIp.toString().c_str(), sizeof(pkt.laptopIp) - 1);

    esp_err_t result = esp_now_send(broadcastAddr, (uint8_t*)&pkt, sizeof(pkt));
}

void broadcastNewOrder() {

    EspNowPacket pkt = {};

    pkt.msgType = 1;

    strncpy(
        pkt.orderId,
        activeOrderId,
        sizeof(pkt.orderId) - 1
    );


    esp_err_t result = esp_now_send(
        broadcastAddr,
        (uint8_t*)&pkt,
        sizeof(pkt)
    );


    if (result == ESP_OK) {

        Serial.printf(
            "NEW ORDER BROADCAST: %s\n",
            activeOrderId
        );

    } else {

        Serial.printf(
            "NEW ORDER BROADCAST FAILED: 0x%x\n",
            result
        );

    }
}

void sendCaptureRequest(const char* role) {

    EspNowPacket pkt = {};

    pkt.msgType = 2;

    strncpy(
        pkt.orderId,
        activeOrderId,
        sizeof(pkt.orderId) - 1
    );

    strncpy(
        pkt.role,
        role,
        sizeof(pkt.role) - 1
    );


    esp_err_t result = esp_now_send(
        broadcastAddr,
        (uint8_t*)&pkt,
        sizeof(pkt)
    );


    if (result == ESP_OK) {

        Serial.printf(
            "CAPTURE REQUEST SENT: %s\n",
            role
        );

    } else {

        Serial.printf(
            "CAPTURE REQUEST FAILED: %s error=0x%x\n",
            role,
            result
        );

    }
}

void sendUploadRequest(const char* role) {

    EspNowPacket pkt = {};

    pkt.msgType = 4;

    strncpy(
        pkt.orderId,
        activeOrderId,
        sizeof(pkt.orderId) - 1
    );

    strncpy(
        pkt.role,
        role,
        sizeof(pkt.role) - 1
    );


    esp_err_t result = esp_now_send(
        broadcastAddr,
        (uint8_t*)&pkt,
        sizeof(pkt)
    );


    if (result == ESP_OK) {

        Serial.printf(
            "UPLOAD RETRY REQUEST SENT: %s\n",
            role
        );

    } else {

        Serial.printf(
            "UPLOAD REQUEST FAILED: %s error=0x%x\n",
            role,
            result
        );

    }
}

void checkForLaptopAck() {
    int packetSize = statusUdp.parsePacket();
    if (packetSize <= 0) return;

    char buf[128];
    int len = statusUdp.read(buf, min(packetSize, (int)sizeof(buf) - 1));
    buf[len] = 0;

    StaticJsonDocument<128> ackDoc;
    if (deserializeJson(ackDoc, buf) == DeserializationError::Ok &&
        ackDoc["type"] == "discovery_ack") {
        laptopIp = statusUdp.remoteIP();
        haveLaptopIp = true;
        Serial.print("Learned laptop IP: ");
        Serial.println(laptopIp);
    }
}

void startSetupPortal()
{   
    Serial.println("Button pressed!");
    Serial.println("Opening configuration portal...");

    stopNetworkServices();

    WiFi.disconnect(false);
    delay(100);
    
    wm.setConfigPortalBlocking(false);
    wm.setConfigPortalTimeout(timeoutDuration);
    wm.setBreakAfterConfig(true);

    // Force basicScreenDrawn reset by calling showPortalScreen with reset or resetting flag
    showPortalScreen(timeoutDuration);

    Serial.println("Starting AP Portal: OSS_MASTER_SETUP_AP");

    wm.startConfigPortal("OSS_MASTER_SETUP_AP", "SST@2002"); 

    portalRunning = true;
    portalStartTime = millis();
}

void handleStatus() {
    DynamicJsonDocument doc(256);

    doc["connected"] = WiFi.status() == WL_CONNECTED;
    doc["ssid"] = WiFi.SSID();
    doc["ip"] = WiFi.localIP().toString();

    if (WiFi.getMode() == WIFI_AP)
        doc["mode"] = "portal";
    else if (WiFi.getMode() == WIFI_STA)
        doc["mode"] = "station";
    else
        doc["mode"] = "unknown";

    doc["hostname"] = "OSS-MASTER";

    String response;
    serializeJson(doc, response);

    server.send(200, "application/json", response);
}

void broadcastStatus() {
    unsigned long now = millis();

    if (now - lastStatusBroadcast < STATUS_BROADCAST_INTERVAL)
        return;

    lastStatusBroadcast = now;

    DynamicJsonDocument doc(256);
    bool connected = WiFi.status() == WL_CONNECTED;

    doc["device"] = "oss-master";
    doc["connected"] = connected;
    doc["ssid"] = connected ? WiFi.SSID() : "";
    doc["ip"] = connected
        ? WiFi.localIP().toString()
        : WiFi.softAPIP().toString();
    doc["mode"] = WiFi.getMode() == WIFI_AP ? "portal" : "station";

    String payload;
    serializeJson(doc, payload);

    IPAddress localIp = WiFi.localIP();
    IPAddress subnetMask = WiFi.subnetMask();
    IPAddress broadcastIp(
        localIp[0] | ~subnetMask[0],
        localIp[1] | ~subnetMask[1],
        localIp[2] | ~subnetMask[2],
        localIp[3] | ~subnetMask[3]
    );

    IPAddress broadcastAddresses[] = {
        broadcastIp,
        IPAddress(255, 255, 255, 255),
        STATUS_LAPTOP_IP
    };

    for (IPAddress destination : broadcastAddresses) {
        if (!statusUdp.beginPacket(destination, STATUS_UDP_PORT)) {
            Serial.println("UDP heartbeat beginPacket failed");
            continue;
        }

        statusUdp.print(payload);

        if (statusUdp.endPacket() == 1) {
            Serial.print("UDP heartbeat sent to ");
            Serial.println(destination);
        } else {
            Serial.println("UDP heartbeat endPacket failed");
        }
    }
}

void enterStationMode(){
    WiFi.softAPdisconnect(true);
    WiFi.mode(WIFI_STA);
    delay(100);
    Serial.println("Returned to STA mode");
}

void startNetworkServices(){
    if (WiFi.status() == WL_CONNECTED){
        if (MDNS.begin("OSS-MASTER")){
            Serial.println("mDNS started");
        } else{
            Serial.println("Failed to start mDNS");
        }
    }
    server.begin();
}

void stopNetworkServices(){
    server.stop();
    MDNS.end();
}

void broadcastOrderCancelled() {

    if (activeOrderId[0] == '\0') {
        Serial.println("No active order to cancel.");
        return;
    }

    EspNowPacket pkt = {};

    pkt.msgType = 8;

    strncpy(
        pkt.orderId,
        activeOrderId,
        sizeof(pkt.orderId) - 1
    );

    pkt.orderId[sizeof(pkt.orderId) - 1] = '\0';

    esp_err_t result = esp_now_send(
        broadcastAddr,
        (uint8_t*)&pkt,
        sizeof(pkt)
    );

    if (result == ESP_OK) {

        Serial.print("ORDER CANCELLED SENT TO SLAVES: ");
        Serial.println(activeOrderId);

    } else {

        Serial.printf(
            "ORDER CANCELLATION FAILED: 0x%x\n",
            result
        );
    }
}

void sendOrderCancelled() {

    if (activeOrderId[0] == '\0') {
        Serial.println("No active order to cancel.");
        return;
    }

    DynamicJsonDocument eventDoc(128);

    eventDoc["device"] = "oss-master";
    eventDoc["event"] = "order_cancelled";
    eventDoc["order_id"] = activeOrderId;

    String eventPayload;

    serializeJson(
        eventDoc,
        eventPayload
    );

    IPAddress destination =
        haveLaptopIp
            ? laptopIp
            : STATUS_LAPTOP_IP;

    if (
        statusUdp.beginPacket(
            destination,
            STATUS_UDP_PORT
        )
    ) {

        statusUdp.print(eventPayload);

        if (statusUdp.endPacket() == 1) {

            Serial.print("ORDER CANCELLED SENT TO PC: ");
            Serial.println(activeOrderId);

        }
        else {

            Serial.println(
                "Failed to send order cancellation to PC."
            );

        }

    }
    else {

        Serial.println(
            "Failed to begin UDP packet for cancellation."
        );

    }
}

void resetOrderState() {

    memset(
        activeOrderId,
        0,
        sizeof(activeOrderId)
    );

    backState = {};
    sideState = {};
    topState = {};

    captureStep = 0;

    finishScreenActive = false;

    orderState = READY_FOR_ORDER;
}

void cancelCurrentOrder() {

    if (
        orderState == ORDER_CREATED ||
        orderState == CAPTURING ||
        orderState == ORDER_COMPLETE ||
        orderState == ORDER_FAILED
    ) {

        Serial.println();
        Serial.println("==============================");
        Serial.println("ORDER CANCELLED");
        Serial.print("Order ID: ");
        Serial.println(activeOrderId);
        Serial.println("==============================");

        // Tell all camera slaves to abandon this order.
        broadcastOrderCancelled();

        // Tell PC to delete the order and clear its UI.
        sendOrderCancelled();

        resetOrderState();

        showConnectedScreen();
    }
}

void setup() {
    Serial.begin(115200);

    tft.init();
    tft.setRotation(1);      // Landscape
    
    // Backlight setup
    ledcAttach(TFT_BL, 5000, 8);
    ledcWrite(TFT_BL, 255);
    
    // Temporary splash screen (remove later when EEZ UI is working)
    tft.fillScreen(TFT_BLACK);
    tft.setTextColor(TFT_WHITE);
    tft.setTextSize(2);
    tft.drawString("OSS-MASTER", 20, 20);

    pinMode(CONFIG_WIFI_PIN, INPUT_PULLUP);
    pinMode(CREATE_ORDER_PIN, INPUT_PULLUP);
    pinMode(CANCEL_PIN, INPUT_PULLUP);
    
    // network hostname
    WiFi.setHostname("OSS-MASTER");

    // set a temporary access point called OSS_MASTER_SETUP_AP for the PC to connect to OSS_MASTER
    bool res = wm.autoConnect("OSS_MASTER_SETUP_AP", "SST@2002");

    if (!res){
        Serial.println("Failed to connect");
        ESP.restart();
    }

    delay(1000);

    Serial.print("Connected SSID: ");
    Serial.println(WiFi.SSID());

    Serial.print("IP: ");
    Serial.println(WiFi.localIP());

    server.on("/status", handleStatus);

    statusUdp.begin(STATUS_UDP_PORT);
    startNetworkServices();
    setupEspNow();
    esp_now_register_recv_cb(onEspNowDataReceived);
    broadcastCreds();
    showConnectedScreen();
}

void loop()
{
    // --------------------------------------------------------
    // INSTANT DISPLAY REFRESH
    // --------------------------------------------------------
    if (needDisplayRefresh) {
        needDisplayRefresh = false;
        if (orderState == READY_FOR_ORDER) {
            showConnectedScreen();
        }
    }
    
    processFinishScreen();

    processCaptureSequence();
    processCaptureRetries();
    checkForLaptopAck();
    server.handleClient();
    broadcastStatus();

    static unsigned long lastPowerCheck = 0;
    if (orderState == READY_FOR_ORDER && millis() - lastPowerCheck >= 1000) {
        lastPowerCheck = millis();
        
        unsigned long now = millis();
        // 3-second heartbeat timeout threshold
        bool backOn  = (backStatus.lastSeen > 0)  && (now - backStatus.lastSeen < 3000);
        bool sideOn  = (sideStatus.lastSeen > 0)  && (now - sideStatus.lastSeen < 3000);
        bool topOn   = (topStatus.lastSeen > 0)   && (now - topStatus.lastSeen < 3000);

        bool backWifi = backOn && backStatus.wifiConnected;
        bool sideWifi = sideOn && sideStatus.wifiConnected;
        bool topWifi  = topOn  && topStatus.wifiConnected;

        static bool pBackOn = false, pSideOn = false, pTopOn = false;
        static bool pBackWifi = false, pSideWifi = false, pTopWifi = false;

        // Trigger display refresh immediately if power or Wi-Fi state toggles
        if (backOn != pBackOn || sideOn != pSideOn || topOn != pTopOn ||
            backWifi != pBackWifi || sideWifi != pSideWifi || topWifi != pTopWifi) {
            
            pBackOn = backOn; pSideOn = sideOn; pTopOn = topOn;
            pBackWifi = backWifi; pSideWifi = sideWifi; pTopWifi = topWifi;
            
            needDisplayRefresh = true;
        }
    }

    // ============================================================
    // PERIODIC CREDENTIAL BROADCAST (NEW)
    // ============================================================
    // Re-broadcast Wi-Fi credentials every 5 seconds when idle
    // so any newly booted slaves can receive them.
    static unsigned long lastCredsBroadcast = 0;
    if (orderState == READY_FOR_ORDER && WiFi.status() == WL_CONNECTED) {
        if (millis() - lastCredsBroadcast >= 5000) {
            lastCredsBroadcast = millis();
            broadcastCreds();
        }
    }
    // ============================================================

    if (portalRunning)
    {
        bool cancelState = digitalRead(CANCEL_PIN);

        if (cancelLastState == HIGH && cancelState == LOW) {
            Serial.println("CANCEL button pressed during WiFi setup.");

            wm.stopConfigPortal();
            portalRunning = false;

            enterStationMode();
            WiFi.begin();

            Serial.println("Exiting WiFi setup. Reconnecting to saved network...");
            showConnectedScreen(); // Force screen redraw on cancel
        }

        cancelLastState = cancelState;
        wm.process();

        static unsigned long lastScreenUpdate = 0;
        if (millis() - lastScreenUpdate >= 1000)
        {
            lastScreenUpdate = millis();
            int remaining = timeoutDuration - ((millis() - portalStartTime) / 1000);
            if (remaining < 0) remaining = 0;
            showPortalScreen(remaining);
        }

        if (!wm.getConfigPortalActive())
        {
            Serial.println("Portal closed.");
            portalRunning = false;

            enterStationMode();
            WiFi.begin();

            unsigned long start = millis();
            while (WiFi.status() != WL_CONNECTED && millis() - start < 15000)
            {
                delay(200);
            }

            startNetworkServices();
            setupEspNow();
            esp_now_register_recv_cb(onEspNowDataReceived);

            if (WiFi.status() == WL_CONNECTED) {
                Serial.println("Wi-Fi configuration successful.");
                Serial.println("Broadcasting updated credentials to camera slaves...");
                broadcastCreds();
            }

            // ALWAYS redraw main screen when portal finishes
            needDisplayRefresh = false;
            showConnectedScreen(); 
        }
        return;
    }

    // (1 = Not pressed, 0 = Pressed)
    static unsigned long lastDebugTime = 0;
    if (millis() - lastDebugTime > 500) {
        Serial.print("Button Pin State: ");
        Serial.println(digitalRead(CONFIG_WIFI_PIN));
        lastDebugTime = millis();
    }
    
    bool currentState = digitalRead(CONFIG_WIFI_PIN);

    if (configWifiLastState == HIGH && currentState == LOW)
    {
        Serial.println("Button pressed once!");
        startSetupPortal();
    }

    configWifiLastState = currentState;

    bool cancelState = digitalRead(CANCEL_PIN);

    if (
        cancelLastState == HIGH &&
        cancelState == LOW
    ) {

        Serial.println("CANCEL button pressed.");

        if (
            orderState == ORDER_CREATED ||
            orderState == CAPTURING ||
            orderState == ORDER_COMPLETE ||
            orderState == ORDER_FAILED
        ) {

            cancelCurrentOrder();

        }
    }

    cancelLastState = cancelState;

    // reconnect to saved wifi credentials
    if(WiFi.status() != WL_CONNECTED)
    {
        if(!wifiLost)
        {
            wifiLost = true;
            wifiLostTime = millis();
            lastReconnectAttempt = 0;

            Serial.println("Wi-Fi connection lost.");
        }

        // try reconnecting every 5 seconds
        if (millis() - lastReconnectAttempt >= 5000)
        {
            lastReconnectAttempt = millis();

            Serial.println("Attempting Wi-Fi reconnect...");
            WiFi.reconnect();
        }

        // if still no connection after 30 seconds,
        if(millis() - wifiLostTime >= 30000)
        {
            Serial.println("Reconnect failed. Opening config portal...");
            startSetupPortal();

            wifiLost = false; // reset timer after portal exits
        }
    }
    else
    {
        if (wifiLost){
            Serial.println("Wi-Fi reconnected.");
        }
        wifiLost = false;
    }

    bool buttonState = digitalRead(CREATE_ORDER_PIN);

    if (createOrderLastState == HIGH && buttonState == LOW) {

        // FIRST PRESS

        if (orderState == READY_FOR_ORDER) {
            createNewOrder();
        }

        // SECOND PRESS

        else if (orderState == ORDER_CREATED) {
            startCapture();
        }

        // DURING CAPTURE

        else if (orderState == CAPTURING) {
            Serial.println(
                "Capture already in progress. "
                "Button ignored."
            );
        }

        // COMPLETE

        else if (orderState == ORDER_COMPLETE) {

            Serial.println(
                "Order completion screen active."
            );

        }

    }


    createOrderLastState = buttonState;
}
