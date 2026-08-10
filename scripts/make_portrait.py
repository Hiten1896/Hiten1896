#!/usr/bin/env python3
"""
scripts/make_portrait.py
Generates a self-contained ascii.svg profile portrait using rembg (with OpenCV fallback),
bilateral filtering, CLAHE contrast tuning, and SMIL typing animation reveal.
"""

import os
import sys
import xml.sax.saxutils as xml_escape
import numpy as np

def find_profile_image():
    candidates = ["profile.jpg", "profile.jpg.jpg", "profile.jpeg", "profile.png"]
    for c in candidates:
        if os.path.exists(c):
            return c
    raise FileNotFoundError(f"No profile image found. Candidates checked: {candidates}")

def remove_background(pil_img):
    """Attempt background removal via rembg, with fast fallback to OpenCV edge/threshold isolation."""
    import cv2
    rgb = np.array(pil_img.convert("RGB"))

    # If u2net model exists or rembg can be called quickly
    u2net_path = os.path.expanduser("~/.u2net/u2net.onnx")
    if os.path.exists(u2net_path):
        try:
            import rembg
            print("Removing background using cached rembg u2net model...")
            no_bg = rembg.remove(pil_img)
            return np.array(no_bg)
        except Exception as e:
            print(f"rembg processing warning: {e}")

    # Try rembg with fast fail if model not cached locally yet
    if not os.path.exists(u2net_path) and os.environ.get("CI") == "true":
        try:
            import rembg
            print("Running rembg background removal in CI...")
            no_bg = rembg.remove(pil_img)
            return np.array(no_bg)
        except Exception as e:
            print(f"rembg warning: {e}")

    print("Using OpenCV bilateral & adaptive thresholding for foreground mask...")
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    blurred = cv2.bilateralFilter(gray, d=9, sigmaColor=75, sigmaSpace=75)

    # Adaptive thresholding to segment subject from light background
    _, mask = cv2.threshold(blurred, 235, 255, cv2.THRESH_BINARY_INV)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

    rgba = np.dstack((rgb, mask))
    return rgba

def generate_ascii_portrait():
    from PIL import Image
    import cv2

    image_path = find_profile_image()
    print(f"Loading input profile image: {image_path}")

    input_image = Image.open(image_path).convert("RGBA")

    # 1. Remove background
    rgba_np = remove_background(input_image)

    rgb = rgba_np[:, :, :3]
    alpha = rgba_np[:, :, 3]

    # Convert to grayscale
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)

    # 2. Apply bilateral filter for skin smoothing while preserving edges
    smoothed = cv2.bilateralFilter(gray, d=9, sigmaColor=75, sigmaSpace=75)

    # 3. Apply CLAHE & contrast tuning
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(smoothed)

    # Normalize contrast to full 0..255 range
    enhanced = cv2.normalize(enhanced, None, alpha=0, beta=255, norm_type=cv2.NORM_MINMAX)

    # Output dimensions (ASCII grid width and height)
    num_cols = 84
    aspect_ratio_correction = 0.52  # Monospace char height vs width ratio
    orig_h, orig_w = enhanced.shape
    num_rows = int((orig_h / orig_w) * num_cols * aspect_ratio_correction)

    # Resize image and alpha mask to grid size
    resized_gray = cv2.resize(enhanced, (num_cols, num_rows), interpolation=cv2.INTER_AREA)
    resized_alpha = cv2.resize(alpha, (num_cols, num_rows), interpolation=cv2.INTER_AREA)

    # ASCII character ramp (12 characters, from space to heavy char)
    ramp = " .:-=+*cs#%@"
    ramp_len = len(ramp)

    # Map pixels to character lines
    ascii_grid = []
    for r in range(num_rows):
        row_chars = []
        for c in range(num_cols):
            a = resized_alpha[r, c]
            if a < 40:  # Background threshold
                row_chars.append(" ")
            else:
                val = resized_gray[r, c]
                char_idx = int((val / 255.0) * (ramp_len - 1))
                char_idx = max(0, min(ramp_len - 1, char_idx))
                row_chars.append(ramp[char_idx])
        ascii_grid.append("".join(row_chars))

    # SVG layout metrics
    char_width = 7.2
    line_height = 11.5
    margin_x = 24
    margin_y = 30

    svg_width = int(num_cols * char_width + margin_x * 2)
    svg_height = int(num_rows * line_height + margin_y * 2)

    # Build SVG content with SMIL animation reveal per row
    svg_lines = []
    svg_lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {svg_width} {svg_height}" width="{svg_width}" height="{svg_height}">')
    svg_lines.append('  <style>')
    svg_lines.append('    .bg { fill: #0d1117; rx: 12px; ry: 12px; }')
    svg_lines.append('    .border { fill: none; stroke: #30363d; stroke-width: 1.5; rx: 12px; ry: 12px; }')
    svg_lines.append('    .ascii-text { font-family: "JetBrains Mono", "Fira Code", "Courier New", monospace; font-size: 10px; font-weight: 600; white-space: pre; }')
    svg_lines.append('    .title { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; font-size: 12px; font-weight: 600; fill: #8b949e; }')
    svg_lines.append('    .glow { text-shadow: 0 0 5px rgba(88, 166, 255, 0.4); }')
    svg_lines.append('  </style>')

    # Background card
    svg_lines.append(f'  <rect class="bg" width="{svg_width}" height="{svg_height}" />')
    svg_lines.append(f'  <rect class="border" width="{svg_width - 2}" height="{svg_height - 2}" x="1" y="1" />')

    # Card Title / Header dot indicators
    svg_lines.append('  <circle cx="20" cy="18" r="5" fill="#ff5f56" />')
    svg_lines.append('  <circle cx="36" cy="18" r="5" fill="#ffbd2e" />')
    svg_lines.append('  <circle cx="52" cy="18" r="5" fill="#27c93f" />')
    svg_lines.append(f'  <text x="{svg_width - 20}" y="22" text-anchor="end" class="title">ascii_portrait.py</text>')

    # Group for ASCII rows
    svg_lines.append('  <g class="ascii-text">')

    row_delay_step = 0.04  # seconds delay per row reveal
    for idx, line_str in enumerate(ascii_grid):
        y_pos = margin_y + 12 + (idx * line_height)
        escaped_line = xml_escape.escape(line_str)
        begin_sec = round(idx * row_delay_step, 3)

        # Color gradient effect (blue to cyan glow)
        ratio = idx / max(1, num_rows - 1)
        r_val = int(88 + (100 * ratio))
        g_val = int(166 + (60 * (1 - ratio)))
        b_val = 255
        color_hex = f"#{r_val:02x}{g_val:02x}{b_val:02x}"

        svg_lines.append(
            f'    <text x="{margin_x}" y="{y_pos:.1f}" fill="{color_hex}" opacity="0">'
            f'<animate attributeName="opacity" values="0;1" begin="{begin_sec}s" dur="0.12s" fill="freeze" />'
            f'{escaped_line}</text>'
        )

    svg_lines.append('  </g>')
    svg_lines.append('</svg>')

    output_path = "ascii.svg"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(svg_lines))

    print(f"Successfully generated {output_path} ({svg_width}x{svg_height}px)")

if __name__ == "__main__":
    generate_ascii_portrait()
