"""Crop a PNG produced by verify/capture.py (no third-party deps)."""
import struct
import sys
import zlib

from capture import _write_png


def read_png(path):
    with open(path, "rb") as handle:
        data = handle.read()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("not a png")
    pos = 8
    width = height = None
    idat = b""
    while pos < len(data):
        length = struct.unpack(">I", data[pos:pos + 4])[0]
        kind = data[pos + 4:pos + 8]
        body = data[pos + 8:pos + 8 + length]
        pos += 12 + length
        if kind == b"IHDR":
            width, height, depth, color, _, _, _ = struct.unpack(">IIBBBBB", body)
            if depth != 8 or color not in (2, 6):
                raise ValueError("unsupported png")
            channels = 3 if color == 2 else 4
        elif kind == b"IDAT":
            idat += body
        elif kind == b"IEND":
            break
    raw = zlib.decompress(idat)
    stride = width * channels
    rows = []
    prev = bytearray(stride)
    at = 0
    for _ in range(height):
        filt = raw[at]
        at += 1
        line = bytearray(raw[at:at + stride])
        at += stride
        for i in range(stride):
            a = line[i - channels] if i >= channels else 0
            b = prev[i]
            c = prev[i - channels] if i >= channels else 0
            if filt == 1:
                line[i] = (line[i] + a) & 0xFF
            elif filt == 2:
                line[i] = (line[i] + b) & 0xFF
            elif filt == 3:
                line[i] = (line[i] + (a + b) // 2) & 0xFF
            elif filt == 4:
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                pred = a if pa <= pb and pa <= pc else (b if pb <= pc else c)
                line[i] = (line[i] + pred) & 0xFF
        rows.append(bytes(line))
        prev = line
    return width, height, channels, rows


def crop(src, dst, left, top, width, height):
    w, h, channels, rows = read_png(src)
    out = []
    for y in range(top, min(top + height, h)):
        line = rows[y]
        part = line[left * channels:(left + width) * channels]
        rgba = bytearray(width * 4)
        for x in range(min(width, w - left)):
            r = part[x * channels]
            g = part[x * channels + 1]
            b = part[x * channels + 2]
            a = part[x * channels + 3] if channels == 4 else 255
            rgba[x * 4:x * 4 + 4] = bytes((r, g, b, a))
        out.append(bytes(rgba))
    _write_png(dst, width, len(out), out)
    return width, len(out)


if __name__ == "__main__":
    src, dst = sys.argv[1], sys.argv[2]
    left, top, width, height = [int(v) for v in sys.argv[3:7]]
    print(crop(src, dst, left, top, width, height))
