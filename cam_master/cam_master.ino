#include <WiFiManager.h>
#include <ESPmDNS.h>
#include <WebServer.h>
#include <ArduinoJson.h>
#include <TFT_eSPI.h>

WiFiManager wm;

static bool lastState = HIGH;

const int TRIGGER_PIN = 4; // button to configure wifi network by broadcasting the temporary access point
const int TFT_BL = 32;
const int BL_CHANNEL = 0;
const int BL_FREQ = 5000;
const int BL_RESOLUTION = 8;

unsigned long wifiLostTime = 0;
bool wifiLost = false;

unsigned long lastReconnectAttempt = 0;

WebServer server(80);

TFT_eSPI tft = TFT_eSPI();

void showConnectedScreen() {
    tft.fillScreen(TFT_BLACK);
    tft.setTextColor(TFT_GREEN);
    tft.setTextSize(2);
    tft.drawString("CAM MASTER", 20, 20);
    tft.setTextColor(TFT_WHITE);
    tft.drawString("Status: Connected", 20, 60);
    tft.drawString("SSID: " + WiFi.SSID(), 20, 100);
    tft.drawString("IP: " + WiFi.localIP().toString(), 20, 140);
    tft.drawString("Host: CAM-MASTER.local", 20, 180);
}

void showPortalScreen() {
    tft.fillScreen(TFT_BLACK);
    tft.setTextColor(TFT_YELLOW);
    tft.setTextSize(2);
    tft.drawString("WiFi Setup Mode", 20, 20);
    tft.setTextColor(TFT_WHITE);
    tft.drawString("Connect to:", 20, 70);
    tft.drawString("CAM_SETUP_AP", 20, 100);
    tft.drawString("Password:", 20, 150);
    tft.drawString("SST@2002", 20, 180);
    tft.drawString("Open: 192.168.4.1", 20, 230);
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
    tft.drawString("CAM MASTER", 20, 20);

    pinMode(TRIGGER_PIN, INPUT_PULLUP);
    
    // network hostname
    WiFi.setHostname("CAM-MASTER");

    // set a temporary access point called CAM_SETUP_AP for the PC to connect to CAM_MASTER
    bool res = wm.autoConnect("CAM_SETUP_AP", "SST@2002");

    if (!res){
        Serial.println("Failed to connect");
        ESP.restart();
    }

    enterStationMode();

    Serial.print("Wi-Fi mode: ");
    Serial.println(WiFi.getMode());

    startNetworkServices();
    showConnectedScreen();

}

void loop()
{
    server.handleClient();

    // (1 = Not pressed, 0 = Pressed)
    static unsigned long lastDebugTime = 0;
    if (millis() - lastDebugTime > 500) {
        Serial.print("Button Pin State: ");
        Serial.println(digitalRead(TRIGGER_PIN));
        lastDebugTime = millis();
    }
    
    bool currentState = digitalRead(TRIGGER_PIN);

    if (lastState == HIGH && currentState == LOW)
    {
        Serial.println("Button pressed once!");
        startSetupPortal();
    }

    lastState = currentState;

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
}

void startSetupPortal()
{   
    Serial.println("Button pressed!");
    Serial.println("Disconnecting from current Wi-Fi network...");

    stopNetworkServices();

    WiFi.disconnect(true);
    delay(100);

    showPortalScreen();

    Serial.println("Starting AP Portal: CAM_SETUP_AP");
    
    bool result = wm.startConfigPortal("CAM_SETUP_AP", "SST@2002");

    Serial.print("Result: ");
    Serial.println(result);

    if (result){

        enterStationMode();

        startNetworkServices();
        showConnectedScreen();
        
        Serial.println("Returned to STA mode");
    }
}

void handleStatus() {
    DynamicJsonDocument doc(256);

    doc["connected"] = WiFi.status() == WL_CONNECTED;
    doc["ssid"] = WiFi.SSID();
    doc["ip"] = WiFi.localIP().toString();

    String response;
    serializeJson(doc, response);

    server.send(200, "application/json", response);
}

void enterStationMode(){
    WiFi.softAPdisconnect(true);
    WiFi.mode(WIFI_STA);
    Serial.println(WiFi.localIP());
}

void startNetworkServices(){
    if (MDNS.begin("CAM-MASTER")){
        Serial.println("mDNS started");
    } else{
        Serial.println("Failed to start mDNS");
    }
    server.on("/status", handleStatus);
    server.begin();
}

void stopNetworkServices(){
    server.stop();
    MDNS.end();
}