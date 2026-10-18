"""Assemble the four chart tiles captured by capture_screenshots.py into the
single 2x2 grid used on the Explorer feature page.

    python compose_chart_grid.py <shots_dir> <out.png>
"""
import sys
from PIL import Image

SRC, OUT = sys.argv[1].rstrip("/"), sys.argv[2]
TILES = ["chart-lines", "chart-columns", "chart-radar", "chart-scatter"]

BG = (248, 250, 252)
GAP = 32          # between tiles
PAD = 32          # around the grid
TILE_W = 1200     # each tile is resized to this width

images = []
for name in TILES:
    im = Image.open(f"{SRC}/{name}.png").convert("RGB")
    im = im.resize((TILE_W, round(im.height * TILE_W / im.width)), Image.LANCZOS)
    images.append(im)

# All four tiles share a row/column geometry, so the cell is the largest of them.
cell_h = max(im.height for im in images)
grid = Image.new("RGB", (PAD * 2 + TILE_W * 2 + GAP, PAD * 2 + cell_h * 2 + GAP), BG)

for index, im in enumerate(images):
    x = PAD + (index % 2) * (TILE_W + GAP)
    y = PAD + (index // 2) * (cell_h + GAP)
    grid.paste(im, (x, y + (cell_h - im.height) // 2))

grid.save(OUT, optimize=True)
print("wrote", OUT, grid.size)
