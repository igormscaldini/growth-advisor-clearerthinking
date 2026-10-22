import sys
from pathlib import Path
from PIL import Image, ImageFilter
from playwright.sync_api import sync_playwright

out = Path(sys.argv[1])
html = """<!doctype html><html><head><meta charset="utf-8"><style>
body{margin:0;background:#fff}
.w{width:630px;padding:6px 12px 10px;box-sizing:content-box;font-family:Helvetica;font-size:16px;line-height:1.5;color:#000;font-weight:400}
h4{font:italic 700 16px/1.5 Helvetica;margin:0 0 24px}
p{margin:0}
a{color:#0000FF;text-decoration:none}
</style></head><body><div class="w">
<h4>1. Steelmanning helps you find the truth</h4>
<p>The classic argument for steelmanning comes from the philosopher John Stuart Mill, <a>who argued</a> that if you don’t know the strongest cases in favor of the views you oppose, then you don’t know how well those views can account for the same evidence that you’re relying on to justify <em>your own</em> view. If you only evaluate weakened, straw versions of opposing views, then the evidence will look harder to explain without your view than it really is, and you won’t really know the strength of the evidence for your own position.</p>
</div></body></html>"""
with sync_playwright() as p:
    b = p.chromium.launch(channel="chrome")
    pg = b.new_page(device_scale_factor=2, viewport={"width": 680, "height": 400})
    pg.set_content(html)
    pg.locator(".w").screenshot(path=str(out.with_suffix(".sharp.png")))
    b.close()

img = Image.open(out.with_suffix(".sharp.png")).convert("RGB")
w, h = img.size
start = int(h * 0.36)            # heading + first lines stay sharp
levels = [img.filter(ImageFilter.GaussianBlur(r)) for r in range(0, 13)]
res = img.copy()
for y in range(start, h):
    t = (y - start) / (h - start)            # 0 -> 1 down the image
    r = t ** 1.6 * 11
    lo, hi = int(r), min(int(r) + 1, 12)
    row = Image.blend(levels[lo].crop((0, y, w, y + 1)), levels[hi].crop((0, y, w, y + 1)), r - lo)
    fade = max(0.0, (t - 0.55) / 0.45) ** 1.5 * 0.85   # wash toward white near the bottom
    row = Image.blend(row, Image.new("RGB", (w, 1), "white"), fade)
    res.paste(row, (0, y))
res.save(out, optimize=True)
print(out, res.size)
