# Mosquitto Local Setup Guide — Windows

## 1. Download Mosquitto

Download Eclipse Mosquitto for Windows from the official website:

```text
https://mosquitto.org/download/
```

Or directly from the Windows 64-bit binary directory:

```text
https://mosquitto.org/files/binary/win64/
```

Choose the latest installer with a name similar to:

```text
mosquitto-x.x.x-install-windows-x64.exe
```

---

## 2. Install Mosquitto

Run the downloaded `.exe` installer.

It is recommended to keep the default installation directory:

```text
C:\Program Files\mosquitto\
```

After installation, this folder should contain files such as:

```text
C:\Program Files\mosquitto\
│
├── mosquitto.exe
├── mosquitto_pub.exe
├── mosquitto_sub.exe
├── mosquitto.conf
└── ...
```

The main tools are:

```text
mosquitto.exe
mosquitto_pub.exe
mosquitto_sub.exe
```

---

## 3. Verify Installation

Open PowerShell and run:

```powershell
& "C:\Program Files\mosquitto\mosquitto.exe" -h
```

If Mosquitto is installed correctly, the command will display help and version information.

---

## 4. Start Mosquitto Locally

Run:

```powershell
& "C:\Program Files\mosquitto\mosquitto.exe" -v
```

The `-v` option enables verbose logging.

Expected output should contain something similar to:

```text
mosquitto version ...
Opening ipv4 listen socket on port 1883.
```

The default MQTT port is:

```text
1883
```

Keep this terminal open while testing.

---

## 5. Test Subscriber

Open a second PowerShell window.

Run:

```powershell
& "C:\Program Files\mosquitto\mosquitto_sub.exe" -h localhost -p 1883 -t "test/chat"
```

This terminal will wait for messages published to:

```text
test/chat
```

---

## 6. Test Publisher

Open a third PowerShell window.

Run:

```powershell
& "C:\Program Files\mosquitto\mosquitto_pub.exe" -h localhost -p 1883 -t "test/chat" -m "hello mqtt"
```

The subscriber terminal should immediately display:

```text
hello mqtt
```

If this happens, Mosquitto is working correctly on the local machine.

---

## 7. Add Mosquitto to Windows PATH

This step is optional but recommended.

Without PATH, commands must use the full path:

```powershell
& "C:\Program Files\mosquitto\mosquitto.exe" -v
```

After adding Mosquitto to PATH, you can simply use:

```bash
mosquitto -v
```

```bash
mosquitto_sub
```

```bash
mosquitto_pub
```

### Add to PATH

Open:

```text
Start
→ Search "Environment Variables"
→ Edit the system environment variables
→ Environment Variables
```

Find:

```text
Path
```

Choose:

```text
Edit
```

Add:

```text
C:\Program Files\mosquitto\
```

Save the changes.

Close and reopen PowerShell.

Verify:

```bash
mosquitto -h
```

---

## 8. Check Port 1883

To check whether Mosquitto is listening on port `1883`, run:

```powershell
netstat -ano | findstr :1883
```

Expected output is similar to:

```text
TCP    127.0.0.1:1883    0.0.0.0:0    LISTENING
```

or:

```text
TCP    0.0.0.0:1883    0.0.0.0:0    LISTENING
```

---

## 9. Mosquitto Windows Service

Mosquitto may also be installed as a Windows service.

Press:

```text
Win + R
```

Run:

```text
services.msc
```

Look for:

```text
Mosquitto Broker
```

The service can be:

```text
Start
Stop
Restart
```

For local development and testing, running Mosquitto manually with:

```bash
mosquitto -v
```

is convenient because the broker logs remain visible.

---

## 10. Common Errors

### `mosquitto` is not recognized

Example:

```text
'mosquitto' is not recognized as an internal or external command
```

Either use the full path:

```powershell
& "C:\Program Files\mosquitto\mosquitto.exe" -v
```

or add:

```text
C:\Program Files\mosquitto\
```

to Windows PATH.

---

### Port 1883 is already in use

Check:

```powershell
netstat -ano | findstr :1883
```

If another process is already listening on `1883`, Mosquitto may already be running.

Do not start another broker on the same port.

---

### Connection refused

If `mosquitto_pub` or `mosquitto_sub` reports connection refused:

1. Make sure Mosquitto is running.
2. Make sure the port is `1883`.
3. Use `localhost` or `127.0.0.1`.
4. Check Windows Firewall if necessary.

Example:

```bash
mosquitto_sub -h localhost -p 1883 -t "test/chat"
```

---

## 11. Final Local Configuration

After setup, the local Mosquitto broker should be available at:

```text
Host: localhost
Port: 1883
```

or:

```text
127.0.0.1:1883
```

Basic local test flow:

```text
mosquitto_pub
      │
      │ test/chat
      ▼
Mosquitto Broker
 localhost:1883
      │
      │ test/chat
      ▼
mosquitto_sub
```

---

## 12. Setup Checklist

- [ ] Download Mosquitto installer
- [ ] Install Mosquitto
- [ ] Verify `mosquitto.exe`
- [ ] Start broker using `mosquitto -v`
- [ ] Verify port `1883`
- [ ] Test `mosquitto_sub`
- [ ] Test `mosquitto_pub`
- [ ] Confirm subscriber receives `hello mqtt`
- [ ] Add Mosquitto to PATH (optional)
- [ ] Check Mosquitto Windows service (optional)

Once the publish/subscribe test works, Mosquitto is successfully installed and running locally.
