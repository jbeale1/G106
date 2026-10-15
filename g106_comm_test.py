#!/usr/bin/env python3

# g106_comm_test.py
# confirm that the G106 QRP radio responds to serial commands

# Requires: pip install pyserial

import time
import serial

#PORT = "COM7" # Windows
PORT = "/dev/ttyUSB0" # Linux

BAUD = 19200        # radio uses this bitrate
RADIO_ADDR = 0x70   # G106 CI-V address
CTRL_ADDR = 0xE0    # PC controller address
PREFIX = bytes([0xFE, 0xFE, RADIO_ADDR, CTRL_ADDR])
SUFFIX = b"\xFD"


def read_frames(ser, timeout=1.0):
    """Collect all CI-V frames received within the timeout. Returns bodies (dst, src, cmd, data...)."""
    deadline = time.time() + timeout
    raw = bytearray()
    while time.time() < deadline:
        n = ser.in_waiting
        if n:
            raw += ser.read(n)
        else:
            time.sleep(0.02)

    bodies = []
    for part in raw.split(SUFFIX):
        idx = part.find(b"\xFE\xFE")
        if idx != -1 and len(part) > idx + 2:
            bodies.append(bytes(part[idx + 2:]))
    return bodies


def send_cmd(ser, cmd, data=b""):
    """Send a CI-V command and return the radio's response body (or None)."""
    ser.reset_input_buffer()
    ser.write(PREFIX + cmd + data + SUFFIX)
    ser.flush()
    for body in read_frames(ser):
        # Radio responses have dst=E0 (controller), src=70 (radio).
        # Ignore our own echoed command (dst=70, src=E0).
        if len(body) >= 3 and body[0] == CTRL_ADDR and body[1] == RADIO_ADDR:
            return body
    return None


def main():
    print(f"Opening {PORT} at {BAUD} 8N1...")
    with serial.Serial(
        port=PORT,
        baudrate=BAUD,
        bytesize=serial.EIGHTBITS,
        parity=serial.PARITY_NONE,
        stopbits=serial.STOPBITS_ONE,
        timeout=0,
    ) as ser:

        # 1. Radio ID (0x19 0x00) -> expect 0x70 as the ID byte
        body = send_cmd(ser, b"\x19", b"\x00")
        if body:
            print(f"Radio ID response : {body.hex(' ').upper()}")
            print(f"Radio ID          : {body[-1]:02X} ({'OK' if body[-1] == 0x70 else 'unexpected'})")
        else:
            print("Radio ID          : NO RESPONSE")

        # 2. Active VFO frequency (0x03) -> 5 BCD bytes, little-endian, in Hz
        body = send_cmd(ser, b"\x03")
        if body and len(body) >= 8:
            freq_hz = int("".join(f"{b:02X}" for b in reversed(body[3:8])))
            print(f"VFO frequency     : {freq_hz} Hz ({freq_hz / 1e6:.6f} MHz)")
        else:
            print("VFO frequency     : NO RESPONSE")

        # 3. S-meter (0x14 0x02) -> 2 BCD bytes, big-endian, 0-255
        body = send_cmd(ser, b"\x14", b"\x02")
        if body and len(body) >= 6:
            smeter = int(body[4:6].hex())
            print(f"S-meter           : {smeter} (0-255)")
        else:
            print("S-meter           : NO RESPONSE")


if __name__ == "__main__":
    main()

