#!/usr/bin/env python3
"""
scripts/make_portrait.py
Crops profile.jpg into a clean square format, base64 encodes it into a crisp, high-res
vector-styled SVG container (ascii.svg), and injects a smooth fade-in / scale animation.
"""

import os
import base64
import io
from PIL import Image

def find_profile_image():
    candidates = ["profile.jpg", "profile.jpg.jpg", "profile.jpeg", "profile.png"]
    for c in candidates:
        if os.path.exists(c):
            return c
    raise FileNotFoundError(f"No profile image found. Candidates checked: {candidates}")

def crop_center_square(img):
    """Crop PIL image to a center-focused square."""
    width, height = img.size
    crop_size = min(width, height)
    left = (width - crop_size) // 2
    top = (height - crop_size) // 2
    right = left + crop_size
    bottom = top + crop_size
    return img.crop((left, top, right, bottom))

def generate_logo_portrait():
    image_path = find_profile_image()
    print(f"Loading branding profile image: {image_path}")

    # Load and crop to square
    raw_img = Image.open(image_path).convert("RGB")
    square_img = crop_center_square(raw_img)

    # Resize to crisp high resolution (800x800)
    high_res_img = square_img.resize((800, 800), Image.Resampling.LANCZOS)

    # Encode to base64 JPEG
    buffer = io.BytesIO()
    high_res_img.save(buffer, format="JPEG", quality=95)
    img_b64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
    data_uri = f"data:image/jpeg;base64,{img_b64}"

    # SVG Card Dimensions
    size = 480
    pad = 20
    avatar_size = size - (pad * 2)

    # Build SVG content with smooth scaling & fade-in animation
    svg_content = f"""<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 {size} {size}" width="{size}" height="{size}">
  <defs>
    <!-- Dark Mode Card Gradient Border -->
    <linearGradient id="border-grad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#58a6ff" />
      <stop offset="50%" stop-color="#1f6feb" />
      <stop offset="100%" stop-color="#a371f7" />
    </linearGradient>

    <!-- Avatar Image Clip Path (Rounded Square) -->
    <clipPath id="avatar-clip">
      <rect x="{pad}" y="{pad}" width="{avatar_size}" height="{avatar_size}" rx="20" ry="20" />
    </clipPath>

    <!-- Glow Filter -->
    <filter id="glow-effect" x="-20%" y="-20%" width="140%" height="140%">
      <feGaussianBlur stdDeviation="8" result="blur" />
      <feComposite in="SourceGraphic" in2="blur" operator="over" />
    </filter>
  </defs>

  <style>
    @keyframes fadeInScale {{
      0% {{
        opacity: 0;
        transform: scale(0.92);
      }}
      100% {{
        opacity: 1;
        transform: scale(1);
      }}
    }}
    .card-bg {{
      fill: #0d1117;
      rx: 24px;
      ry: 24px;
    }}
    .card-border {{
      fill: none;
      stroke: url(#border-grad);
      stroke-width: 2;
      rx: 24px;
      ry: 24px;
    }}
    .avatar-wrapper {{
      transform-origin: center;
      animation: fadeInScale 1.2s cubic-bezier(0.16, 1, 0.3, 1) forwards;
    }}
    .avatar-frame {{
      fill: #161b22;
      stroke: #30363d;
      stroke-width: 1.5;
      rx: 22px;
      ry: 22px;
    }}
  </style>

  <!-- Container Card -->
  <rect class="card-bg" width="{size}" height="{size}" />
  <rect class="card-border" width="{size-4}" height="{size-4}" x="2" y="2" />

  <!-- Animated Avatar Group -->
  <g class="avatar-wrapper">
    <animate attributeName="opacity" values="0;1" begin="0s" dur="1.0s" fill="freeze" />
    <animateTransform attributeName="transform" type="scale" values="0.94;1.0" begin="0s" dur="1.0s" additive="sum" fill="freeze" />

    <!-- Frame Background -->
    <rect class="avatar-frame" x="{pad-1}" y="{pad-1}" width="{avatar_size+2}" height="{avatar_size+2}" />

    <!-- Base64 Embedded High-Res Image -->
    <image href="{data_uri}" x="{pad}" y="{pad}" width="{avatar_size}" height="{avatar_size}" clip-path="url(#avatar-clip)" preserveAspectRatio="xMidYMid slice" />
  </g>
</svg>"""

    output_path = "ascii.svg"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(svg_content)

    print(f"Successfully generated high-res animated portrait vector {output_path} ({size}x{size}px)")

if __name__ == "__main__":
    generate_logo_portrait()
