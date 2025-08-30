# TAK Server Meshtastic Plugin

A TAK Server interceptor plugin that bridges TAK Server with Meshtastic mesh networks, enabling CoT (Cursor on Target) message transmission over LoRa mesh radios.

## Overview

This plugin intercepts CoT messages containing a `__meshtastic` detail element and forwards them to connected Meshtastic devices via the mesh network. This enables TAK clients to communicate over long-range, low-power LoRa networks without requiring internet connectivity.

## Features

- **Message Interception**: Automatically detects and processes CoT messages marked for Meshtastic transmission
- **Multiple Interface Support**: Supports Serial, TCP, and Bluetooth connections to Meshtastic devices
- **Message Compression**: Automatically compresses large CoT messages to fit within Meshtastic's packet size limitations
- **Configurable**: YAML-based configuration for easy customization
- **Statistics Tracking**: Monitors total messages processed and Meshtastic messages sent

## Requirements

- TAK Server 4.10 or later
- Java 17
- Python 3.7+
- Meshtastic Python library (see installation methods below)
- Meshtastic device (serial, TCP, or Bluetooth connected)

### Python Library Installation Methods

**For Debian 12+ / Ubuntu 23.04+ (with PEP 668 restrictions):**
```bash
# Method 1: Using pipx (recommended)
sudo apt-get install pipx
pipx install meshtastic

# Method 2: Using apt (if available)
sudo apt-get install python3-meshtastic

# Method 3: Override system protection (not recommended)
pip3 install --break-system-packages meshtastic
```

**For older systems:**
```bash
pip3 install meshtastic
```

## Quick Start

```bash
# 1. Run setup script (handles permissions and dependencies)
sudo bash setup-meshtastic-permissions.sh

# 2. Deploy plugin files
sudo cp build/libs/takserver-meshtastic-plugin-*.jar /opt/tak/lib/
sudo cp src/main/resources/meshtastic_sender.py /opt/tak/conf/plugins/
sudo cp tak.server.plugins.MeshtasticInterceptorPlugin.yaml /opt/tak/conf/plugins/

# 3. Set permissions
sudo chmod 755 /opt/tak/conf/plugins/meshtastic_sender.py
sudo chown tak:tak /opt/tak/conf/plugins/*

# 4. Restart TAK Server
sudo systemctl restart takserver

# 5. Test (replace /dev/ttyUSB0 with your device)
echo '<event uid="test"/>' | sudo -u tak python3 /opt/tak/conf/plugins/meshtastic_sender.py --interface serial --port /dev/ttyUSB0
```

## Installation

### 1. Run the Setup Script (REQUIRED for Serial/USB Connections)

The setup script configures serial port permissions and installs dependencies:

```bash
# Copy and run the setup script on your TAK Server
sudo bash setup-meshtastic-permissions.sh
```

This script will:
- Detect and configure the TAK Server user
- Add necessary users to the `dialout` group for serial port access
- Create persistent udev rules for device permissions
- Install the Python meshtastic library
- Detect connected Meshtastic devices
- Provide testing commands

**Note**: After running the script, you must restart TAK Server for permission changes to take effect:
```bash
sudo systemctl restart takserver
```

### 2. Deploy Plugin Files

Copy the following files to your TAK Server installation:

```bash
# Copy the plugin JAR
sudo cp build/libs/takserver-meshtastic-plugin-4.10.0-0-0.jar /opt/tak/lib/

# Copy the Python script from resources
sudo cp src/main/resources/meshtastic_sender.py /opt/tak/conf/plugins/

# Copy the configuration file
sudo cp tak.server.plugins.MeshtasticInterceptorPlugin.yaml /opt/tak/conf/plugins/

# Copy the setup script
sudo cp setup-meshtastic-permissions.sh /opt/tak/

# Set appropriate permissions
sudo chmod 755 /opt/tak/conf/plugins/meshtastic_sender.py
sudo chmod 755 /opt/tak/setup-meshtastic-permissions.sh
sudo chown tak:tak /opt/tak/lib/takserver-meshtastic-plugin-4.10.0-0-0.jar
sudo chown tak:tak /opt/tak/conf/plugins/meshtastic_sender.py
sudo chown tak:tak /opt/tak/conf/plugins/tak.server.plugins.MeshtasticInterceptorPlugin.yaml
```

### 3. Configure the Plugin

Edit `/opt/tak/conf/plugins/tak.server.plugins.MeshtasticInterceptorPlugin.yaml`:

```yaml
# Enable/disable the plugin
enabled: true

# Meshtastic interface type: serial, tcp, or ble
interface: serial

# Serial port (for serial interface) or BLE address (for BLE interface)
port: /dev/ttyUSB0

# TCP host (only used for TCP interface)
host: localhost

# Meshtastic channel to use (0-7)
channel: 0

# Log level for the plugin (DEBUG, INFO, WARN, ERROR)
logLevel: INFO
```

#### Interface Configuration Examples

**Serial Connection (USB)**:
```yaml
interface: serial
port: /dev/ttyUSB0  # Linux
# port: /dev/tty.usbserial-0001  # macOS
# port: COM3  # Windows
```

**TCP Connection**:
```yaml
interface: tcp
host: 192.168.1.100  # IP address of device running Meshtastic TCP server
```

**Bluetooth Connection**:
```yaml
interface: ble
port: AA:BB:CC:DD:EE:FF  # Bluetooth MAC address of Meshtastic device
```

### 4. Restart TAK Server

```bash
sudo systemctl restart takserver
```

## Usage

### Sending CoT Messages via Meshtastic

To send a CoT message through the Meshtastic network, include a `__meshtastic` element in the message's detail section:

```xml
<event version="2.0" uid="MESH-001" type="a-f-G-U-C" time="2024-08-29T12:00:00Z" 
       start="2024-08-29T12:00:00Z" stale="2024-08-29T12:05:00Z" how="m-g">
    <point lat="40.0" lon="-105.0" hae="1609.0" ce="10.0" le="10.0"/>
    <detail>
        <contact callsign="MESH-USER-1"/>
        <__meshtastic/>  <!-- This triggers Meshtastic transmission -->
    </detail>
</event>
```

### Message Compression

Due to Meshtastic's packet size limitations (typically ~200 bytes), the plugin automatically compresses large CoT messages into a compact JSON format:

```json
{
  "cot": "1",
  "u": "MESH-001",           // UID (truncated)
  "t": "a-f-G-U-C",          // Type (truncated)
  "la": 40.0,                // Latitude
  "lo": -105.0,              // Longitude
  "c": "MESH-USER-1"         // Callsign (truncated)
}
```

## File Structure

```
takserver-meshtastic-plugin/
├── build/
│   └── libs/
│       └── takserver-meshtastic-plugin-4.10.0-0-0.jar  # Built plugin JAR
├── src/
│   └── main/
│       ├── java/tak/server/plugins/
│       │   └── MeshtasticInterceptorPlugin.java        # Java interceptor
│       └── resources/
│           └── meshtastic_sender.py                    # Python script (deploy this)
├── build.gradle                                        # Build configuration
├── setup-meshtastic-permissions.sh                     # Permission setup script
├── tak.server.plugins.MeshtasticInterceptorPlugin.yaml # Plugin configuration
└── README.md                                           # This file
```

## Architecture

The plugin consists of three main components:

1. **Java Interceptor Plugin** (`MeshtasticInterceptorPlugin.java`)
   - Intercepts TAK Server messages
   - Identifies messages with `__meshtastic` detail
   - Extracts CoT XML
   - Invokes Python script for transmission

2. **Python Meshtastic Bridge** (`src/main/resources/meshtastic_sender.py`)
   - Handles communication with Meshtastic hardware
   - Manages message compression
   - Supports multiple interface types
   - Provides helpful error messages for missing dependencies

3. **Configuration** (`tak.server.plugins.MeshtasticInterceptorPlugin.yaml`)
   - Runtime configuration without recompilation
   - Interface and connection settings
   - Logging configuration

## Monitoring

### Plugin Status

Check the plugin status in the TAK Server admin interface:
```
https://<tak-server>:8443/Marti/plugins/
```

### Logs

Plugin logs are available at:
```bash
# Plugin Java logs
tail -f /opt/tak/logs/takserver-plugins.log

# Python script output (if errors occur)
grep -i meshtastic /opt/tak/logs/takserver-plugins.log
```

### Statistics

The plugin tracks:
- Total messages intercepted
- Messages sent via Meshtastic
- Errors and failures

These statistics are logged when the plugin stops.

## Troubleshooting

### Plugin Not Loading

1. Verify JAR file is in `/opt/tak/lib/`
2. Check file permissions
3. Verify plugin package name starts with `tak.server.plugins`
4. Check `/opt/tak/logs/takserver-plugins.log` for errors

### Meshtastic Connection Issues

1. **Permission Denied Errors**:
   
   If you see `[Errno 13] Permission denied: '/dev/ttyUSB0'`:
   ```bash
   # Run the setup script
   sudo bash /opt/tak/setup-meshtastic-permissions.sh
   
   # Restart TAK Server
   sudo systemctl restart takserver
   
   # Verify user is in dialout group
   groups tak  # Should show 'dialout' in the list
   ```

2. **Verify Meshtastic device is connected**:
   ```bash
   # List serial ports
   ls -la /dev/ttyUSB* /dev/ttyACM*
   
   # Check device permissions (should show group as 'dialout')
   ls -la /dev/ttyUSB0
   # Expected: crw-rw---- 1 root dialout ...
   
   # Check recent USB connections
   sudo dmesg | tail -20
   
   # Test with Meshtastic CLI
   meshtastic --info
   ```

3. **Test as TAK Server user**:
   ```bash
   # Test as the tak user (recommended)
   echo '<event uid="test"/>' | sudo -u tak python3 /opt/tak/conf/plugins/meshtastic_sender.py --interface serial --port /dev/ttyUSB0
   
   # Or temporarily change permissions for testing (not for production)
   sudo chmod 666 /dev/ttyUSB0
   ```

4. **Check Python script permissions**:
   ```bash
   ls -la /opt/tak/conf/plugins/meshtastic_sender.py
   # Should be executable by tak user
   ```

### Message Not Being Sent

1. Verify `__meshtastic` element is present in CoT detail
2. Check plugin is enabled in configuration
3. Monitor logs for interception confirmation
4. Verify Meshtastic device has good signal and network connectivity

### Performance Considerations

- Each intercepted message spawns a Python process (consider pooling for high-volume scenarios)
- Large messages are automatically compressed but may still exceed Meshtastic limits
- Consider message priority and frequency to avoid overwhelming the mesh network

## Development

### Building from Source

```bash
cd takserver-meshtastic-plugin
gradle shadowJar
```

### Testing

Create a test CoT message with `__meshtastic` detail:
```bash
# Send test message to TAK Server
echo '<event version="2.0" uid="TEST-001" type="a-f-G-U-C" time="2024-08-29T12:00:00Z" start="2024-08-29T12:00:00Z" stale="2024-08-29T12:05:00Z" how="m-g"><point lat="40.0" lon="-105.0" hae="1609.0" ce="10.0" le="10.0"/><detail><contact callsign="TEST"/><__meshtastic/></detail></event>' | nc localhost 8087
```

## Limitations

- Maximum message size limited by Meshtastic packet size (~200 bytes after compression)
- Python script execution overhead for each message
- No bidirectional sync (Meshtastic to TAK Server) in current version
- Message delivery confirmation depends on Meshtastic ACK settings

## Future Enhancements

- [ ] Bidirectional message flow (Meshtastic → TAK Server)
- [ ] Message queuing and batching
- [ ] Persistent Python process to reduce overhead
- [ ] Custom message prioritization
- [ ] Encryption support for sensitive data
- [ ] Web UI for configuration and monitoring
- [ ] Support for Meshtastic telemetry data
- [ ] Automatic retry on transmission failure

## License

This plugin is part of the TAK Server SDK examples and follows the same licensing terms.

## Support

For issues related to:
- **TAK Server**: Refer to TAK Server documentation
- **Meshtastic**: Visit [meshtastic.org](https://meshtastic.org)
- **Plugin Issues**: Check the troubleshooting section or file an issue

## Contributing

Contributions are welcome! Please ensure:
1. Code follows TAK Server plugin conventions
2. Tests are included for new features
3. Documentation is updated accordingly

## Version History

- **1.0.0** (2024-08-29): Initial release
  - Basic message interception and forwarding
  - Support for serial, TCP, and BLE interfaces
  - Automatic message compression