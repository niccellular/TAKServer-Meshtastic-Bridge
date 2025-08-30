#!/bin/bash

# TAK Server Meshtastic Plugin - Serial Port Permission Setup Script
# This script configures the necessary permissions for TAK Server to access Meshtastic devices
# Run with: sudo bash setup-meshtastic-permissions.sh

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}TAK Server Meshtastic Plugin - Permission Setup${NC}"
echo "================================================="
echo ""

# Function to print colored messages
print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    print_error "This script must be run as root (use sudo)"
    exit 1
fi

# Detect TAK Server user
print_info "Detecting TAK Server user..."
TAK_USER=""

# Check common TAK Server users
if id "tak" &>/dev/null; then
    TAK_USER="tak"
elif id "takserver" &>/dev/null; then
    TAK_USER="takserver"
else
    # Try to find from running process
    TAK_PROCESS=$(ps aux | grep -E "takserver|tak-server" | grep -v grep | head -1)
    if [ ! -z "$TAK_PROCESS" ]; then
        TAK_USER=$(echo "$TAK_PROCESS" | awk '{print $1}')
    fi
fi

if [ -z "$TAK_USER" ]; then
    print_warn "Could not auto-detect TAK Server user"
    read -p "Enter the TAK Server user (usually 'tak' or 'takserver'): " TAK_USER
    
    if ! id "$TAK_USER" &>/dev/null; then
        print_error "User $TAK_USER does not exist"
        exit 1
    fi
fi

print_info "TAK Server user detected: $TAK_USER"

# Add TAK user to dialout group
print_info "Adding $TAK_USER to dialout group for serial port access..."
usermod -a -G dialout "$TAK_USER"

if groups "$TAK_USER" | grep -q dialout; then
    print_info "✓ $TAK_USER successfully added to dialout group"
else
    print_error "Failed to add $TAK_USER to dialout group"
    exit 1
fi

# Also add the current sudo user if they exist
if [ ! -z "$SUDO_USER" ] && [ "$SUDO_USER" != "root" ]; then
    print_info "Adding $SUDO_USER to dialout group for testing..."
    usermod -a -G dialout "$SUDO_USER"
    print_info "✓ $SUDO_USER added to dialout group"
fi

# Check for connected Meshtastic devices
print_info "Checking for connected Meshtastic devices..."
echo ""

DEVICE_FOUND=false
DEVICE_PATH=""

# Check for USB serial devices
for device in /dev/ttyUSB* /dev/ttyACM*; do
    if [ -e "$device" ]; then
        DEVICE_FOUND=true
        DEVICE_PATH="$device"
        print_info "Found serial device: $device"
        
        # Get device info
        DEVICE_INFO=$(ls -la "$device")
        echo "  Permissions: $DEVICE_INFO"
        
        # Check if it might be Meshtastic
        if command -v udevadm &> /dev/null; then
            VENDOR=$(udevadm info --query=all --name="$device" 2>/dev/null | grep -E "ID_VENDOR|ID_MODEL" | head -2)
            if [ ! -z "$VENDOR" ]; then
                echo "  Device info:"
                echo "$VENDOR" | sed 's/^/    /'
            fi
        fi
        echo ""
    fi
done

if [ "$DEVICE_FOUND" = false ]; then
    print_warn "No USB serial devices found. Please connect your Meshtastic device."
    echo ""
    echo "Common Meshtastic serial ports:"
    echo "  - /dev/ttyUSB0 (most common for USB serial adapters)"
    echo "  - /dev/ttyACM0 (for native USB devices)"
    echo ""
fi

# Create udev rule for persistent permissions
print_info "Creating udev rule for persistent serial port permissions..."

UDEV_RULE_FILE="/etc/udev/rules.d/99-meshtastic.rules"
cat > "$UDEV_RULE_FILE" << 'EOF'
# Meshtastic devices - grant access to dialout group
# CP2102/CP2104 USB to UART Bridge (common in Meshtastic devices)
SUBSYSTEM=="tty", ATTRS{idVendor}=="10c4", ATTRS{idProduct}=="ea60", MODE="0660", GROUP="dialout"

# CH340 USB to Serial (another common chip)
SUBSYSTEM=="tty", ATTRS{idVendor}=="1a86", ATTRS{idProduct}=="7523", MODE="0660", GROUP="dialout"

# FTDI USB to Serial
SUBSYSTEM=="tty", ATTRS{idVendor}=="0403", ATTRS{idProduct}=="6001", MODE="0660", GROUP="dialout"

# Generic rule for all USB serial devices (less secure but more compatible)
SUBSYSTEM=="tty", KERNEL=="ttyUSB[0-9]*", MODE="0660", GROUP="dialout"
SUBSYSTEM=="tty", KERNEL=="ttyACM[0-9]*", MODE="0660", GROUP="dialout"
EOF

print_info "✓ Created udev rule at $UDEV_RULE_FILE"

# Reload udev rules
print_info "Reloading udev rules..."
udevadm control --reload-rules
udevadm trigger
print_info "✓ Udev rules reloaded"

# Install Python dependencies
print_info "Checking Python dependencies..."

# Detect Debian 12+ with externally managed environment
if [ -f /etc/debian_version ] && python3 -c "import sys; exit(0 if sys.version_info >= (3,11) else 1)" 2>/dev/null; then
    print_info "Detected Debian 12+ with externally managed Python environment"
    
    # Check if pipx is available (preferred method)
    if command -v pipx &> /dev/null; then
        print_info "Installing meshtastic via pipx..."
        pipx install meshtastic --force
        print_info "✓ Meshtastic installed via pipx"
        
        # Create wrapper script for TAK Server to use
        cat > /usr/local/bin/meshtastic-wrapper << 'EOF'
#!/bin/bash
# Wrapper to use pipx-installed meshtastic
export PATH="$HOME/.local/bin:$PATH"
python3 -m meshtastic "$@"
EOF
        chmod 755 /usr/local/bin/meshtastic-wrapper
        
    # Try apt package first
    elif apt-cache show python3-meshtastic &> /dev/null; then
        print_info "Installing meshtastic via apt..."
        apt-get update -qq
        apt-get install -y -qq python3-meshtastic
        print_info "✓ Meshtastic installed via apt"
        
    # Use pip with --break-system-packages as last resort
    else
        print_warn "Installing with pip (--break-system-packages). Consider using pipx instead."
        
        # First ensure pip is installed
        if ! command -v pip3 &> /dev/null; then
            apt-get update -qq
            apt-get install -y -qq python3-pip
        fi
        
        # Install with override flag
        pip3 install --quiet --break-system-packages meshtastic
        print_info "✓ Meshtastic Python library installed (with override)"
        
        print_warn "Note: Using --break-system-packages is not recommended for production."
        echo "  Consider installing pipx instead:"
        echo "    sudo apt-get install pipx"
        echo "    pipx install meshtastic"
    fi
    
# For older systems or non-Debian
else
    if command -v pip3 &> /dev/null; then
        print_info "Installing meshtastic Python library..."
        pip3 install --quiet meshtastic
        print_info "✓ Meshtastic Python library installed"
    else
        print_warn "pip3 not found. Please install Python dependencies manually:"
        echo "  sudo apt-get install python3-pip"
        echo "  pip3 install meshtastic"
    fi
fi

# Check if Python script is already deployed
PYTHON_SCRIPT_DEPLOYED=false
if [ -f "/opt/tak/conf/plugins/meshtastic_sender.py" ]; then
    PYTHON_SCRIPT_DEPLOYED=true
    print_info "✓ Python script already deployed at /opt/tak/conf/plugins/meshtastic_sender.py"
else
    print_warn "Python script not yet deployed to /opt/tak/conf/plugins/"
fi

# Test script permissions
if [ "$DEVICE_FOUND" = true ] && [ ! -z "$DEVICE_PATH" ]; then
    print_info "Testing serial port access for $TAK_USER..."
    
    # Create a test script
    TEST_SCRIPT="/tmp/test_serial_access.sh"
    cat > "$TEST_SCRIPT" << EOF
#!/bin/bash
if [ -r "$DEVICE_PATH" ] && [ -w "$DEVICE_PATH" ]; then
    echo "SUCCESS: Can access $DEVICE_PATH"
    exit 0
else
    echo "ERROR: Cannot access $DEVICE_PATH"
    exit 1
fi
EOF
    chmod +x "$TEST_SCRIPT"
    
    # Test as TAK user
    if sudo -u "$TAK_USER" "$TEST_SCRIPT" 2>/dev/null; then
        print_info "✓ $TAK_USER can access $DEVICE_PATH"
    else
        print_warn "$TAK_USER cannot access $DEVICE_PATH yet (may need service restart)"
    fi
    
    rm -f "$TEST_SCRIPT"
fi

# Check if TAK Server is running
print_info "Checking TAK Server status..."
if systemctl is-active --quiet takserver; then
    print_info "TAK Server is running"
    echo ""
    print_warn "IMPORTANT: You need to restart TAK Server for permission changes to take effect:"
    echo "  sudo systemctl restart takserver"
else
    print_info "TAK Server is not currently running"
fi

echo ""
echo "========================================="
echo -e "${GREEN}Setup Complete!${NC}"
echo "========================================="
echo ""
echo "Next steps:"
echo "1. If TAK Server is running, restart it:"
echo "   sudo systemctl restart takserver"
echo ""
echo "2. If you want to test manually as your user ($SUDO_USER), logout and login again, or run:"
echo "   newgrp dialout"
echo ""
echo "3. Update the plugin configuration file:"
echo "   /opt/tak/conf/plugins/tak.server.plugins.MeshtasticInterceptorPlugin.yaml"
echo ""

if [ "$DEVICE_FOUND" = true ]; then
    echo "4. Your Meshtastic device was detected at: $DEVICE_PATH"
    echo "   Update the 'port' setting in the configuration to use this device."
else
    echo "4. No Meshtastic device detected. After connecting your device:"
    echo "   - Run 'ls /dev/ttyUSB* /dev/ttyACM*' to find the device"
    echo "   - Update the 'port' setting in the configuration"
fi

echo ""
echo "5. Deploy the plugin files (if not done already):"
echo "   From the takserver-meshtastic-plugin directory:"
echo "   sudo cp build/libs/takserver-meshtastic-plugin-*.jar /opt/tak/lib/"
echo "   sudo cp src/main/resources/meshtastic_sender.py /opt/tak/conf/plugins/"
echo "   sudo cp tak.server.plugins.MeshtasticInterceptorPlugin.yaml /opt/tak/conf/plugins/"
echo "   sudo chmod 755 /opt/tak/conf/plugins/meshtastic_sender.py"
echo "   sudo chown tak:tak /opt/tak/conf/plugins/meshtastic_sender.py"
echo ""
echo "6. Test the Python script manually:"
if [ "$DEVICE_FOUND" = true ]; then
    echo "   echo '<event uid=\"test\"/>' | sudo -u $TAK_USER python3 /opt/tak/conf/plugins/meshtastic_sender.py --interface serial --port $DEVICE_PATH"
else
    echo "   echo '<event uid=\"test\"/>' | sudo -u $TAK_USER python3 /opt/tak/conf/plugins/meshtastic_sender.py --interface serial --port /dev/ttyUSB0"
fi

echo ""
print_info "For more information, see the README.md file"