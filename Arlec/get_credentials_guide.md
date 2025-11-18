# Getting Your Arlec Device Credentials - Simple Guide

You need 3 pieces of information:
1. **Device ID** - Unique identifier
2. **IP Address** - Local network address
3. **Local Key** - Encryption key

## Method 1: Smart Life App + Chrome DevTools (EASIEST)

This is the simplest way that doesn't require Tuya IoT account setup:

### Step 1: Find IP Address

**Option A: Check Your Router**
1. Open your router admin (usually 192.168.1.1 or 192.168.86.1)
2. Look for "Connected Devices" or "DHCP Clients"
3. Find your Arlec device (might show as "Smart Plug" or manufacturer "Espressif" or "Tuya")
4. Note the IP address (e.g., 192.168.1.123)

**Option B: Use Smart Life App**
1. Open Smart Life app
2. Select your Arlec device
3. Tap Settings (gear icon)
4. Look for "Device Information" or "Network Info"
5. Note the IP address

### Step 2: Get Device ID and Local Key Using Chrome

**This is the KEY step:**

1. **Open Smart Life Web App**
   - Go to: https://iot.tuya.com/ (or https://smartlife.tuya.com/)
   - Log in with your Smart Life app credentials

2. **Open Chrome Developer Tools**
   - Press `F12` or `Ctrl+Shift+I`
   - Go to "Network" tab

3. **View Your Devices**
   - In the Smart Life web interface, navigate to your devices
   - Click on your Arlec plug

4. **Find the API Call**
   - In the Network tab, look for API calls with names like:
     - `devices`
     - `device/list`
     - `device/info`
   - Click on the API call
   - Go to "Response" tab

5. **Extract Credentials**
   - Look for your device in the JSON response
   - Find these fields:
     ```json
     {
       "id": "bf1234567890abcdef",        // This is DEVICE_ID
       "local_key": "a1b2c3d4e5f6g7h8",   // This is LOCAL_KEY
       "ip": "192.168.1.123"               // This is IP_ADDRESS
     }
     ```
   - Copy these values!

## Method 2: Use TinyTuya Wizard (REQUIRES TUYA IOT ACCOUNT)

If you want the automated approach:

1. **Create Tuya IoT Account**
   - Go to: https://iot.tuya.com/
   - Sign up (use same email as Smart Life app)

2. **Create Cloud Project**
   - Click "Cloud" → "Development"
   - Click "Create Cloud Project"
   - Region: Choose closest to you (US, EU, etc.)
   - Name: "Smart Home Control"
   - Industry: "Smart Home"
   - Development Method: "Smart Home"
   - Click "Create"

3. **Link Your App**
   - Go to "Devices" tab in your project
   - Click "Link Tuya App Account"
   - Click "Add App Account"
   - Scan QR code with Smart Life app
   - Your devices will appear

4. **Get API Credentials**
   - In your project, go to "Overview"
   - Copy:
     - Access ID/Client ID (API Key)
     - Access Secret/Client Secret (API Secret)

5. **Run TinyTuya Wizard**
   ```bash
   python -m tinytuya wizard
   ```
   - Enter your API Key
   - Enter your API Secret
   - Select your region
   - The wizard will discover devices and extract all credentials

## Method 3: Android App - "Tuya Smart Life Local Key Extract"

There are Android apps that can show the Local Key directly:

1. Search Play Store for "Tuya Local Key" apps
2. Log in with your Smart Life credentials
3. The app will show Device ID, IP, and Local Key for all your devices

## Method 4: Network Packet Capture (ADVANCED)

If you're comfortable with network tools:

1. Use Wireshark or tcpdump
2. Filter for traffic to/from your device's IP
3. Capture the initial handshake when device connects
4. The Local Key is transmitted during pairing

## After Getting Credentials

Once you have all three pieces of information:

1. **Update `IoS_logins.py`:**
   ```python
   ARLEC_DEVICE_ID = "bf1234567890abcdef"  # Your Device ID
   ARLEC_DEVICE_IP = "192.168.1.123"        # Your IP Address
   ARLEC_LOCAL_KEY = "a1b2c3d4e5f6g7h8"    # Your Local Key
   ```

2. **Test the connection:**
   ```bash
   python arlec_test.py
   ```

3. **Use the controller:**
   ```bash
   python arlec_controller.py
   ```

## Troubleshooting

### Can't Find Device on Network?
- Make sure it's plugged in and the LED is on
- Check if it's connected to WiFi in the Smart Life app
- Your computer and device must be on the same WiFi network

### Can't Get Local Key?
- The Local Key changes if you remove and re-add the device
- Try Method 1 (Chrome DevTools) - it's the most reliable
- As a last resort, reset the device and re-pair it while packet capturing

### Still Stuck?
- Check if your device is actually a Tuya-based device
- Some Arlec models might use different protocols
- Verify the device works in the Smart Life/Tuya app first

## Quick Reference

**What you need:**
```
DEVICE_ID:  bf1234567890abcdef (about 20 characters)
IP_ADDRESS: 192.168.1.xxx
LOCAL_KEY:  a1b2c3d4e5f6g7h8 (usually 16 characters)
```

**Where to put it:**
```
File: C:\Projects\plug\IoS_logins.py
Lines: 17-19
```

**How to test:**
```bash
cd C:\Projects\plug\Arlec
python arlec_test.py
```
