"""
Generate app icons in multiple sizes using matplotlib.
Run once: python generate_icon.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, Circle, Arc, Wedge
from matplotlib.patheffects import withStroke
import numpy as np

def draw_icon(ax, size=512):
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.set_aspect('equal')
    ax.axis('off')

    # ── Background: deep navy rounded square ──────────────────────────────────
    bg = FancyBboxPatch((2, 2), 96, 96,
                        boxstyle="round,pad=4",
                        facecolor="#0D1B2E", edgecolor="none", zorder=0)
    ax.add_patch(bg)

    # ── Subtle gradient overlay strips (depth) ────────────────────────────────
    for i, alpha in enumerate(np.linspace(0.0, 0.06, 8)):
        strip = mpatches.FancyBboxPatch(
            (2, 2 + i*12), 96, 12,
            boxstyle="square,pad=0",
            facecolor="#4FA3E0", edgecolor="none", alpha=alpha, zorder=1)
        ax.add_patch(strip)

    # ── Gear / sprocket ring (automotive identity) ────────────────────────────
    cx, cy, r_outer, r_inner = 50, 52, 32, 22
    n_teeth = 12
    theta = np.linspace(0, 2*np.pi, n_teeth * 4 + 1)

    gear_x, gear_y = [], []
    for i, t in enumerate(theta[:-1]):
        seg = i % 4
        if seg == 0:   r = r_outer + 4.5
        elif seg == 1: r = r_outer + 4.5
        elif seg == 2: r = r_outer
        else:          r = r_outer
        gear_x.append(cx + r * np.cos(t))
        gear_y.append(cy + r * np.sin(t))
    gear_x.append(gear_x[0]); gear_y.append(gear_y[0])

    ax.fill(gear_x, gear_y, color="#1E3A5F", zorder=2)
    ax.plot(gear_x, gear_y, color="#2A6DBB", linewidth=0.8, zorder=3)

    # Outer ring
    ring_out = Circle((cx, cy), r_outer, fill=False,
                      edgecolor="#2A6DBB", linewidth=1.8, zorder=4)
    ax.add_patch(ring_out)

    # Inner hole
    hole = Circle((cx, cy), r_inner, facecolor="#0D1B2E",
                  edgecolor="#1565C0", linewidth=1.4, zorder=5)
    ax.add_patch(hole)

    # ── PMO diamond / chart bars inside gear ──────────────────────────────────
    # Three rising bars — Gantt / progress metaphor
    bar_specs = [
        (cx-10, cy-8, 7, 6,  "#1E88E5"),
        (cx-1,  cy-8, 7, 11, "#42A5F5"),
        (cx+8,  cy-8, 7, 16, "#64B5F6"),
    ]
    for bx, by, bw, bh, bc in bar_specs:
        bar = mpatches.FancyBboxPatch((bx, by), bw, bh,
                                      boxstyle="round,pad=0.6",
                                      facecolor=bc, edgecolor="none",
                                      alpha=0.95, zorder=6)
        ax.add_patch(bar)

    # Upward trend arrow tip
    ax.annotate("", xy=(cx+16, cy+12), xytext=(cx-12, cy-4),
                arrowprops=dict(arrowstyle="->,head_width=2.5,head_length=2.5",
                                color="#7DD3FC", lw=1.6),
                zorder=7)

    # ── Checkmark ring (milestone complete) ───────────────────────────────────
    check_arc = Arc((cx, cy), r_inner*1.35, r_inner*1.35,
                    angle=0, theta1=30, theta2=330,
                    color="#00ACC1", linewidth=2.0, zorder=5)
    ax.add_patch(check_arc)

    # ── "O" Orhan monogram — top left corner ─────────────────────────────────
    mono_bg = Circle((18, 83), 10, facecolor="#1565C0",
                     edgecolor="none", zorder=7)
    ax.add_patch(mono_bg)
    ax.text(18, 83, "O", ha='center', va='center',
            fontsize=10, fontweight='bold', color='white',
            fontfamily='DejaVu Sans', zorder=8)

    # ── "PMO" text ────────────────────────────────────────────────────────────
    ax.text(50, 14, "PMO", ha='center', va='center',
            fontsize=11, fontweight='bold', color='#E2E8F0',
            fontfamily='DejaVu Sans', zorder=8,
            path_effects=[withStroke(linewidth=2, foreground='#0D1B2E')])

    # ── Thin accent line under PMO ────────────────────────────────────────────
    ax.plot([34, 66], [10.5, 10.5], color="#1E88E5", linewidth=1.2,
            solid_capstyle='round', zorder=8)

    # ── Small dot accents ─────────────────────────────────────────────────────
    for dot_x, dot_y in [(85, 83), (82, 78), (88, 78)]:
        ax.add_patch(Circle((dot_x, dot_y), 1.5,
                            facecolor="#00ACC1", edgecolor="none", zorder=8))

def generate_icons():
    os.makedirs("icons", exist_ok=True)
    sizes = [16, 32, 48, 64, 128, 256, 512]
    for sz in sizes:
        fig, ax = plt.subplots(figsize=(sz/72, sz/72), dpi=72)
        fig.patch.set_facecolor("none")
        fig.subplots_adjust(0, 0, 1, 1)
        draw_icon(ax, sz)
        path = f"icons/icon_{sz}x{sz}.png"
        fig.savefig(path, dpi=72, bbox_inches='tight',
                    pad_inches=0, facecolor='none', transparent=False)
        plt.close(fig)
        print(f"  ✅ {path}")

    # Also save a high-res 512px preview
    fig, ax = plt.subplots(figsize=(7.11, 7.11), dpi=72)
    fig.patch.set_facecolor("#0D1B2E")
    fig.subplots_adjust(0, 0, 1, 1)
    draw_icon(ax, 512)
    fig.savefig("icons/icon_preview_512.png", dpi=72,
                bbox_inches='tight', pad_inches=0, facecolor='#0D1B2E')
    plt.close(fig)
    print("  ✅ icons/icon_preview_512.png (preview)")

    # Generate .ico (Windows) using PIL if available
    try:
        from PIL import Image
        imgs = []
        for sz in [16, 32, 48, 256]:
            img = Image.open(f"icons/icon_{sz}x{sz}.png").convert("RGBA")
            img = img.resize((sz, sz), Image.LANCZOS)
            imgs.append(img)
        imgs[0].save("icons/pmo_app.ico", format="ICO",
                     sizes=[(s, s) for s in [16, 32, 48, 256]])
        print("  ✅ icons/pmo_app.ico (Windows icon)")
    except Exception as e:
        print(f"  ℹ  .ico skipped: {e}")

    print("\nAll icons generated in ./icons/")

if __name__ == "__main__":
    generate_icons()
