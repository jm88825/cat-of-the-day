#!/usr/bin/env python3
"""Build all app icon / splash / store images from the kitten photo.

    tools/.venv/bin/python tools/make-icons.py      (needs Pillow)

Source: app/assets/source/kitten-icon-source.png (1024x1024, chosen by the owner).
Writes app/assets/{icon,android-icon-foreground,android-icon-background,
splash-icon,favicon}.png, store-assets/icon-512.png and previews/ (not shipped).
"""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "app/assets/source/kitten-icon-source.png"
ASSETS = ROOT / "app/assets"
STORE = ROOT / "store-assets"
PREVIEW = ROOT / "store-assets/previews"
SIZE = 1024
PEACH = (243, 201, 169)          # mid-tone of the photo's backdrop (#F3C9A9)
FACE_CENTER = (500, 470)         # approx. kitten face centre in the source photo
FG_SCALE = 0.62                  # keeps ears + face inside the 66% adaptive-icon circle


def feathered_rect_mask(w, h, feather):
    m = Image.new("L", (w, h), 0)
    ImageDraw.Draw(m).rectangle([feather, feather, w - feather, h - feather], fill=255)
    return m.filter(ImageFilter.GaussianBlur(feather / 2))


def circle_mask(size, inset=0, feather=0):
    m = Image.new("L", (size, size), 0)
    ImageDraw.Draw(m).ellipse([inset, inset, size - inset, size - inset], fill=255)
    return m.filter(ImageFilter.GaussianBlur(feather)) if feather else m


def main():
    src = Image.open(SRC).convert("RGB").resize((SIZE, SIZE), Image.LANCZOS)
    PREVIEW.mkdir(parents=True, exist_ok=True)

    # Legacy / iOS / web icon: the photo full-bleed (launchers round it).
    src.save(ASSETS / "icon.png", optimize=True)
    src.resize((48, 48), Image.LANCZOS).save(ASSETS / "favicon.png", optimize=True)
    src.resize((512, 512), Image.LANCZOS).save(STORE / "icon-512.png", optimize=True)

    # Adaptive icon background: the same backdrop, blurred into a smooth peach gradient.
    bg = src.filter(ImageFilter.GaussianBlur(140))
    bg.save(ASSETS / "android-icon-background.png", optimize=True)

    # Adaptive icon foreground: kitten scaled into the safe zone, edges feathered
    # so they melt into the background layer.
    s = int(SIZE * FG_SCALE)
    kit = src.resize((s, s), Image.LANCZOS).convert("RGBA")
    kit.putalpha(feathered_rect_mask(s, s, 46))
    fg = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    ox = round(SIZE / 2 - FACE_CENTER[0] * FG_SCALE)
    oy = round(SIZE / 2 - 12 - FACE_CENTER[1] * FG_SCALE)
    fg.alpha_composite(kit, (ox, oy))
    fg.save(ASSETS / "android-icon-foreground.png", optimize=True)

    # Splash: round kitten portrait on transparent (expo-splash-screen adds the bg colour).
    splash = src.convert("RGBA")
    splash.putalpha(circle_mask(SIZE, inset=8, feather=3))
    splash.save(ASSETS / "splash-icon.png", optimize=True)

    # Previews of what Android launchers show (66.7% viewport of the 108dp layers).
    composed = bg.convert("RGBA")
    composed.alpha_composite(fg)
    vp = round(SIZE * 72 / 108)
    off = (SIZE - vp) // 2
    view = composed.crop((off, off, off + vp, off + vp)).resize((432, 432), Image.LANCZOS)
    for name, shape in (("adaptive-circle", "circle"), ("adaptive-squircle", "squircle")):
        m = Image.new("L", view.size, 0)
        d = ImageDraw.Draw(m)
        if shape == "circle":
            d.ellipse([0, 0, *view.size], fill=255)
        else:
            d.rounded_rectangle([0, 0, *view.size], radius=120, fill=255)
        out = Image.new("RGBA", view.size, (255, 255, 255, 0))
        out.paste(view, (0, 0), m)
        out.save(PREVIEW / f"icon-{name}-preview.png")
    sheet = Image.new("RGB", (432 * 2 + 60, 432 + 40), (32, 32, 36))
    for i, name in enumerate(("adaptive-circle", "adaptive-squircle")):
        im = Image.open(PREVIEW / f"icon-{name}-preview.png")
        sheet.paste(im, (20 + i * (432 + 20), 20), im)
    sheet.save(PREVIEW / "icon-masks-on-dark.png")
    print("icons written")


if __name__ == "__main__":
    main()
