#!/usr/bin/env python3
"""
Create a crisp, modern placeholder fallback image for no-match media scenarios.
Optimized for cross-platform asset resolution (Android/Linux/Windows).
"""

import os
import sys
from PIL import Image, ImageDraw, ImageFont


def _get_text_dimensions(draw_obj, text, font):
    """Calculates text bounding box safely across different Pillow versions."""
    try:
        bbox = draw_obj.textbbox((0, 0), text, font=font)
        return bbox[2] - bbox[0], bbox[3] - bbox[1]
    except Exception:
        # Fallback for legacy Pillow builds or basic default fonts
        return draw_obj.textlength(text, font=font), 20


def create_placeholder():
    """Generates a high-quality, theme-matching placeholder asset."""
    # Scale up resolution to 512x512 for crisper display on high-DPI mobile screens
    width, height = 512, 512
    
    # Initialize in RGBA mode for smooth alpha-channel blending of geometric shapes
    img = Image.new('RGBA', (width, height), color=(0x07, 0x09, 0x13, 0xff))
    draw = ImageDraw.Draw(img)
    
    # 1. Draw Decorative Background Radials (Polished Opacity)
    for i in range(4):
        r = 160 + i * 45
        draw.ellipse(
            [(width // 2 - r, height // 2 - r), (width // 2 + r, height // 2 + r)],
            outline=(0x1c, 0x50, 0xec, 40),  # Top-header blue theme accent with alpha
            width=2
        )
    
    # 2. Draw Vector Lion Core Representation
    # Lion Mane
    draw.polygon(
        [
            (width // 2, height // 2 - 120),
            (width // 2 - 100, height // 2 - 70),
            (width // 2 - 90, height // 2 - 20),
            (width // 2, height // 2 - 45),
            (width // 2 + 90, height // 2 - 20),
            (width // 2 + 100, height // 2 - 70),
        ],
        fill=(0xff, 0x7a, 0x00, 220)
    )
    # Lion Head
    draw.ellipse(
        [(width // 2 - 75, height // 2 - 95), (width // 2 + 75, height // 2 - 25)],
        fill=(0xff, 0xc3, 0x00, 240)
    )
    # Lion Body Base
    draw.ellipse(
        [(width // 2 - 60, height // 2 - 25), (width // 2 + 60, height // 2 + 90)],
        fill=(0xff, 0xc3, 0x00, 190)
    )
    
    # 3. Dynamic Cross-Platform Font Loading
    base_path = os.path.dirname(os.path.abspath(__file__))
    asset_font_path = os.path.join(base_path, 'assets', 'fonts', 'FontAwesome.ttf')
    
    font = None
    title_font = None
    
    font_candidates = [
        asset_font_path,
        "/system/fonts/Roboto-Bold.ttf",       # Android standard primary bold
        "/system/fonts/Roboto-Regular.ttf",    # Android standard regular
        "/system/fonts/DroidSans.ttf",         # Android legacy fallback
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", # Linux Desktop
        "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",            # Arch Linux
        "C:\\Windows\\Fonts\\arialbd.ttf",     # Windows Desktop Bold
        "C:\\Windows\\Fonts\\arial.ttf"        # Windows Desktop Standard
    ]
    
    for path in font_candidates:
        if os.path.exists(path):
            try:
                font = ImageFont.truetype(path, 28)
                title_font = ImageFont.truetype(path, 18)
                break
            except Exception:
                continue

    # Ultimate fail-safe if no system fonts match
    if font is None:
        font = ImageFont.load_default()
        title_font = ImageFont.load_default()
    
    # 4. Text Layout Engine Adjustments
    main_text = "DANCING LION"
    text_width, _ = _get_text_dimensions(draw, main_text, font)
    draw.text(
        ((width - text_width) // 2, height - 105),
        main_text,
        fill=(0x33, 0xd4, 0x9c, 255),  # Modern neon green accent color
        font=font
    )
    
    subtitle = "Searching Online Repository"
    subtitle_width, _ = _get_text_dimensions(draw, subtitle, title_font)
    draw.text(
        ((width - subtitle_width) // 2, height - 65),
        subtitle,
        fill=(0xff, 0xff, 0xff, 160),
        font=title_font
    )
    
    # 5. Safe Asset Directory Resolution & Export
    assets_dir = os.path.join(base_path, 'assets', 'images')
    os.makedirs(assets_dir, exist_ok=True)
    output_path = os.path.join(assets_dir, 'dancing_lion.png')
    
    # Flatten canvas to RGB before saving PNG
    final_img = img.convert('RGB')
    final_img.save(output_path, "PNG")
    print(f"✓ Modern placeholder canvas generated successfully: {output_path}")
    return output_path


if __name__ == "__main__":
    create_placeholder()