# USB Network Share V3 - Professional Edition

Share USB devices (COM ports and webcams) over a local network with **automatic discovery, TLS encryption, priority queuing, and persistent configuration**.

## 🌟 What's New in V3

### 🔍 Automatic Server Discovery
- **Zero-configuration networking** using mDNS/Bonjour
- Servers automatically appear in client list
- No need to remember IP addresses
- One-click connection to discovered servers

### 🔒 TLS Encryption
- **Optional TLS 1.2+ encryption** for all traffic
- Protects against eavesdropping on local network
- Simple checkbox to enable/disable
- Self-signed certificate support

### 💾 Configuration Persistence
- **All settings automatically saved** and restored
- Remembers last used devices, servers, and preferences
- Platform-specific config storage
- No more re-entering settings on restart

### ⚡ Priority Command Queue
- **Emergency commands execute immediately** (bypass queue)
- G-code commands get high priority
- Status queries use low priority
- Prevents command delays during heavy load

### 📊 Enhanced Metrics
- **Detailed latency statistics** (min/max/average)
- Packet counters (sent/received)
- Command queue depth monitoring
- Frame rate tracking

## 🚀 Quick Start

### Installation

```bash
# Install dependencies
pip install -r requirements_v3.txt
```

**New in V3:** Requires `zeroconf` package for automatic discovery (optional but recommended)

### First Time Setup

**On Computer B (Laser Room - Server):**
1. Run: `python usb_network_share_server_v3.py`
2. Select your laser's COM port and camera
3. Give your server a friendly name (e.g., "Laser-Workshop")
4. Check "Enable mDNS discovery" ✓ (recommended)
5. Optionally check "Use TLS encryption" for security
6. Click "▶ Start Server"
7. Server starts and announces itself on network

**On Computer A (Office - Client):**
1. Run: `python usb_network_share_client_v3.py`
2. Look in "🔍 Discovered Servers" list
3. Click your server name to auto-fill connection details
4. Enter virtual COM port (COM10)
5. Match TLS setting to server (if server uses TLS, enable it here too)
6. Check "Auto-reconnect" ✓ (recommended)
7. Click "🔌 Connect to Server"
8. All settings automatically saved for next time!

## 📋 Key Features

### Server Features
- 📡 **mDNS broadcasting** - Announces presence on network
- 🏷️ **Custom server name** - Easy identification
- 🔒 **TLS encryption** - Optional secure communication
- ⚡ **Priority queue** - Emergency stops never wait
- 📊 **Queue monitoring** - See command backlog
- 💾 **Auto-save config** - Settings persist across restarts
- 🔄 **Device memory** - Remembers last used COM port/camera
- 📈 **Enhanced stats** - Packets sent/received, queue depth

### Client Features
- 🔍 **Auto-discovery** - Finds servers automatically
- 🖱️ **One-click connect** - Select from discovered list
- 🔒 **TLS support** - Matches server encryption
- 🔄 **Auto-reconnect** - With exponential backoff (from V2)
- 💾 **Config persistence** - Never re-enter settings
- 📊 **Detailed metrics** - Min/max/avg latency tracking
- 🎥 **Camera streaming** - Same efficient JPEG from V2
- ❤️ **Heartbeat monitor** - 15-second detection (from V2)

## 🎯 Using with Lightburn

### Setup Process

1. **Start Server** (one-time setup)
   - Select laser COM port and camera
   - Name your server: "Laser-Workshop"
   - Enable mDNS discovery
   - Optionally enable TLS for security
   - Click "▶ Start Server"
   - Configuration saved automatically

2. **Start Client** (one-time setup)
   - Select "Laser-Workshop" from discovered servers (or enter IP manually)
   - Enter COM10 as virtual port
   - Match TLS setting (if server uses TLS)
   - Enable auto-reconnect
   - Click "🔌 Connect to Server"
   - Configuration saved automatically

3. **Configure Lightburn** (one-time)
   - Open Lightburn
   - Edit → Device Settings
   - Add device using COM10
   - Test connection

4. **Daily Use**
   - Just start server and client - they remember everything!
   - Server appears in client's discovery list automatically
   - One-click connection
   - Auto-reconnects if network drops

## 🔍 Device Discovery Details

### How It Works

**Server Side:**
- Broadcasts service info using mDNS protocol
- Service name: `<your-server-name>._usb-share._tcp.local.`
- Includes server name, IP, port, and TLS status
- Automatically announces when server starts
- Removes announcement when server stops

**Client Side:**
- Listens for `_usb-share._tcp.local.` services
- Populates "Discovered Servers" list
- Shows server name, IP, and port
- Updates in real-time as servers appear/disappear
- Click any server to auto-fill connection details

### Manual Fallback

If discovery isn't working:
1. Manually enter server IP in client
2. Works exactly like V2
3. Settings still saved automatically
4. All other features work normally

## 🔒 TLS Encryption

### When to Use TLS

**Use TLS if:**
- Operating on untrusted network (shared WiFi, etc.)
- Handling sensitive data or commands
- Company security policy requires encryption
- Operating over WAN/Internet (not recommended generally)

**Skip TLS if:**
- Using dedicated/isolated network
- Minimizing latency is critical (adds 2-5ms)
- Testing/development environment
- Trusted home network

### How to Enable

**Server:**
1. Check "Use TLS encryption"
2. Start server

**Client:**
1. Check "Use TLS encryption"
2. Connect to server

**Important:** Both must agree! Server with TLS cannot accept client without TLS and vice versa.

### Performance Impact

- Adds 2-5ms latency per command
- Negligible for most use cases
- Still much faster than non-TCP_NODELAY implementations
- Acceptable for laser engraving, CNC, etc.

## ⚡ Priority Command Queue

### Priority Levels

**Emergency (Priority 0):**
- `M112` - Emergency stop
- `!` - Feed hold
- Safety interlock commands
- **Executes immediately**, bypasses queue

**High (Priority 1):**
- G-code motion commands: `G0`, `G1`, `G2`, `G3`
- M-code laser/spindle control: `M3`, `M5`
- Critical operation commands

**Normal (Priority 5):**
- Regular serial data
- Non-G/M commands
- General communication

**Low (Priority 10):**
- `?` - Status queries
- Non-critical info requests
- Background polling

### How It Works

1. Commands enter priority queue when received
2. Queue processor pulls highest priority first
3. Emergency commands bypass queue entirely
4. Prevents status queries from delaying G-code
5. Queue depth monitored and displayed

### Monitoring Queue

- Check "Command Queue" statistic on server
- Normal: 0-5 commands
- High load: 5-20 commands
- Overload: 20+ commands (may need to slow down)

## 💾 Configuration Files

### Location

**Windows:**
- Server: `%APPDATA%\USBNetworkShare\server_config.json`
- Client: `%APPDATA%\USBNetworkShare\client_config.json`

**Linux/Mac:**
- Server: `~/.config/usb_network_share/server_config.json`
- Client: `~/.config/usb_network_share/client_config.json`

### What's Saved

**Server Config:**
```json
{
  "server_name": "Laser-Workshop",
  "server_port": 5555,
  "use_tls": false,
  "enable_discovery": true,
  "last_serial_port": "COM3",
  "last_camera_index": 0
}
```

**Client Config:**
```json
{
  "server_ip": "192.168.1.100",
  "server_port": 5555,
  "virtual_com_port": "COM10",
  "auto_reconnect": true,
  "use_tls": false,
  "auto_discover": true,
  "last_server_name": "Laser-Workshop"
}
```

### Manual Editing

- Files are human-readable JSON
- Safe to edit manually if needed
- Restart application to reload
- Delete file to reset to defaults

## 📊 Understanding Statistics

### Server Statistics

**Clients:** Number of currently connected clients

**Uptime:** How long server has been running

**Sent / Received:** Total data transferred (MB)

**Packets:** Individual messages sent/received (useful for troubleshooting)

**Command Queue:** Current number of queued serial commands
- 0 = Idle
- 1-5 = Normal operation
- 5-20 = Heavy load
- 20+ = Overload (consider slowing down)

### Client Statistics

**Connected:** Time connected to server

**Latency:** Current round-trip ping time
- Also shows average, min, and max over last 100 pings
- Normal: 1-5ms on wired LAN
- Acceptable: 5-20ms on WiFi
- High: 20ms+ (check network)

**Sent / Received:** Data transferred (MB)

**Packets:** Messages sent/received

**Reconnections:** Number of times auto-reconnect activated
- 0 = Stable connection
- 1-2 = Occasional network hiccup
- Many = Network problems (investigate)

## 🛠️ Troubleshooting

### Device Discovery Issues

**No servers appear in list:**
```
Possible causes:
✓ Different networks (VPN, guest network, etc.)
✓ Firewall blocking mDNS (port 5353 UDP)
✓ Server doesn't have "Enable mDNS discovery" checked
✓ zeroconf package not installed

Solutions:
1. Check both computers on same network
2. Click "🔄 Refresh Discovery"  
3. Disable firewall temporarily to test
4. Fall back to manual IP entry
5. Check server has mDNS enabled
```

**Server appears but can't connect:**
```
Possible causes:
✓ TLS settings mismatch
✓ Firewall blocking server port
✓ Discovery showing stale server

Solutions:
1. Verify TLS checkbox matches on both
2. Try manual IP entry to rule out discovery
3. Check firewall allows port 5555 (TCP)
4. Restart both applications
```

### TLS Issues

**"TLS handshake failed":**
```
Possible causes:
✓ TLS enabled on one side only
✓ Certificate problems (if using real certs)
✓ Network proxy interfering

Solutions:
1. Check both have "Use TLS encryption" checked
2. Or uncheck both to disable TLS
3. Check logs for detailed error
4. Try connection without TLS first
```

**Connection slower with TLS:**
```
This is normal!
✓ TLS adds 2-5ms per command
✓ Still much faster than V1
✓ Acceptable for most uses

If critical:
- Disable TLS
- Use wired connection
- Only use TLS on untrusted networks
```

### Configuration Issues

**Settings not saving:**
```
Possible causes:
✓ No write permission to config directory
✓ Disk full
✓ Anti-virus blocking file writes

Solutions:
1. Run as Administrator (Windows)
2. Check disk space
3. Check anti-virus logs
4. Manually create config directory
```

**Settings reset on restart:**
```
Possible causes:
✓ Config file being deleted
✓ Application reading wrong location
✓ File permissions issue

Solutions:
1. Check config file location (see above)
2. Verify file exists after closing app
3. Check file permissions
4. Look for errors in log file
```

### Priority Queue Issues

**Commands delayed:**
```
Possible causes:
✓ Queue backing up (high load)
✓ Serial port slow
✓ Many status queries

Solutions:
1. Check queue depth statistic
2. Reduce status query frequency
3. Emergency stops always work (Priority 0)
4. G-code gets priority over queries
```

**Emergency stop delayed:**
```
This should NEVER happen!
✓ Emergency stops bypass queue
✓ Should execute within 5-10ms

If delayed:
1. Check logs for errors
2. Report as bug
3. Check serial port responsive
```

### Network Issues

**High latency:**
```
Possible causes:
✓ WiFi connection
✓ Network congestion
✓ Long distance
✓ VPN/proxy

Solutions:
1. Use wired Ethernet (best)
2. Move closer to router (WiFi)
3. Check for interference
4. Disable VPN
5. Check for other network activity
```

**Frequent disconnections:**
```
Possible causes:
✓ Unstable network
✓ WiFi power saving
✓ Router issues

Solutions:
1. Enable auto-reconnect (should already be on)
2. Use wired connection
3. Disable WiFi power saving
4. Check router logs
5. Try different port
```

## 🔧 Advanced Configuration

### Custom Server Port

Change from default 5555:
1. Edit port in server before starting
2. Server announces new port via mDNS
3. Client discovers automatically
4. Or manually enter port on client

### Multiple Servers

Run multiple servers:
1. Use different ports (5555, 5556, etc.)
2. Use different server names
3. Both appear in client discovery
4. Each tracks own statistics

### Firewall Configuration

**Windows Firewall:**
```powershell
# Allow mDNS (discovery)
New-NetFirewallRule -DisplayName "mDNS" -Direction Inbound -Protocol UDP -LocalPort 5353 -Action Allow

# Allow USB Share Server
New-NetFirewallRule -DisplayName "USB Share Server" -Direction Inbound -Protocol TCP -LocalPort 5555 -Action Allow
```

**Linux (ufw):**
```bash
# Allow mDNS
sudo ufw allow 5353/udp

# Allow USB Share Server  
sudo ufw allow 5555/tcp
```

## 📈 Performance Benchmarks

### Typical Performance (Gigabit Ethernet)

| Metric | No TLS | With TLS |
|--------|--------|----------|
| Serial Latency | 5-10ms | 7-15ms |
| Heartbeat RTT | 1-5ms | 3-8ms |
| Video Frame Latency | 100-200ms | 100-200ms |
| Command Queue Processing | <1ms | <1ms |
| Discovery Time | 1-5s | 1-5s |
| Reconnection Time | 1-3s | 2-4s |

### Resource Usage

| Resource | V2 | V3 | Notes |
|----------|----|----|-------|
| CPU (idle) | 3-6% | 4-7% | +1% for discovery |
| RAM | 50-100MB | 60-120MB | +20MB for tracking |
| Network (idle) | <1 Kbps | <2 Kbps | +1 Kbps for mDNS |
| Disk | 0 | ~10KB | Config files |

## 🔄 Upgrading from V2

### Migration Steps

1. **Install new dependencies:**
   ```bash
   pip install -r requirements_v3.txt
   ```

2. **Replace files:**
   - Use `usb_network_share_server_v3.py` instead of V2
   - Use `usb_network_share_client_v3.py` instead of V2
   - Keep V2 files as backup if desired

3. **First run:**
   - Re-enter your settings (one time only)
   - Enable mDNS discovery if desired
   - Optionally enable TLS
   - Settings saved automatically for future

4. **That's it!**
   - Protocol remains compatible
   - All V2 reliability features preserved
   - New features automatically available

### What Changes

**Better:** 
- No more re-entering settings
- Automatic server discovery
- Better statistics
- Optional encryption

**Same:**
- Connection reliability
- Auto-reconnection
- Heartbeat monitoring
- Performance

**Different:**
- Config files in new location
- One new dependency (zeroconf)
- Slightly higher resource use

## 📚 Technical Details

### Protocol Compatibility

V3 maintains V2 protocol compatibility:
- Same length-prefix framing
- Same command structure
- Same PING/PONG heartbeat
- V3 client can connect to V2 server (without new features)
- V2 client can connect to V3 server (without new features)

**TLS breaks compatibility:** V3 with TLS cannot talk to V2

### mDNS Service Details

**Service Type:** `_usb-share._tcp.local.`

**Service Name:** `<server-name>._usb-share._tcp.local.`

**Properties:**
- `version`: "3.0"
- `tls`: "true" or "false"

**Port:** Configurable (default 5555)

### Priority Queue Implementation

**Data Structure:** Python's `PriorityQueue` (heap-based)

**Priority Values:**
- Emergency: 0 (highest)
- High: 1
- Normal: 5  
- Low: 10 (lowest)

**Thread Safety:** Built-in locks

**Max Size:** 100 commands (configurable)

**Overflow Behavior:** Blocks until space available

## 🎯 Best Practices

### For Best Performance

1. ✅ Use wired Ethernet connection
2. ✅ Enable auto-reconnect
3. ✅ Enable mDNS discovery
4. ✅ Monitor latency statistics
5. ✅ Keep queue depth low (<10)
6. ❌ Don't use TLS unless needed
7. ❌ Don't poll status too frequently

### For Best Security

1. ✅ Enable TLS encryption
2. ✅ Use isolated network if possible
3. ✅ Monitor connected clients
4. ✅ Check logs regularly
5. ❌ Don't expose to internet
6. ❌ Don't use on untrusted networks without TLS

### For Best Reliability

1. ✅ Enable auto-reconnect
2. ✅ Use wired connection
3. ✅ Monitor reconnection count
4. ✅ Check heartbeat latency
5. ✅ Keep applications updated
6. ❌ Don't ignore high latency warnings
7. ❌ Don't overload command queue

## 🚧 Known Limitations

1. **Single Device:** Each instance shares one COM port (same as V2)
2. **Windows Only:** Virtual COM ports require Windows
3. **Local Network:** Designed for LAN, not WAN
4. **TLS Certificates:** Uses self-signed (not CA-signed)
5. **mDNS Scope:** Local network only (by design)
6. **No Authentication:** Future feature (see roadmap)
7. **Camera Latency:** 100-200ms typical (acceptable for alignment)

## 🗺️ Future Roadmap

See CHANGELOG_V3.md for complete roadmap.

**High Priority (V4):**
- Multi-factor authentication
- Device whitelisting
- Audit logging
- Certificate management

**Medium Priority (V4-V5):**
- Multiple device support
- True H.264 video encoding
- Web control panel
- System tray integration

**Low Priority (V5+):**
- Cross-platform virtual COM ports
- WebRTC for ultra-low latency
- Mobile app

## 📄 License

MIT License - See LICENSE file for details

## 🙏 Credits

**Built with:**
- Python 3.x
- PySerial - COM port communication
- OpenCV - Camera handling
- Pillow - Image processing
- ttkbootstrap - Modern UI
- zeroconf - mDNS/Bonjour discovery
- Tkinter - GUI foundation

**Inspired by:**
- VirtualHere, USB Network Gate, FlexiHub
- Bonjour/Avahi networking
- Modern Python development practices

---

**Version:** 3.0  
**Status:** Production Ready  
**Date:** 2025  
**Compatibility:** V2 protocol (without TLS)

**Questions?** Check CHANGELOG_V3.md for detailed changes or open an issue.

**Enjoy your professional-grade USB sharing! 🎉**
