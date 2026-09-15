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

const int CREATE_ORDER_PIN = 22; // button to start create a directory for order and to take photo of order
static bool createOrderLastState = HIGH;

// tft display
const int TFT_BL = 32;
const int BL_CHANNEL = 0;
const int BL_FREQ = 5000;
const int BL_RESOLUTION = 8;

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
    uint8_t msgType;      // 0 = creds, 1 = trigger
    char ssid[32];
    char pass[64];
    char laptopIp[16];
} EspNowPacket;

uint8_t broadcastAddr[] = {0xFF,0xFF,0xFF,0xFF,0xFF,0xFF};
IPAddress laptopIp;
bool haveLaptopIp = false;

void showConnectedScreen() {
    tft.fillScreen(TFT_BLACK);
    tft.setTextColor(TFT_GREEN);
    tft.setTextSize(2);
    tft.drawString("OSS MASTER", 20, 20);
    tft.setTextColor(TFT_WHITE);
    tft.drawString("Status: Connected", 20, 60);
    tft.drawString("SSID: " + WiFi.SSID(), 20, 100);
    tft.drawString("IP: " + WiFi.localIP().toString(), 20, 140);
    tft.drawString("Host: OSS-MASTER.local", 20, 180);
}

void showPortalScreen(int secondsLeft) {
    // Only draw the background text once to prevent screen flickering
    static bool basicScreenDrawn = false;
    
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

    // Erase only the previous timer area using a black rectangle
    tft.fillRect(20, 220, 280, 30, TFT_BLACK); 
    
    // Draw the active countdown
    tft.setTextColor(TFT_RED);
    tft.drawString("Timeout in: " + String(secondsLeft) + "s", 20, 220);

    // Reset the static flag when time runs out or finishes so it can be drawn next time
    if (secondsLeft <= 0) {
        basicScreenDrawn = false;
    }
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
    if (WiFi.status() != WL_CONNECTED) return;
    EspNowPacket pkt = {};
    pkt.msgType = 0;
    strncpy(pkt.ssid, WiFi.SSID().c_str(), sizeof(pkt.ssid) - 1);
    strncpy(pkt.pass, WiFi.psk().c_str(), sizeof(pkt.pass) - 1);
    if (haveLaptopIp) strncpy(pkt.laptopIp, laptopIp.toString().c_str(), sizeof(pkt.laptopIp) - 1);
    esp_now_send(broadcastAddr, (uint8_t*)&pkt, sizeof(pkt));
}

void broadcastTrigger() {
    EspNowPacket pkt = {};
    pkt.msgType = 1;
    esp_now_send(broadcastAddr, (uint8_t*)&pkt, sizeof(pkt));
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
    showConnectedScreen();
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

void loop()
{
    checkForLaptopAck();
    server.handleClient();
    broadcastStatus();

    if (portalRunning)
    {
        wm.process();

        static unsigned long lastScreenUpdate = 0;

        if (millis() - lastScreenUpdate >= 1000)
        {
            lastScreenUpdate = millis();

            int remaining = timeoutDuration - ((millis() - portalStartTime) / 1000);

            if (remaining < 0)
                remaining = 0;

            showPortalScreen(remaining);
        }

        if (!wm.getConfigPortalActive())
        {
            Serial.println("Portal closed.");

            portalRunning = false;

            enterStationMode();

            WiFi.begin();

            unsigned long start = millis();

            while (WiFi.status() != WL_CONNECTED &&
                millis() - start < 15000)
            {
                delay(200);
            }

            startNetworkServices();
            setupEspNow();

            if (WiFi.status() == WL_CONNECTED)
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

    bool orderState = digitalRead(CREATE_ORDER_PIN);
    if (createOrderLastState == HIGH && orderState == LOW) {
        Serial.println("Order button pressed - triggering capture");
        broadcastTrigger();
    }
    createOrderLastState = orderState;
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
    broadcastCreds();
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