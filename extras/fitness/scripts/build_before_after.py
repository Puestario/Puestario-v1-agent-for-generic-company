#!/usr/bin/env python3
"""
Before/after comparison card generator.
Smart alignment: body-scale normalization + waistband anchoring + direction correction.
Requires: Pillow (pip install Pillow)

Configure the constants at the top before running.
"""
from PIL import Image, ImageDraw, ImageFont, ImageOps
import os

PHOTOS_DIR = "/tmp/client_photos"
OUT_DIR    = "YOUR_OUTPUT_DIR"  # e.g. /path/to/workspace/reports
os.makedirs(OUT_DIR, exist_ok=True)

# ─── CLIENT INFO — fill these in per session ─────────────────────────────────
CLIENT_NAME  = "YOUR_CLIENT_NAME"
BEFORE_DATE  = "YOUR_BEFORE_DATE"   # e.g. "January 1, 2026"
AFTER_DATE   = "YOUR_AFTER_DATE"    # e.g. "March 1, 2026"
PROGRAM      = "YOUR_PROGRAM_NAME"  # e.g. "12-WEEK PROGRAM"
AFTER_WEIGHT = ""              # e.g. "145 lbs" or "" to omit
# ─────────────────────────────────────────────────────────────────────────────

# ─── BRAND COLORS — customize to match your brand ────────────────────────────
BG_COLOR    = (10, 10, 10)
PANEL_COLOR = (18, 18, 18)
ACCENT      = (232, 84, 32)    # YOUR_BRAND_COLOR — replace this RGB tuple, not the comment
WHITE       = (255, 255, 255)
GRAY        = (150, 150, 150)
BRAND_NAME  = "YOUR_BRAND_NAME"
# ─────────────────────────────────────────────────────────────────────────────

CARD_W   = 1080
PHOTO_H  = 660
HEADER_H = 60
LABEL_H  = 60
FOOTER_H = 80
CARD_H   = HEADER_H + PHOTO_H + LABEL_H + FOOTER_H
PHOTO_W  = CARD_W // 2

WAISTBAND_TARGET_Y = 270

# Per-image calibration — adjust waistband_frac per photo
# waistband_frac: top of shorts as fraction of original image height (0.0–1.0)
# flip: True to mirror horizontally
CALIBRATION = {
    'before_front': dict(waistband_frac=0.488, flip=False),
    'after_front':  dict(waistband_frac=0.450, flip=False),
    'before_side':  dict(waistband_frac=0.400, flip=True),
    'after_side':   dict(waistband_frac=0.363, flip=True),
    'before_back':  dict(waistband_frac=0.481, flip=False),
    'after_back':   dict(waistband_frac=0.413, flip=False),
}


def smart_prepare(img: Image.Image, key: str) -> Image.Image:
    cfg = CALIBRATION[key]
    w, h = img.size

    if cfg['flip']:
        img = ImageOps.mirror(img)

    scale = PHOTO_W / w
    new_w = PHOTO_W
    new_h = int(h * scale)
    img   = img.resize((new_w, new_h), Image.LANCZOS)

    waist_y = cfg['waistband_frac'] * h * scale
    top    = int(waist_y - WAISTBAND_TARGET_Y)
    bottom = top + PHOTO_H

    if top < 0:
        pad = Image.new("RGB", (new_w, new_h - top), BG_COLOR)
        pad.paste(img, (0, -top))
        img, new_h = pad, new_h - top
        top, bottom = 0, PHOTO_H
    if bottom > new_h:
        pad = Image.new("RGB", (new_w, bottom), BG_COLOR)
        pad.paste(img, (0, 0))
        img, new_h = pad, bottom

    img = img.crop((0, top, new_w, bottom))

    if new_w > PHOTO_W:
        left = (new_w - PHOTO_W) // 2
        img  = img.crop((left, 0, left + PHOTO_W, PHOTO_H))
    elif new_w < PHOTO_W:
        pad = Image.new("RGB", (PHOTO_W, PHOTO_H), BG_COLOR)
        pad.paste(img, ((PHOTO_W - new_w) // 2, 0))
        img = pad

    return img


def load_font(path, size):
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.load_default()


FB = "/System/Library/Fonts/HelveticaNeue.ttc"
FR = "/System/Library/Fonts/Helvetica.ttc"

f_client = load_font(FB, 28)
f_prog   = load_font(FR, 16)
f_tag    = load_font(FB, 20)
f_date   = load_font(FR, 14)
f_label  = load_font(FB, 22)
f_brand  = load_font(FB, 14)


def center_text(draw, text, y, x0, x1, font, color):
    try:
        bbox = draw.textbbox((0, 0), text, font=font)
        tw   = bbox[2] - bbox[0]
    except Exception:
        tw = len(text) * 10
    draw.text((x0 + (x1 - x0 - tw) // 2, y), text, fill=color, font=font)


def build_card(view: str, before_path: str, after_path: str) -> str:
    canvas = Image.new("RGB", (CARD_W, CARD_H), BG_COLOR)
    draw   = ImageDraw.Draw(canvas)

    draw.rectangle([0, 0, CARD_W, 4], fill=ACCENT)
    center_text(draw, CLIENT_NAME, 10, 0, CARD_W, f_client, WHITE)
    center_text(draw, PROGRAM,     40, 0, CARD_W, f_prog,   GRAY)

    photo_y = HEADER_H
    sides = [
        ("BEFORE", before_path, f"before_{view.lower()}", 0,      BEFORE_DATE, ""),
        ("AFTER",  after_path,  f"after_{view.lower()}",  PHOTO_W, AFTER_DATE,  AFTER_WEIGHT),
    ]

    for label, path, cal_key, x_off, date_str, wt_str in sides:
        img = Image.open(path).convert("RGB")
        img = smart_prepare(img, cal_key)

        ov = Image.new("RGBA", (PHOTO_W, PHOTO_H), (0, 0, 0, 0))
        gd = ImageDraw.Draw(ov)
        for row in range(55):
            a = int((55 - row) / 55 * 150)
            gd.line([(0, row), (PHOTO_W, row)], fill=(0, 0, 0, a))
        img = Image.alpha_composite(img.convert("RGBA"), ov).convert("RGB")
        canvas.paste(img, (x_off, photo_y))

        tc = ACCENT if label == "AFTER" else (35, 35, 35)
        tw_t, th_t = 88, 26
        tx, ty = x_off + 12, photo_y + 10
        draw.rectangle([tx, ty, tx + tw_t, ty + th_t], fill=tc)
        center_text(draw, label, ty + 4, tx, tx + tw_t, f_tag, WHITE)

    cx = CARD_W // 2
    draw.rectangle([cx - 1, photo_y, cx + 1, photo_y + PHOTO_H], fill=ACCENT)

    ly = photo_y + PHOTO_H
    draw.rectangle([0,      ly, PHOTO_W, ly + LABEL_H], fill=PANEL_COLOR)
    draw.rectangle([PHOTO_W, ly, CARD_W, ly + LABEL_H], fill=(22, 22, 22))
    center_text(draw, BEFORE_DATE,             ly + 8,  0,      PHOTO_W, f_date,  GRAY)
    center_text(draw, view.upper() + " VIEW",  ly + 30, 0,      PHOTO_W, f_label, WHITE)
    center_text(draw, AFTER_DATE,              ly + 8,  PHOTO_W, CARD_W, f_date,  GRAY)
    after_lbl = view.upper() + " VIEW" + (f"  ·  {AFTER_WEIGHT}" if AFTER_WEIGHT else "")
    center_text(draw, after_lbl,               ly + 30, PHOTO_W, CARD_W, f_label, WHITE)

    fy = ly + LABEL_H
    draw.rectangle([0, fy, CARD_W, CARD_H], fill=(14, 14, 14))
    draw.rectangle([0, fy, CARD_W, fy + 1], fill=(40, 40, 40))
    center_text(draw, BRAND_NAME, fy + (FOOTER_H - 18) // 2, 0, CARD_W, f_brand, ACCENT)
    draw.rectangle([0, CARD_H - 4, CARD_W, CARD_H], fill=ACCENT)

    out = os.path.join(OUT_DIR, f"client_{view.lower()}_comparison.jpg")
    canvas.save(out, "JPEG", quality=92)
    print(f"Saved: {out}")
    return out


if __name__ == "__main__":
    for v in ["Front", "Side", "Back"]:
        b = os.path.join(PHOTOS_DIR, f"before_{v.lower()}.jpg")
        a = os.path.join(PHOTOS_DIR, f"after_{v.lower()}.jpg")
        if os.path.exists(b) and os.path.exists(a):
            build_card(v, b, a)
        else:
            print(f"Missing photos for {v}: before={os.path.exists(b)} after={os.path.exists(a)}")
