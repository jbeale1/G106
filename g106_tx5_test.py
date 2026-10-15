#!/usr/bin/env python3

# g106_tx5_test.py
# Requires: pip install pyserial
# Use only with a dummy load connected to the ANT jack.

import time
import serial

PORT = "/dev/ttyUSB0"   # use "COM7" on Windows
BAUD = 19200
# FREQ_HZ = 7_025_423 # 40 m band
FREQ_HZ = 3_601_423 # 80 m band

TX_SECONDS = 5
REFRESH_S = 1.0         # re-send PTT-on this often (radio drops PTT after ~2 s)

RADIO_ADDR = 0x70
CTRL_ADDR = 0xE0
PREFIX = bytes([0xFE, 0xFE, RADIO_ADDR, CTRL_ADDR])
SUFFIX = b"\xFD"
ACK = 0xFB
NAK = 0xFA


def freq_to_bcd_le(hz):
    digits = f"{hz:010d}"
    pairs = [int(digits[i:i + 2], 16) for i in range(0, 10, 2)]
    return bytes(reversed(pairs))


def read_frames(ser, timeout=1.0):
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
    ser.reset_input_buffer()
    ser.write(PREFIX + cmd + data + SUFFIX)
    ser.flush()
    for body in read_frames(ser):
        if len(body) >= 3 and body[0] == CTRL_ADDR and body[1] == RADIO_ADDR:
            return body
    return None


def check_ack(name, body):
    if body is None:
        raise RuntimeError(f"{name}: no response")
    if body[2] == ACK:
        return
    if body[2] == NAK:
        raise RuntimeError(f"{name}: radio rejected command (NAK)")
    raise RuntimeError(f"{name}: unexpected reply {body.hex(' ').upper()}")


def set_ptt(ser, on):
    return send_cmd(ser, b"\x1C\x00", b"\x01" if on else b"\x00")


def main():
    with serial.Serial(
        port=PORT,
        baudrate=BAUD,
        bytesize=serial.EIGHTBITS,
        parity=serial.PARITY_NONE,
        stopbits=serial.STOPBITS_ONE,
        timeout=0,
    ) as ser:

        check_ack("Set frequency", send_cmd(ser, b"\x05", freq_to_bcd_le(FREQ_HZ)))

        try:
            print(f"Transmitting for {TX_SECONDS} s...")
            start = time.monotonic()
            next_tick = start
            while time.monotonic() - start < TX_SECONDS:
                check_ack("PTT on", set_ptt(ser, True))
                next_tick += REFRESH_S
                time.sleep(max(0, next_tick - time.monotonic()))
        finally:
            body = set_ptt(ser, False)
            if body and body[2] == ACK:
                print("PTT off: OK")
            else:
                print("PTT off: NO CONFIRMATION, check the radio")


if __name__ == "__main__":
    main()
