import sys
sys.path.insert(0, "verify")
from crop_png import read_png
w, h, ch, rows = read_png("verify/out/widgets.png")

def pix(x, y):
    r = rows[y]
    return tuple(r[x*ch:x*ch+3])

def runs(y, x0, x1, skip=(245, 247, 251)):
    out = []
    prev = None
    start = x0
    for x in range(x0, x1):
        c = pix(x, y)
        if c != prev:
            if prev is not None:
                out.append((start, x - 1, prev))
            prev = c
            start = x
    out.append((start, x1 - 1, prev))
    return [o for o in out if o[2] != skip]

print("row65", runs(65, 40, 120))
print("row80", runs(80, 40, 120))
print("row70 right", runs(70, 800, 880))
print("row300 right", runs(300, 800, 880))
print("chip650", runs(650, 50, 220))
print("chip680", runs(680, 50, 220))
print("date1040", runs(1040, 450, 800))
print("bg", pix(10, 10))
