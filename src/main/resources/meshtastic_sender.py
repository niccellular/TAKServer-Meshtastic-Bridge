#!/usr/bin/env python3
"""
Meshtastic CoT Sender
Sends Cursor on Target (CoT) messages over Meshtastic mesh network
"""

import sys
import json
import argparse
import logging
from typing import Optional

# Try to import meshtastic with helpful error message
try:
    import meshtastic
    import meshtastic.serial_interface
    import meshtastic.tcp_interface
    import meshtastic.ble_interface
except ImportError as e:
    print(f"Error: Failed to import meshtastic library: {e}", file=sys.stderr)
    print("\nTo install on Debian 12+, use one of these methods:", file=sys.stderr)
    print("  1. pipx install meshtastic  (recommended)", file=sys.stderr)
    print("  2. apt install python3-meshtastic  (if available)", file=sys.stderr)
    print("  3. pip3 install --break-system-packages meshtastic  (not recommended)", file=sys.stderr)
    print("\nOr run the setup script: sudo bash /opt/tak/setup-meshtastic-permissions.sh", file=sys.stderr)
    sys.exit(1)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class MeshtasticCoTSender:
    def __init__(self, interface_type: str = "serial", port: str = "/dev/ttyUSB0", host: str = "localhost"):
        """
        Initialize Meshtastic interface
        
        Args:
            interface_type: Type of interface (serial, tcp, ble)
            port: Serial port or BLE address
            host: TCP host (only for TCP interface)
        """
        self.interface_type = interface_type
        self.interface = None
        
        try:
            if interface_type == "serial":
                logger.info(f"Connecting to Meshtastic via serial port: {port}")
                self.interface = meshtastic.serial_interface.SerialInterface(port)
            elif interface_type == "tcp":
                logger.info(f"Connecting to Meshtastic via TCP: {host}")
                self.interface = meshtastic.tcp_interface.TCPInterface(host)
            elif interface_type == "ble":
                logger.info(f"Connecting to Meshtastic via BLE: {port}")
                self.interface = meshtastic.ble_interface.BLEInterface(port)
            else:
                raise ValueError(f"Unknown interface type: {interface_type}")
                
        except Exception as e:
            logger.error(f"Failed to initialize Meshtastic interface: {e}")
            raise
    
    def send_cot(self, cot_xml: str, channel: int = 0) -> bool:
        """
        Send CoT XML over Meshtastic
        
        Args:
            cot_xml: CoT XML string to send
            channel: Meshtastic channel to use (default 0)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Meshtastic has a message size limit, so we may need to compress or truncate
            # For now, we'll send as-is and let Meshtastic handle fragmentation
            
            # Extract essential information from CoT for smaller message if needed
            # This is a simplified approach - you may want to implement proper CoT compression
            if len(cot_xml) > 200:  # Meshtastic typical limit
                # Create a compact version with just essential fields
                compact_msg = self._create_compact_cot(cot_xml)
                logger.info(f"Original CoT too large ({len(cot_xml)} bytes), sending compact version ({len(compact_msg)} bytes)")
                message = compact_msg
            else:
                message = cot_xml
            
            # Send via Meshtastic
            self.interface.sendText(
                text=message,
                channelIndex=channel,
                wantAck=True,
                wantResponse=False
            )
            
            logger.info(f"Sent CoT message via Meshtastic ({len(message)} bytes)")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send CoT via Meshtastic: {e}")
            return False
    
    def _create_compact_cot(self, cot_xml: str) -> str:
        """
        Create a compact version of CoT for Meshtastic transmission
        Extract only essential fields: uid, type, lat, lon, callsign
        """
        try:
            # Simple XML parsing (production code should use proper XML parser)
            import re
            
            # Extract key attributes
            uid_match = re.search(r'uid="([^"]+)"', cot_xml)
            type_match = re.search(r'type="([^"]+)"', cot_xml)
            lat_match = re.search(r'lat="([^"]+)"', cot_xml)
            lon_match = re.search(r'lon="([^"]+)"', cot_xml)
            callsign_match = re.search(r'callsign="([^"]+)"', cot_xml)
            
            # Build compact JSON message
            compact = {
                "cot": "1",  # Version/marker
            }
            
            if uid_match:
                compact["u"] = uid_match.group(1)[:20]  # Truncate UID
            if type_match:
                compact["t"] = type_match.group(1)[:10]  # Truncate type
            if lat_match and lon_match:
                compact["la"] = round(float(lat_match.group(1)), 5)
                compact["lo"] = round(float(lon_match.group(1)), 5)
            if callsign_match:
                compact["c"] = callsign_match.group(1)[:15]  # Truncate callsign
            
            return json.dumps(compact, separators=(',', ':'))
            
        except Exception as e:
            logger.error(f"Failed to create compact CoT: {e}")
            # Return a minimal message on error
            return '{"cot":"1","err":"parse"}'
    
    def close(self):
        """Close the Meshtastic interface"""
        if self.interface:
            try:
                self.interface.close()
                logger.info("Meshtastic interface closed")
            except Exception as e:
                logger.error(f"Error closing interface: {e}")

def main():
    parser = argparse.ArgumentParser(description='Send CoT messages via Meshtastic')
    parser.add_argument('--interface', type=str, default='serial',
                       choices=['serial', 'tcp', 'ble'],
                       help='Meshtastic interface type')
    parser.add_argument('--port', type=str, default='/dev/ttyUSB0',
                       help='Serial port or BLE address')
    parser.add_argument('--host', type=str, default='localhost',
                       help='TCP host (for TCP interface)')
    parser.add_argument('--channel', type=int, default=0,
                       help='Meshtastic channel index')
    
    args = parser.parse_args()
    
    # Read CoT XML from stdin
    cot_xml = sys.stdin.read()
    
    if not cot_xml:
        logger.error("No CoT XML received on stdin")
        sys.exit(1)
    
    sender = None
    try:
        # Initialize sender
        sender = MeshtasticCoTSender(
            interface_type=args.interface,
            port=args.port,
            host=args.host
        )
        
        # Send the CoT
        success = sender.send_cot(cot_xml, channel=args.channel)
        
        sys.exit(0 if success else 1)
        
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)
    finally:
        if sender:
            sender.close()

if __name__ == "__main__":
    main()