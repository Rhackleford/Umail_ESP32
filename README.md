uMail_ESP (Enhanced)

A lightweight SMTP client for MicroPython, originally developed by Shawwwn and enhanced for improved reliability and functionality. This version builds on the foundation of uMail to support robust email and SMS sending (via email-to-SMS gateways) from devices like the ESP32, with no subscription services required.
Acknowledgments

This project is based on the excellent work of Shawwwn from the uMail repository, released under the MIT License in 2018. The original umail.py provided a simple, effective SMTP client for MicroPython, and this fork extends it with additional features and improvements while preserving its lightweight design. Thank you, Shawwwn, for the foundational code!
Updates and Enhancements

The enhanced umailesp.py includes the following improvements over the original:

    Better Error Handling:
        Replaced assert statements with raise Exception—prevents crashes and allows calling scripts to handle errors gracefully.
        Added debug prints for all SMTP commands (e.g., SMTP: EHLO -> 250 ...)—aids troubleshooting without external tools.
    Retry Logic:
        Added a configurable retry mechanism in to() (default: 3 retries, 5s delay)—improves reliability over unstable Wi-Fi connections, common in battery-powered setups like the ESP32 with TP4056.
    Configurable Timeout:
        Introduced a timeout parameter in __init__ (default: 10s, adjustable)—allows tuning for slower networks, enhancing compatibility with real-world conditions.
    MIME Support:
        Added optional mime=True in send()—inserts basic MIME headers (text/plain; charset=UTF-8) for proper email formatting and future extensibility (e.g., logs or attachments).
    Memory Optimization:
        Optimized cmd() to return a single-string response list—reduces RAM usage slightly, critical for memory-constrained MicroPython devices like the ESP32.
    Documentation:
        Added comprehensive docstrings and inline comments—makes the code GitHub-friendly and maintainable for future contributors.

Usage
Requirements

    MicroPython firmware on your device (tested with v1.24.1 on ESP32; SSL support required for Gmail).
    Wi-Fi connectivity (e.g., ESP32 in STA mode).
    An SMTP-enabled email account (e.g., Gmail with a 16-digit app password).

Installation

    Download umailesp.py from this repository.
    Upload it to your MicroPython device’s filesystem:
        Using Thonny: File > Save As > MicroPython Device > umailesp.py.
        Or via ampy: ampy --port /dev/ttyUSB0 put umailesp.py.

Example: Sending BME280 Readings

This example sends temperature, humidity, and pressure readings from a BME280 sensor via email and SMS using an ESP32:
python
import time
from machine import Pin, I2C
import network
import bme280
import ssd1306
import umailesp32  # Note: Rename to match your file

# Wi-Fi config
SSID = "your_ssid"
PASSWORD = "your_password"

# SMTP config
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 465  # Use 465 for SSL (recommended) or 587 for STARTTLS
SENDER_EMAIL = "your.email@gmail.com"
SENDER_PASSWORD = "your_app_password"  # Gmail 16-digit app password
RECIPIENT_EMAIL = "recipient@example.com"
SMS_GATEWAY = "1234567890@vtext.com"  # Replace with your number@carrier-gateway

# Connect to Wi-Fi
def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if not wlan.isconnected():
        wlan.connect(SSID, PASSWORD)
        timeout = 10
        while not wlan.isconnected() and timeout > 0:
            time.sleep(1)
            timeout -= 1
    return wlan.isconnected(), wlan.ifconfig()[0] if wlan.isconnected() else "Wi-Fi Failed"

# Initialize I2C
i2c_oled = I2C(0, scl=Pin(4), sda=Pin(5))
oled = ssd1306.SSD1306_I2C(128, 64, i2c_oled, addr=0x3C)
i2c_bme = I2C(1, scl=Pin(15), sda=Pin(2))
sensor = bme280.BME280(i2c=i2c_bme, address=0x76)

# Boot
oled.fill(0)
oled.text("Booting...", 10, 20)
oled.show()
time.sleep(2)

wifi_ok, wifi_status = connect_wifi()
oled.fill(0)
oled.text("Wi-Fi:", 10, 5)
oled.text(wifi_status[:12], 10, 20)
oled.show()
time.sleep(2)

# Main loop
while True:
    try:
        temp, pressure, humidity = sensor.values
        temp_c = float(temp[:-1])
        pressure_hpa = float(pressure[:-3])
        humidity_pct = float(humidity[:-1])

        oled.fill(0)
        oled.text(f"Temp: {temp_c:.1f} C", 10, 5)
        oled.text(f"Hum: {humidity_pct:.1f} %", 10, 20)
        oled.text(f"Pres: {pressure_hpa:.0f} hPa", 10, 35)
        oled.text("Wi-Fi: OK" if wifi_ok else "Wi-Fi: NO", 10, 50)
        oled.show()

        if wifi_ok:
            client = umailesp32.SMTP(SMTP_SERVER, SMTP_PORT, ssl=True, 
                                    username=SENDER_EMAIL, password=SENDER_PASSWORD, 
                                    timeout=30)
            
            # Email
            subject = "BME280 Readings"
            body = f"Temp: {temp_c:.1f} C\nHumidity: {humidity_pct:.1f} %\nPressure: {pressure_hpa:.0f} hPa"
            client.to(RECIPIENT_EMAIL)
            client.write(f"From: ESP32 <{SENDER_EMAIL}>\n")
            client.write(f"To: {RECIPIENT_EMAIL}\n")
            client.write(f"Subject: {subject}\n")
            client.send(body, mime=True)
            
            # SMS
            sms_body = f"T:{temp_c:.1f}C H:{humidity_pct:.1f}% P:{pressure_hpa:.0f}hPa"
            client.to(SMS_GATEWAY)
            client.write(f"From: ESP32 <{SENDER_EMAIL}>\n")
            client.write(f"To: {SMS_GATEWAY}\n")
            client.write("Subject: BME280\n")
            client.send(sms_body, mime=True)
            
            client.quit()

    except Exception as e:
        oled.fill(0)
        oled.text("Error:", 10, 5)
        oled.text(str(e)[:12], 10, 20)
        oled.show()
        print("Error:", e)

    time.sleep(3600)  # Hourly
Notes:

    Port: Changed to 465 (SSL) from 587 (STARTTLS) to match your latest working config.
    Module Name: Updated to umailesp32—rename your file accordingly.
    SMS Gateway: Replace 1234567890@vtext.com with your carrier’s gateway (e.g., Verizon: number@vtext.com, AT&T: number@txt.att.net).

Configuration Tips

    Gmail: Enable 2-factor authentication and generate an app password at Google Account Security.
    Timeout: Increase to 30s (timeout=30) for slow networks.
    SSL: Use port 465 with ssl=True for direct SSL (simpler); use 587 with ssl=False for STARTTLS if preferred.

Contributing

Feel free to fork, submit pull requests, or open issues! This project aims to remain lightweight and practical for ESP32 users.
License

MIT License, per the original uMail project. See LICENSE file for details.
