#!/usr/bin/env python3
"""
Create a crisp, modern placeholder fallback image for no-match media scenarios.
Optimized for cross-platform asset resolution (Android/Linux/Windows).
"""

import os
import sys
from PIL import Image, ImageDraw, ImageFont

def create_placeholder():
    """Generates a high-quality, theme-matching placeholder asset."""
    # Scale up resolution to 512x512 for crisper display on high-DPI mobile screens
    width, height = 512, 512
    
    # Background color dynamically matches the app_modern.kv dark canvas (#07090d)
    img = Image.new('RGB', (width, height), color=(0x07, 0x09, 0x13))
    draw = ImageDraw.Draw(img, 'RGBA')
    
    # 1. Draw Decorative Background Radials (Polished Opacity)
    for i in range(4):
        r = 160 + i * 45
        draw.ellipse(
            [(width//2 - r, height//2 - r), (width//2 + r, height//2 + r)],
            outline=(0x1c, 0x50, 0xec, 25), # Matches top-header blue theme with alpha transparency
            width=2
        )
    
    # 2. Draw Vector Lion Core Representation
    # Lion Mane
    draw.polygon(
        [
            (width//2, height//2 - 120),
            (width//2 - 100, height//2 - 70),
            (width//2 - 90, height//2 - 20),
            (width//2, height//2 - 45),
            (width//2 + 90, height//2 - 20),
            (width//2 + 100, height//2 - 70),
        ],
        fill=(0xff, 0x7a, 0x00, 220)
    )
    # Lion Head
    draw.ellipse(
        [(width//2 - 75, height//2 - 95), (width//2 + 75, height//2 - 25)],
        fill=(0xff, 0xc3, 0x00, 240)
    )
    # Lion Body Base
    draw.ellipse(
        [(width//2 - 60, height//2 - 25), (width//2 + 60, height//2 + 90)],
        fill=(0xff, 0xc3, 0x00, 190)
    )
    
    # 3. Dynamic Cross-Platform Font Loading
    # Looks for your custom asset font first, falls back to common system locations cleanly
    base_path = os.path.dirname(os.path.abspath(__file__))
    asset_font_path = os.path.join(base_path, 'assets', 'fonts', 'FontAwesome.ttf')
    
    font = None
    title_font = None
    
    font_candidates = [
        asset_font_path,
        "/system/fonts/Roboto-Bold.ttf", # Android standard primary font
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", # Linux Desktop
        "C:\\Windows\\Fonts\\arialbd.ttf" # Windows Desktop
    ]
    
    for path in font_candidates:
        if os.path.exists(path):
            try:
                font = ImageFont.truetype(path, 28)
                title_font = ImageFont.truetype(path, 18)
                break
            except Exception:
                continue

    # Ultimate fail-safe if absolute font assets are missing entirely
    if font is None:
        font = ImageFont.load_default()
        title_font = ImageFont.load_default()
    
    # 4. Text Layout Engine Adjustments
    main_text = "DANCING LION"
    bbox = draw.textbbox((0, 0), main_text, font=font)
    text_width = bbox[2] - bbox[0]
    draw.text(
        ((width - text_width) // 2, height - 105),
        main_text,
        fill=(0x33, 0xd4, 0x9c, 255), # Clean modern neon green accent color
        font=font
    )
    
    subtitle = "Searching Online Repository"
    bbox = draw.textbbox((0, 0), subtitle, font=title_font)
    subtitle_width = bbox[2] - bbox[0]
    draw.text(
        ((width - subtitle_width) // 2, height - 65),
        subtitle,
        fill=(0xff, 0xff, 0xff, 160),
        font=title_font
    )
    
    # 5. Safe Asset Directory Resolution
    assets_dir = os.path.join(base_path, 'assets', 'images')
    os.makedirs(assets_dir, exist_ok=True)
    output_path = os.path.join(assets_dir, 'dancing_lion.png')
    
    # Save the updated image asset file
    img.save(output_path, "PNG")
    print(f"✓ Modern placeholder canvas generated successfully: {output_path}")

if __name__ == "__main__":
    create_placeholder()