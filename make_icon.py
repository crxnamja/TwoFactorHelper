#!/usr/bin/env python3
"""Generate the TwoFactorHelper app icon."""

import math
import os
import subprocess
from PIL import Image, ImageDraw, ImageFont, ImageFilter

SIZE = 1024
CENTER = SIZE // 2


def lerp(a, b, t):
    return a + (b - a) * t


def draw_icon():
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))

    # --- Gradient background ---
    for y in range(SIZE):
        for x in range(SIZE):
            t = y / SIZE
            # Top: vibrant blue, Bottom: deep indigo
            r = int(lerp(30, 55, t))
            g = int(lerp(60, 20, t))
            b = int(lerp(220, 160, t))
            # Subtle radial warmth in center
            dx = (x - CENTER) / CENTER
            dy = (y - CENTER) / CENTER
            dist = math.sqrt(dx * dx + dy * dy)
            warm = max(0, 1 - dist * 0.8)
            r = min(255, int(r + warm * 40))
            g = min(255, int(g + warm * 15))
            img.putpixel((x, y), (r, g, b, 255))

    # Rounded rect mask
    mask = Image.new("L", (SIZE, SIZE), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        [0, 0, SIZE - 1, SIZE - 1], radius=int(SIZE / 4.5), fill=255
    )
    img.putalpha(mask)

    # --- Shield shape (proper: wide top, pointed bottom) ---
    shield_layer = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shield_layer)

    # Shield dimensions
    sw = 480  # width
    sh = 580  # height
    sx = CENTER - sw // 2  # left x
    sy = 185  # top y
    cr = 50  # corner radius
    bp = sy + sh  # bottom point y

    # Build shield as polygon: flat top with rounded corners, tapers to point
    points = []

    # Top-left corner (arc from left to top)
    for i in range(20):
        a = math.pi + (math.pi / 2) * (i / 19)
        px = sx + cr + cr * math.cos(a)
        py = sy + cr + cr * math.sin(a)
        points.append((px, py))

    # Top edge
    points.append((sx + sw - cr, sy))

    # Top-right corner
    for i in range(20):
        a = -math.pi / 2 + (math.pi / 2) * (i / 19)
        px = sx + sw - cr + cr * math.cos(a)
        py = sy + cr + cr * math.sin(a)
        points.append((px, py))

    # Right side tapering to bottom point
    side_h = sh * 0.45
    points.append((sx + sw, sy + side_h))

    # Curve to bottom point
    for i in range(30):
        t = i / 29
        # Quadratic bezier: right-side midpoint -> bottom point
        p0 = (sx + sw, sy + side_h)
        p1 = (sx + sw - sw * 0.15, sy + sh * 0.8)
        p2 = (CENTER, bp)
        px = (1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t ** 2 * p2[0]
        py = (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t ** 2 * p2[1]
        points.append((px, py))

    # Curve from bottom point to left side
    for i in range(30):
        t = i / 29
        p0 = (CENTER, bp)
        p1 = (sx + sw * 0.15, sy + sh * 0.8)
        p2 = (sx, sy + side_h)
        px = (1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t ** 2 * p2[0]
        py = (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t ** 2 * p2[1]
        points.append((px, py))

    points.append((sx, sy + cr))

    # Draw shield fill (frosted glass effect)
    sd.polygon(points, fill=(255, 255, 255, 40))

    # Shield border
    for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1), (0, 0)]:
        shifted = [(p[0] + dx, p[1] + dy) for p in points]
        sd.polygon(shifted, outline=(255, 255, 255, 100))

    # Inner highlight on shield (top portion lighter)
    highlight = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    hd = ImageDraw.Draw(highlight)
    for i, (px, py) in enumerate(points):
        points[i] = (px, py)
    # Top gradient shine
    for y_off in range(int(sh * 0.35)):
        alpha = int(25 * (1 - y_off / (sh * 0.35)))
        y_pos = sy + y_off
        # Find shield width at this y
        left_x = sx + 10
        right_x = sx + sw - 10
        hd.line([(left_x, y_pos), (right_x, y_pos)], fill=(255, 255, 255, alpha))

    shield_layer = Image.alpha_composite(shield_layer, highlight)
    img = Image.alpha_composite(img, shield_layer)

    # --- "2FA" text ---
    draw = ImageDraw.Draw(img)
    font_size = 210
    font = None
    for name in [
        "/System/Library/Fonts/SFCompact-Bold.otf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ]:
        if os.path.exists(name):
            try:
                font = ImageFont.truetype(name, font_size)
                break
            except Exception:
                continue
    if font is None:
        font = ImageFont.load_default()

    text = "2FA"
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    tx = CENTER - tw // 2
    ty = CENTER - th // 2 - 40

    # Text shadow
    shadow = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).text((tx + 4, ty + 4), text, fill=(0, 0, 0, 60), font=font)
    shadow = shadow.filter(ImageFilter.GaussianBlur(radius=4))
    img = Image.alpha_composite(img, shadow)

    # Main text
    text_layer = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    ImageDraw.Draw(text_layer).text((tx, ty), text, fill=(255, 255, 255, 255), font=font)
    img = Image.alpha_composite(img, text_layer)

    # --- Lock icon below text ---
    lock_layer = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    ld = ImageDraw.Draw(lock_layer)

    lx = CENTER  # center x
    ly = ty + th + 55  # top of lock body
    body_w, body_h = 52, 40
    shackle_w = 32
    shackle_h = 24

    # Lock body (rounded rect)
    ld.rounded_rectangle(
        [lx - body_w // 2, ly, lx + body_w // 2, ly + body_h],
        radius=8,
        fill=(255, 255, 255, 220),
    )

    # Shackle
    ld.arc(
        [lx - shackle_w // 2, ly - shackle_h, lx + shackle_w // 2, ly + 4],
        start=180, end=0,
        fill=(255, 255, 255, 220),
        width=6,
    )

    # Keyhole
    kh_r = 7
    ld.ellipse(
        [lx - kh_r, ly + 12, lx + kh_r, ly + 12 + kh_r * 2],
        fill=(55, 40, 160, 200),
    )
    ld.polygon(
        [(lx - 4, ly + 20), (lx + 4, ly + 20), (lx + 2, ly + 30), (lx - 2, ly + 30)],
        fill=(55, 40, 160, 200),
    )

    img = Image.alpha_composite(img, lock_layer)

    return img


def create_iconset(img, output_dir):
    iconset_dir = os.path.join(output_dir, "AppIcon.iconset")
    os.makedirs(iconset_dir, exist_ok=True)

    sizes = [16, 32, 64, 128, 256, 512, 1024]
    for size in sizes:
        resized = img.resize((size, size), Image.LANCZOS)
        resized.save(os.path.join(iconset_dir, f"icon_{size}x{size}.png"))
        if size <= 512:
            resized2x = img.resize((size * 2, size * 2), Image.LANCZOS)
            resized2x.save(os.path.join(iconset_dir, f"icon_{size}x{size}@2x.png"))

    return iconset_dir


if __name__ == "__main__":
    base = os.path.dirname(os.path.abspath(__file__))

    print("Drawing icon...")
    icon = draw_icon()

    print("Creating iconset...")
    iconset = create_iconset(icon, base)

    print("Converting to .icns...")
    icns_path = os.path.join(base, "AppIcon.icns")
    subprocess.run(["iconutil", "-c", "icns", iconset, "-o", icns_path], check=True)

    icon.save(os.path.join(base, "icon_preview.png"))
    print(f"Done! {icns_path}")
