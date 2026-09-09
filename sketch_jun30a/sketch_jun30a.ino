#define CAMERA_ID "X"

#include <WiFi.h> // connects ESP slave to a Wi-Fi network when uploading the captured image
#include <esp_now.h> // enables ESP-NOW communication
#include "esp_camera.h" // captures photos from the cam sensor
#include <HTTPClient.h> // sends HTTP requests; used to upload the captured image to a web server

// camera pins

#define PWDN_GPIO_NUM -1
#define RESET_GPIO_NUM -1
#define XCLK_GPIO_NUM 15
#define SIOD_GPIO_NUM 4
#define SIOC_GPIO_NUM 5

#define Y2_GPIO_NUM 11
#define Y3_GPIO_NUM 9
#define Y4_GPIO_NUM 8
#define Y5_GPIO_NUM 10
#define Y6_GPIO_NUM 12
#define Y7_GPIO_NUM 18
#define Y8_GPIO_NUM 17
#define Y9_GPIO_NUM 16

#define VSYNC_GPIO_NUM 6
#define HREF_GPIO_NUM 7
#define PCLK_GPIO_NUM 13

volatile bool captureRequested = false;
CaptureMessage pendingMsg;

typedef struct // CaptureMessage structure of both master and slave
{
    char orderId[32];
    char ssid[32];
    char password[64];
    char serverIP[32];
} CaptureMessage;


void setupEspNow(){
  esp_err_t err = esp_now_init();
  
  if (err != ESP_OK) {
    Serial.print("ESP-NOW init failed: ");
    Serial.println(err);
    return;
    }

    esp_now_register_recv_cb(onDataRecv); // whenever another ESP sends data, automatically call the custom function onDataRecv()
}

void onDataRecv(
    const esp_now_recv_info_t *info,
    const uint8_t *incomingData,
    int len
){

    if (len != sizeof(CaptureMessage))
    {
        Serial.println("Invalid message size");
        return;
    }

    memcpy(
        &pendingMsg,
        incomingData,
        sizeof(pendingMsg)
    );

    captureRequested = true;

    Serial.println("Capture request received");
}

void captureAndSend(CaptureMessage msg)
{
    Serial.println("Connecting to WiFi...");

    WiFi.mode(WIFI_STA);

    WiFi.begin(
        msg.ssid,
        msg.password
    );

    unsigned long start = millis();

    while (
        WiFi.status() != WL_CONNECTED &&
        millis() - start < 15000
    ){
        delay(200);
    }

    if(WiFi.status() != WL_CONNECTED){
        Serial.println("WiFi failed");
        return;
    }

    Serial.println("WiFi connected");
    delay(300);

    camera_fb_t *fb = esp_camera_fb_get();

    if(!fb){
        Serial.println("Camera failed");

        WiFi.disconnect(true);

        return;
    }

    bool uploaded = false;

    for(int i = 0; i < 3 && !uploaded; i++)
    {
        uploaded = uploadPhoto(
            fb,
            msg.orderId,
            CAMERA_ID,
            msg.serverIP
        );

        if(!uploaded)
        {
            Serial.println("Retry upload...");
            delay(1000);
        }
    }

    esp_camera_fb_return(fb);

    WiFi.disconnect(true, true);

    Serial.println("Finished upload");
}

bool uploadPhoto(
    camera_fb_t *fb,
    const char *orderId,
    const char *cameraId,
    const char *serverIP
)
{
    HTTPClient http;

    String url =
        String("http://") +
        serverIP +
        ":5000/upload/"+
        orderId+
        "/"+
        cameraId;

    http.begin(url);

    http.addHeader(
      "Content-Type",
      "image/jpeg"
    );

    int code =
        http.POST(
            fb->buf,
            fb->len
        );

    Serial.print("HTTP=");
    Serial.println(code);

    http.end();

    return code == 200;
}

void initCamera()
{
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

    config.frame_size = FRAMESIZE_SVGA;
    config.pixel_format = PIXFORMAT_JPEG;

    config.grab_mode = CAMERA_GRAB_WHEN_EMPTY;
    config.fb_location = CAMERA_FB_IN_PSRAM;
    config.jpeg_quality = 12;
    config.fb_count = 2;

    if(psramFound())
    {
        config.jpeg_quality = 10;
        config.fb_count = 2;
        config.grab_mode = CAMERA_GRAB_LATEST;
    }
    else
    {
        config.fb_count = 1;
        config.fb_location = CAMERA_FB_IN_DRAM;
    }

    esp_err_t err = esp_camera_init(&config);

    if(err != ESP_OK)
    {
        Serial.printf(
            "Camera init failed: 0x%x\n",
            err
        );

        return;
    }

    sensor_t *s = esp_camera_sensor_get();

    s->set_vflip(s, 1);
    s->set_brightness(s, 1);
    s->set_saturation(s, 0);
}

void setup(){

  Serial.begin(115200);
  
  WiFi.mode(WIFI_STA); // puts the ESP into Station Mode, allowing it to connect to a Wi-Fi router or enable ESP-NOW communication
  
  delay(100);

  Serial.print("MAC: "); // sender needs MAC address to send ESP-NOW messages
  Serial.println(WiFi.macAddress());

  Serial.print("WiFi mode: ");
  Serial.println(WiFi.getMode());
 
  initCamera();

  setupEspNow(); // custom function: sets up ESP-NOW communication 
}

void loop()
{
    if (captureRequested)
    {
        captureRequested = false;
        captureAndSend(pendingMsg);
    }

    delay(10);
}