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
    <!-- Animated Gradient Border -->
    <linearGradient id="border-grad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#58a6ff">
        <animate attributeName="stop-color" values="#58a6ff;#a371f7;#f778ba;#58a6ff" dur="4s" repeatCount="indefinite" />
      </stop>
      <stop offset="50%" stop-color="#1f6feb">
        <animate attributeName="stop-color" values="#1f6feb;#58a6ff;#a371f7;#1f6feb" dur="4s" repeatCount="indefinite" />
      </stop>
      <stop offset="100%" stop-color="#a371f7">
        <animate attributeName="stop-color" values="#a371f7;#f778ba;#58a6ff;#a371f7" dur="4s" repeatCount="indefinite" />
      </stop>
    </linearGradient>

    <!-- Avatar Image Clip Path (Rounded Square) -->
    <clipPath id="avatar-clip">
      <rect x="{pad}" y="{pad}" width="{avatar_size}" height="{avatar_size}" rx="20" ry="20" />
    </clipPath>

    <!-- Soft Glow Filter -->
    <filter id="glow-effect" x="-30%" y="-30%" width="160%" height="160%">
      <feGaussianBlur stdDeviation="6" result="blur" />
      <feComposite in="SourceGraphic" in2="blur" operator="over" />
    </filter>
  </defs>

  <style>
    .card-bg {{
      fill: #0d1117;
      rx: 24px;
      ry: 24px;
    }}
    .card-border {{
      fill: none;
      stroke: url(#border-grad);
      stroke-width: 2.5;
      rx: 24px;
      ry: 24px;
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
  <rect class="card-border" width="{size-4}" height="{size-4}" x="2" y="2">
    <animate attributeName="stroke-width" values="2;3;2" dur="3s" repeatCount="indefinite" />
  </rect>

  <!-- Animated Avatar Group — slow 3.5s entrance so users see it arrive -->
  <g opacity="0">
    <!-- Slow fade from invisible to fully visible -->
    <animate attributeName="opacity" values="0;0;0.3;0.7;1" keyTimes="0;0.1;0.4;0.7;1" begin="0.3s" dur="3.5s" fill="freeze" />
    <!-- Gentle scale-up from 85% to 100% -->
    <animateTransform attributeName="transform" type="scale" values="0.85;0.97;1.0" keyTimes="0;0.7;1" begin="0.3s" dur="3.5s" fill="freeze" calcMode="spline" keySplines="0.33 1 0.68 1; 0.33 1 0.68 1" />

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
