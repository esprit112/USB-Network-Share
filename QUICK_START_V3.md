# 🚀 Quick Start Guide - USB Network Share V3

## New User? Start Here!

### Step 1: Install Python Requirements

```bash
pip install -r requirements_v3.txt
```

**What gets installed:**
- `pyserial` - COM port communication
- `opencv-python` - Camera handling
- `Pillow` - Image processing
- `numpy` - Array operations
- `ttkbootstrap` - Modern dark UI theme
- `zeroconf` - Automatic server discovery ⭐ NEW!

### Step 2: Install com0com (Windows)

**On the CLIENT computer only:**

1. Download from: https://sourceforge.net/projects/com0com/
2. Run installer as Administrator
3. Open "Setup Command Prompt" from com0com folder
4. Create virtual COM port pair:
   ```
   install PortName=COM10 PortName=COM11
   ```
5. Verify with: `list`

### Step 3: Run the Applications

**On Computer B (Laser Room - Server):**
```bash
python usb_network_share_server_v3.py
```

**On Computer A (Office - Client):**
```bash
python usb_network_share_client_v3.py
```

### Step 4: Configure Once

**Server (one-time setup):**
1. Select your laser's COM port from dropdown
2. Select camera index (usually 0)
3. Enter a friendly server name: "Laser-Workshop"
4. Check ✓ "Enable mDNS discovery"
5. Leave "Use TLS encryption" unchecked (unless you need it)
6. Click "▶ Start Server"
7. ✅ All settings automatically saved!

**Client (one-time setup):**
1. Look in "🔍 Discovered Servers" list
2. Click "Laser-Workshop" to auto-fill connection
   - OR manually enter server IP if discovery not working
3. Enter "COM10" for virtual COM port
4. Check ✓ "Auto-reconnect"
5. Leave "Use TLS encryption" unchecked (must match server)
6. Click "🔌 Connect to Server"
7. ✅ All settings automatically saved!

### Step 5: Configure Lightburn (one-time)

1. Open Lightburn
2. Edit → Device Settings
3. Add your device
4. Choose COM10 as the port
5. Test connection
6. ✅ Done! You're ready to use!

## Daily Usage

**That's the beauty of V3 - after initial setup, it's effortless:**

1. Start server → It remembers everything
2. Start client → Discovers server automatically
3. Click discovered server → One-click connection
4. Open Lightburn → Just works!

**If network drops:**
- Client auto-reconnects automatically
- No manual intervention needed
- Just keep working!

---

## Upgrading from V2? Read This!

### What's Different

✨ **New Features:**
- Automatic server discovery (no more IP addresses!)
- Settings saved automatically
- Optional TLS encryption
- Priority command queue
- Better statistics

✅ **What Stays the Same:**
- Same reliability and auto-reconnect
- Same performance (5-10ms latency)
- Same COM port and camera setup
- Protocol compatibility (mostly)

### Upgrade Steps

1. **Install new dependency:**
   ```bash
   pip install zeroconf==0.132.2
   ```

2. **Replace your files:**
   - Keep V2 files as backup if you want
   - Use `usb_network_share_server_v3.py`
   - Use `usb_network_share_client_v3.py`

3. **First run:**
   - Re-enter your settings (just once!)
   - V3 will save them automatically
   - Future runs use saved settings

4. **Enjoy new features:**
   - Enable mDNS discovery for auto-find
   - Monitor enhanced statistics
   - Settings persist forever

### Migration Notes

⚠️ **Configuration location changed:**
- V2: Current directory (not saved)
- V3: `%APPDATA%\USBNetworkShare\` (Windows)

📋 **One-time reconfiguration:**
- V3 can't read your V2 settings (they weren't saved)
- Just re-enter once, then never again!

✅ **Protocol compatible:**
- V3 client can talk to V2 server
- V2 client can talk to V3 server
- (Some features won't work, but basic function OK)

---

## Troubleshooting

### "No servers appear in discovery list"

**Try these in order:**

1. **Check mDNS is enabled:**
   - Server: "Enable mDNS discovery" should be checked ✓
   - Click "🔄 Refresh Discovery" on client

2. **Check same network:**
   - Both computers on same WiFi/LAN?
   - Not using VPN or guest network?

3. **Check firewall:**
   - Temporarily disable to test
   - If works, add exception for port 5353 (UDP)

4. **Fall back to manual:**
   - Enter server IP manually
   - Everything else works the same
   - Discovery is just convenience

### "Could not open virtual COM port"

**Follow these steps:**

1. **Verify com0com installed:**
   - Check Programs list for "com0com"
   - Should be on CLIENT computer

2. **Check COM port name:**
   - Open Device Manager
   - Look for "com0com" ports
   - Use exact name shown (COM10, COM11, etc.)

3. **Try running as Administrator:**
   - Right-click Python file
   - "Run as Administrator"

4. **Reinstall com0com:**
   - Uninstall current version
   - Restart computer
   - Install again as Administrator

### "Connection timeout"

**Check these:**

1. **Server running?**
   - Look for "🟢 Running" status
   - Check server log for errors

2. **Firewall blocking?**
   - Allow port 5555 (TCP)
   - Temporarily disable to test

3. **Correct IP/port?**
   - Try discovery auto-fill
   - Verify IP matches server log

4. **TLS mismatch?**
   - Both must have same TLS setting
   - Try with both unchecked

### "Settings not saving"

**Usually permission issue:**

1. **Run as Administrator** (Windows)

2. **Check config location:**
   - Windows: `%APPDATA%\USBNetworkShare\`
   - Should see `.json` files there

3. **Check disk space:**
   - Config files are tiny (~1KB)
   - But zero space = can't write

4. **Check anti-virus:**
   - May block file writes
   - Add exception if needed

---

## Common Questions

### "Do I need zeroconf?"

**Technically no, but strongly recommended:**

✅ **With zeroconf:**
- Servers appear automatically
- One-click connection
- No IP addresses to remember
- Seamless experience

❌ **Without zeroconf:**
- Must enter IP manually
- Otherwise everything works
- Just less convenient

**Install it:** `pip install zeroconf`

### "Should I enable TLS?"

**Depends on your network:**

🔒 **Enable TLS if:**
- Shared/untrusted network
- Company security policy
- Handling sensitive data
- Want extra peace of mind

⚡ **Skip TLS if:**
- Home/trusted network
- Need lowest latency
- Testing/development
- Adds 2-5ms overhead

**Easy to change:** Just checkbox!

### "Can I run multiple servers?"

**Yes!**

1. Use different COM ports on each
2. Use different server ports (5555, 5556...)
3. Give each unique server name
4. All appear in client discovery
5. Connect to whichever you need

### "Can V2 and V3 talk to each other?"

**Mostly yes:**

✅ **Will work:**
- V3 client → V2 server
- V2 client → V3 server  
- Basic functions work fine

❌ **Won't work:**
- TLS (V2 doesn't have it)
- Discovery (V2 doesn't broadcast)
- Priority queue (V2 doesn't have it)

**Best:** Use same version on both sides

---

## Next Steps

📖 **Read full documentation:**
- `README_V3.md` - Complete manual
- `CHANGELOG_V3.md` - What changed from V2
- Research document - Original recommendations

🎯 **Optimize your setup:**
- Enable auto-reconnect
- Monitor latency stats
- Use wired connection for best performance
- Configure Windows Firewall properly

🔒 **Improve security:**
- Enable TLS if on shared network
- Use isolated network if possible
- Don't expose to internet
- Monitor connected clients

📊 **Monitor performance:**
- Watch latency statistics
- Check queue depth
- Monitor reconnection count
- Look for patterns in logs

---

## Getting Help

**Check these first:**
1. 📝 Log files: `usb_server.log`, `usb_client.log`
2. 📊 Statistics display in UI
3. 🔴 Status indicator colors
4. 📖 README_V3.md troubleshooting section

**Still stuck?**
- Check firewall settings
- Verify both on same network
- Try with TLS disabled
- Test manual IP entry
- Look for error messages in logs

**Found a bug?**
- Check logs for details
- Note exact error message
- List steps to reproduce
- Include configuration (remove sensitive data)

---

## Tips for Best Experience

1. ✅ **Enable mDNS discovery** - Makes life easier
2. ✅ **Enable auto-reconnect** - Network drops are no problem
3. ✅ **Use wired Ethernet** - More stable than WiFi
4. ✅ **Monitor statistics** - Know what's happening
5. ✅ **Check logs occasionally** - Catch issues early
6. ❌ **Don't ignore high latency** - Investigate if >20ms
7. ❌ **Don't poll status too fast** - Uses bandwidth
8. ❌ **Don't skip com0com install** - Client won't work

---

**Ready to go? Start with Step 1 above! 🚀**

**Questions?** Check README_V3.md for detailed documentation.

**Enjoy your automatic, persistent, professional USB sharing! 🎉**
