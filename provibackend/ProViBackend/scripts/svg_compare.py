"""Canonicalise a matplotlib SVG so two renders of the same figure compare equal.

Regression-checking a chart means comparing the file, and a naive diff is
useless here: two runs of identical code differ on hundreds of lines. Worse, a
comparison that only looks at text nodes finds nothing at all — matplotlib draws
glyphs as paths, so an SVG holds no readable text to compare.

Two kinds of noise have to go:

* **Random ids.** Every glyph, marker and clip path gets a random name, written
  into both its definition and each reference. Renumbering them in order of
  first appearance keeps the structure and drops the churn. The names are not
  always bare hex — a scatter marker is `C0_0_<hex>` — so the pattern matches a
  hex run anywhere, not only at a word boundary.
* **Embedded rasters.** A heatmap, a calendar and some matrices draw their mesh
  with `imshow`, which lands in the file as a base64 PNG. PNG encoding is not
  byte-stable, so the payload differs between runs even when the pixels do not.
  Replacing it with its decoded length keeps a size check without the noise.

What remains — geometry, styles, glyph references, structure — is stable, and is
what a regression would actually change.
"""

import base64
import re
import sys

# A hex run long enough to be a generated name, wherever it appears.
_ID = re.compile(r"[0-9a-f]{8,}")
# The payload of an embedded image, which is base64 and usually very long.
_B64 = re.compile(r'(xlink:href="data:image/png;base64,)([A-Za-z0-9+/=\s]+)(")')


def normalise(path) -> str:
    """The SVG at *path* with its run-to-run noise removed."""
    text = open(path, encoding="utf-8").read()
    text = re.sub(r"<dc:date>.*?</dc:date>", "<dc:date/>", text, flags=re.S)

    def raster(m):
        payload = re.sub(r"\s+", "", m.group(2))
        try:
            size = len(base64.b64decode(payload))
        except Exception:
            size = len(payload)
        return f"{m.group(1)}[{size} bytes]{m.group(3)}"

    text = _B64.sub(raster, text)

    mapping: dict = {}

    def rename(m):
        name = m.group(0)
        if name not in mapping:
            mapping[name] = f"ID{len(mapping)}"
        return mapping[name]

    return _ID.sub(rename, text)


#: Idioms this cannot compare at all. parallel_sets emits different ribbon
#: coordinates on every run — it is not reproducible, which is worth knowing
#: independently of any refactor.
UNCOMPARABLE = ("parallel_sets",)


def comparable(path) -> bool:
    return not any(name in str(path) for name in UNCOMPARABLE)


if __name__ == "__main__":
    a, b = sys.argv[1], sys.argv[2]
    print("SAME" if normalise(a) == normalise(b) else "DIFF")
