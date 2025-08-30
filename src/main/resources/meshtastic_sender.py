#!/usr/bin/env python3
"""
Meshtastic CoT Sender using ATAK Protobuf
Sends Cursor on Target (CoT) messages over Meshtastic mesh network using optimized ATAK protobuf format
"""

import sys
import json
import argparse
import logging
import re
import xml.etree.ElementTree as ET
from typing import Optional, Dict, Any
import struct

# Try to import meshtastic with helpful error message
try:
    import meshtastic
    import meshtastic.serial_interface
    import meshtastic.tcp_interface
    import meshtastic.ble_interface
    from meshtastic import portnums_pb2
except ImportError as e:
    print(f"Error: Failed to import meshtastic library: {e}", file=sys.stderr)
    print("\nTo install on Debian 12+, use one of these methods:", file=sys.stderr)
    print("  1. pipx install meshtastic  (recommended)", file=sys.stderr)
    print("  2. apt install python3-meshtastic  (if available)", file=sys.stderr)
    print("  3. pip3 install --break-system-packages meshtastic  (not recommended)", file=sys.stderr)
    print("\nOr run the setup script: sudo bash /opt/tak/setup-meshtastic-permissions.sh", file=sys.stderr)
    sys.exit(1)

# Try to import protobuf
try:
    from google.protobuf import message as protobuf_message
except ImportError:
    print("Error: protobuf library not found. Install with: pip3 install protobuf", file=sys.stderr)
    sys.exit(1)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Define the ATAK protobuf message structure inline
# This matches the atak.proto definition for Meshtastic
class ATAKProtobuf:
    """Simple ATAK protobuf encoder matching Meshtastic's atak.proto"""
    
    # Team color mappings
    TEAM_COLORS = {
        'White': 1, 'Yellow': 2, 'Orange': 3, 'Magenta': 4,
        'Red': 5, 'Maroon': 6, 'Purple': 7, 'Dark Blue': 8,
        'Blue': 9, 'Cyan': 10, 'Teal': 11, 'Green': 12,
        'Dark Green': 13, 'Brown': 14
    }
    
    # Member role mappings
    MEMBER_ROLES = {
        'Team Member': 1, 'Team Lead': 2, 'HQ': 3,
        'Sniper': 4, 'Medic': 5, 'Forward Observer': 6,
        'RTO': 7, 'K9': 8
    }
    
    @staticmethod
    def encode_pli(lat: float, lon: float, alt: int = 0, speed: int = 0, course: int = 0) -> bytes:
        """
        Encode PLI (Position Location Information) message
        
        Args:
            lat: Latitude in degrees
            lon: Longitude in degrees
            alt: Altitude in meters (HAE preferred)
            speed: Speed in m/s
            course: Course in degrees
        
        Returns:
            Encoded protobuf bytes
        """
        # Convert lat/lon to fixed32 (multiply by 1e7)
        lat_i = int(lat * 1e7)
        lon_i = int(lon * 1e7)
        
        # Simple protobuf encoding for PLI
        # Field 5 (PLI) -> Field 1 (lat), Field 2 (lon), Field 3 (alt), Field 4 (speed), Field 5 (course)
        msg = bytearray()
        
        # TAKPacket wrapper
        msg.extend(b'\x2a')  # Field 5 (pli), wire type 2 (length-delimited)
        
        pli_msg = bytearray()
        # latitude_i (field 1, sfixed32)
        pli_msg.extend(b'\x0d')  # Field 1, wire type 5 (fixed32)
        pli_msg.extend(struct.pack('<i', lat_i))
        
        # longitude_i (field 2, sfixed32)
        pli_msg.extend(b'\x15')  # Field 2, wire type 5 (fixed32)
        pli_msg.extend(struct.pack('<i', lon_i))
        
        # altitude (field 3, int32) - optional
        if alt != 0:
            pli_msg.extend(ATAKProtobuf._encode_varint(3 << 3))  # Field 3, wire type 0
            pli_msg.extend(ATAKProtobuf._encode_varint(alt))
        
        # speed (field 4, uint32) - optional
        if speed > 0:
            pli_msg.extend(ATAKProtobuf._encode_varint(4 << 3))  # Field 4, wire type 0
            pli_msg.extend(ATAKProtobuf._encode_varint(speed))
        
        # course (field 5, uint32) - optional
        if course > 0:
            pli_msg.extend(ATAKProtobuf._encode_varint(5 << 3))  # Field 5, wire type 0
            pli_msg.extend(ATAKProtobuf._encode_varint(course))
        
        # Add PLI message length and content
        msg.extend(ATAKProtobuf._encode_varint(len(pli_msg)))
        msg.extend(pli_msg)
        
        return bytes(msg)
    
    @staticmethod
    def encode_geochat(message: str, to: Optional[str] = None, to_callsign: Optional[str] = None) -> bytes:
        """
        Encode GeoChat message
        
        Args:
            message: The text message
            to: Optional UID recipient
            to_callsign: Optional callsign recipient
        
        Returns:
            Encoded protobuf bytes
        """
        msg = bytearray()
        
        # TAKPacket wrapper - Field 6 (chat)
        msg.extend(b'\x32')  # Field 6, wire type 2 (length-delimited)
        
        chat_msg = bytearray()
        
        # message (field 1, string)
        chat_msg.extend(b'\x0a')  # Field 1, wire type 2
        chat_msg.extend(ATAKProtobuf._encode_varint(len(message)))
        chat_msg.extend(message.encode('utf-8'))
        
        # to (field 2, optional string)
        if to:
            chat_msg.extend(b'\x12')  # Field 2, wire type 2
            chat_msg.extend(ATAKProtobuf._encode_varint(len(to)))
            chat_msg.extend(to.encode('utf-8'))
        
        # to_callsign (field 3, optional string)
        if to_callsign:
            chat_msg.extend(b'\x1a')  # Field 3, wire type 2
            chat_msg.extend(ATAKProtobuf._encode_varint(len(to_callsign)))
            chat_msg.extend(to_callsign.encode('utf-8'))
        
        # Add chat message length and content
        msg.extend(ATAKProtobuf._encode_varint(len(chat_msg)))
        msg.extend(chat_msg)
        
        return bytes(msg)
    
    @staticmethod
    def encode_contact(callsign: str, device_callsign: Optional[str] = None) -> bytes:
        """Encode contact information"""
        contact_msg = bytearray()
        
        # callsign (field 1, string)
        if callsign:
            contact_msg.extend(b'\x0a')  # Field 1, wire type 2
            contact_msg.extend(ATAKProtobuf._encode_varint(len(callsign)))
            contact_msg.extend(callsign.encode('utf-8'))
        
        # device_callsign (field 2, string) - optional
        if device_callsign:
            contact_msg.extend(b'\x12')  # Field 2, wire type 2
            contact_msg.extend(ATAKProtobuf._encode_varint(len(device_callsign)))
            contact_msg.extend(device_callsign.encode('utf-8'))
        
        return contact_msg
    
    @staticmethod
    def encode_full_packet(cot_xml: str, compress: bool = False) -> bytes:
        """
        Encode a full TAKPacket from CoT XML
        
        Args:
            cot_xml: The CoT XML string
            compress: Whether to compress the payload
        
        Returns:
            Encoded protobuf bytes
        """
        try:
            # Parse the CoT XML
            root = ET.fromstring(cot_xml)
            
            msg = bytearray()
            
            # is_compressed (field 1, bool) - optional, only if true
            if compress:
                msg.extend(b'\x08\x01')  # Field 1, wire type 0, value 1
            
            # Extract contact info
            contact_elem = root.find('.//contact')
            if contact_elem is not None:
                callsign = contact_elem.get('callsign', '')
                if callsign:
                    contact_data = ATAKProtobuf.encode_contact(callsign)
                    if contact_data:
                        msg.extend(b'\x12')  # Field 2 (contact), wire type 2
                        msg.extend(ATAKProtobuf._encode_varint(len(contact_data)))
                        msg.extend(contact_data)
            
            # Extract group info (team color and role)
            group_elem = root.find('.//__group')
            if group_elem is not None:
                role = group_elem.get('role', 'Team Member')
                team = group_elem.get('name', 'Cyan')
                
                group_msg = bytearray()
                
                # role (field 1, enum)
                role_value = ATAKProtobuf.MEMBER_ROLES.get(role, 1)
                if role_value > 0:
                    group_msg.extend(b'\x08')  # Field 1, wire type 0
                    group_msg.extend(ATAKProtobuf._encode_varint(role_value))
                
                # team (field 2, enum)
                team_value = ATAKProtobuf.TEAM_COLORS.get(team, 10)  # Default Cyan
                if team_value > 0:
                    group_msg.extend(b'\x10')  # Field 2, wire type 0
                    group_msg.extend(ATAKProtobuf._encode_varint(team_value))
                
                if group_msg:
                    msg.extend(b'\x1a')  # Field 3 (group), wire type 2
                    msg.extend(ATAKProtobuf._encode_varint(len(group_msg)))
                    msg.extend(group_msg)
            
            # Extract status (battery)
            status_elem = root.find('.//status')
            if status_elem is not None:
                battery = status_elem.get('battery')
                if battery:
                    try:
                        battery_val = int(battery)
                        status_msg = bytearray()
                        status_msg.extend(b'\x08')  # Field 1, wire type 0
                        status_msg.extend(ATAKProtobuf._encode_varint(battery_val))
                        
                        msg.extend(b'\x22')  # Field 4 (status), wire type 2
                        msg.extend(ATAKProtobuf._encode_varint(len(status_msg)))
                        msg.extend(status_msg)
                    except ValueError:
                        pass
            
            # Extract point (PLI) - this is the main position data
            point_elem = root.find('.//point')
            if point_elem is not None:
                lat = float(point_elem.get('lat', 0))
                lon = float(point_elem.get('lon', 0))
                
                # Try to get altitude (HAE preferred)
                alt = 0
                if point_elem.get('hae'):
                    alt = int(float(point_elem.get('hae')))
                elif point_elem.get('le'):
                    alt = int(float(point_elem.get('le')))
                
                # Get track info if available
                track_elem = root.find('.//track')
                speed = 0
                course = 0
                if track_elem is not None:
                    speed_str = track_elem.get('speed')
                    course_str = track_elem.get('course')
                    if speed_str:
                        speed = int(float(speed_str))
                    if course_str:
                        course = int(float(course_str))
                
                # Encode PLI
                pli_data = ATAKProtobuf.encode_pli(lat, lon, alt, speed, course)
                msg.extend(pli_data)
            
            # Check if this is a GeoChat message
            geochat_elem = root.find('.//remarks')
            if geochat_elem is not None and geochat_elem.text:
                # Extract GeoChat details
                chat_text = geochat_elem.text
                
                # Try to find recipient info
                to_uid = None
                to_callsign = None
                dest_elem = root.find('.//dest')
                if dest_elem is not None:
                    to_callsign = dest_elem.get('callsign')
                
                chat_data = ATAKProtobuf.encode_geochat(chat_text, to_uid, to_callsign)
                msg.extend(chat_data)
            
            return bytes(msg)
            
        except Exception as e:
            logger.error(f"Failed to encode CoT to ATAK protobuf: {e}")
            # Return minimal PLI at 0,0 as fallback
            return ATAKProtobuf.encode_pli(0.0, 0.0)
    
    @staticmethod
    def _encode_varint(value: int) -> bytes:
        """Encode an integer as protobuf varint"""
        result = bytearray()
        while value > 127:
            result.append((value & 0x7F) | 0x80)
            value >>= 7
        result.append(value & 0x7F)
        return bytes(result)


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
        Send CoT XML over Meshtastic using ATAK protobuf format
        
        Args:
            cot_xml: CoT XML string to send
            channel: Meshtastic channel to use (default 0)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Convert CoT XML to ATAK protobuf format
            atak_packet = ATAKProtobuf.encode_full_packet(cot_xml)
            
            logger.info(f"Encoded CoT to ATAK protobuf ({len(atak_packet)} bytes)")
            
            # Send via Meshtastic using ATAK app port
            # The ATAK port number is 72 (0x48) in Meshtastic
            self.interface.sendData(
                data=atak_packet,
                portNum=portnums_pb2.PortNum.ATAK_PLUGIN,  # Use ATAK plugin port
                channelIndex=channel,
                wantAck=True,
                wantResponse=False
            )
            
            logger.info(f"Sent ATAK packet via Meshtastic ({len(atak_packet)} bytes)")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send CoT via Meshtastic: {e}")
            return False
    
    def close(self):
        """Close the Meshtastic interface"""
        if self.interface:
            try:
                self.interface.close()
                logger.info("Meshtastic interface closed")
            except Exception as e:
                logger.error(f"Error closing interface: {e}")

def main():
    parser = argparse.ArgumentParser(description='Send CoT messages via Meshtastic using ATAK protobuf')
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