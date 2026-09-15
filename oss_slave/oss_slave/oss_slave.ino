#include <WiFi.h>
#include <esp_now.h>
#include <HTTPClient.h>
#include "esp_camera.h" // Required for OV3660 definitions

// --- CORRECTED ESP32-S3 EYE CAMERA PIN DEFINITIONS ---
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

// Structure matching the Master's packet
typedef struct {
    uint8_t msgType;      // 0 = creds, 1 = trigger
    char ssid[32];
    char pass[64];
    char laptopIp[16];
} EspNowPacket;

// Camera identification table
struct CameraIdentity {
    const char* macStr;
    const char* role;
};

const CameraIdentity CAMERA_TABLE[] = {
    {"c0:4e:30:2f:28:94", "front"},
    {"28:84:85:a0:c2:9c", "top"},
    {"84:fc:e6:68:41:28", "side"}
};

String myRole = "unknown";

// Stored network configuration received via ESP-NOW
char savedSsid[32] = "";
char savedPass[64] = "";
char savedLaptopIp[16] = "";
bool hasCredentials = false;

// Flag to handle trigger event in main loop
volatile bool triggerReceived = false;

void identifySelf() {
    Serial.println("[CP-3] Entering identifySelf()");
    WiFi.mode(WIFI_STA);
    delay(100); // Give the Wi-Fi stack a brief moment to initialize
    
    String mac = WiFi.macAddress();
    mac.toLowerCase();

    Serial.print("Current Board MAC: ");
    Serial.println(mac);

    for (auto &cam : CAMERA_TABLE) {
        if (mac.equals(cam.macStr)) {
            myRole = cam.role;
            break;
        }
    }

    Serial.print("This board's role: ");
    Serial.println(myRole);
    Serial.println("[CP-4] Exiting identifySelf()");
}

// Updated callback for ESP32 Arduino Core v3.x
void OnDataRecv(const esp_now_recv_info *info, const uint8_t *incomingData, int len) {
    if (len < sizeof(EspNowPacket)) return;
    
    EspNowPacket pkt;
    memcpy(&pkt, incomingData, sizeof(pkt));

    if (pkt.msgType == 0) {
        strncpy(savedSsid, pkt.ssid, sizeof(savedSsid));
        strncpy(savedPass, pkt.pass, sizeof(savedPass));
        strncpy(savedLaptopIp, pkt.laptopIp, sizeof(savedLaptopIp));
        hasCredentials = true;
        Serial.println("Received updated Wi-Fi credentials from Master.");
    } 
    else if (pkt.msgType == 1) {
        Serial.println("Capture trigger received from Master!");
        triggerReceived = true;
    }
}

void initCamera() {
    Serial.println("[CP-5] Entering initCamera()");
    camera_config_t config;
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
    config.frame_size = FRAMESIZE_XGA; // You can drop to SVGA if needed, but XGA works with PSRAM
    config.jpeg_quality = 12;
    
    // Configure PSRAM usage properly to avoid memory crashes
    if (psramFound()) {
        config.fb_count = 2;
        config.fb_location = CAMERA_FB_IN_PSRAM;
        config.grab_mode = CAMERA_GRAB_LATEST;
    } else {
        config.fb_count = 1;
        config.fb_location = CAMERA_FB_IN_DRAM;
        config.grab_mode = CAMERA_GRAB_WHEN_EMPTY;
    }

    Serial.println("[CP-6] Calling esp_camera_init()...");
    esp_err_t err = esp_camera_init(&config);
    if (err != ESP_OK) {
        Serial.printf("Camera init failed with error 0x%x\n", err);
        return;
    }

    // Optional: match sensor adjustments from your working code
    sensor_t * s = esp_camera_sensor_get();
    if (s) {
        s->set_vflip(s, 1);
        s->set_brightness(s, 1);
        s->set_saturation(s, 0);
    }

    Serial.println("OV3660 Camera initialized successfully!");
    Serial.println("[CP-7] Exiting initCamera()");
}

void setup() {
    Serial.begin(115200);
    delay(1000); // Allow serial monitor to catch boot logs
    Serial.println("[CP-1] Setup started");

    // Station mode is required for ESP-NOW and Wi-Fi client operations
    WiFi.mode(WIFI_STA);
    WiFi.disconnect();
    Serial.println("[CP-2] WiFi mode set to STA and disconnected");

    identifySelf();
    initCamera();

    // Initialize ESP-NOW with debug checkpoints
    Serial.println("[CP-8] Initializing ESP-NOW...");
    if (esp_now_init() != ESP_OK) {
        Serial.println("ESP-NOW Init Failed!");
        return;
    }

    Serial.println("[CP-9] Registering ESP-NOW receive callback...");
    esp_now_register_recv_cb(OnDataRecv);
    
    Serial.println("[CP-10] Slave ready and listening for Master packets...");
}

void sendImageToServer() {
    Serial.println("[CP-11] Entering sendImageToServer()");
    // 1. Capture frame from OV3660
    camera_fb_t * fb = esp_camera_fb_get();
    if (!fb) {
        Serial.println("Camera capture failed");
        return;
    }
    Serial.println("[CP-12] Frame captured successfully");

    // 2. Connect to Wi-Fi to Upload
    Serial.println("[" + myRole + "] Connecting to Wi-Fi: " + String(savedSsid));
    WiFi.begin(savedSsid, savedPass);

    unsigned long startAttempt = millis();
    while (WiFi.status() != WL_CONNECTED && millis() - startAttempt < 10000) {
        delay(500);
        Serial.print(".");
    }
    Serial.println();

    if (WiFi.status() == WL_CONNECTED) {
        Serial.println("[" + myRole + "] Connected! IP: " + WiFi.localIP().toString());

        String uploadUrl = "http://" + String(savedLaptopIp) + ":5000/upload?role=" + myRole;
        Serial.println("[" + myRole + "] Uploading to " + uploadUrl);
        
        HTTPClient http;
        http.begin(uploadUrl);
        http.addHeader("Content-Type", "image/jpeg");
        
        int httpResponseCode = http.POST(fb->buf, fb->len);
        
        if (httpResponseCode > 0) {
            Serial.printf("HTTP Response code: %d\n", httpResponseCode);
        } else {
            Serial.printf("Error on sending POST: %s\n", http.errorToString(httpResponseCode).c_str());
        }
        http.end();

        // Disconnect immediately to free up router slots
        WiFi.disconnect(true);
        WiFi.mode(WIFI_STA);
        Serial.println("[" + myRole + "] Disconnected from Wi-Fi. Returning to ESP-NOW listen mode.");
    } else {
        Serial.println("[" + myRole + "] Wi-Fi connection timed out.");
    }

    // 3. Clean up frame buffer
    esp_camera_fb_return(fb);
    Serial.println("[CP-13] Exiting sendImageToServer()");
}

void handleCaptureAndUpload() {
    if (!hasCredentials) {
        Serial.println("Cannot upload: No Wi-Fi credentials received yet.");
        return;
    }

    // 1. Staggered Delay based on role to prevent simultaneous router connections
    unsigned long staggerDelay = 0;
    if (myRole.equals("front")) {
        staggerDelay = 0;       
    } else if (myRole.equals("top")) {
        staggerDelay = 2000;    
    } else if (myRole.equals("side")) {
        staggerDelay = 4000;    
    }
    delay(staggerDelay);

    // 2. Take Photo and Upload
    Serial.println("[" + myRole + "] Taking photo and uploading...");
    sendImageToServer();
}

void loop() {
    if (triggerReceived) {
        triggerReceived = false;
        handleCaptureAndUpload();
    }
}