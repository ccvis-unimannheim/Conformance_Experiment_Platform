#!/usr/bin/env python3
"""Compare two pipeline output trees, ignoring matplotlib's rendering noise.

Two renderings of the same figure never match byte-for-byte even when nothing
changed: matplotlib stamps a <dc:date> and mints a fresh random id per process
for every clip path, marker definition and rasterised image ("pb7467015c3",
"image8bd634ecf3", "C0_0_a2a0687d4c"). Both are normalised away here, and a
base64-embedded SVG (task09/task35 compose one) is decoded and normalised in
turn, so a reported difference is a real difference in the drawing.

usage: svg_diff.py <dir_a> <dir_b> [path-substring-filter ...]
"""
import base64
import re
import sys
from pathlib import Path

_DATE = re.compile(r"<dc:date>.*?</dc:date>", re.S)
_ID = re.compile(r'(?:id="|url\(#|xlink:href="#|href="#)([A-Za-z][A-Za-z0-9_]*?[0-9a-f]{8,})(?=["\)])')
_B64 = re.compile(r'base64,\s*([A-Za-z0-9+/=\s]+?)(?=["\'])')


def _canonical_ids(text: str) -> str:
    mapping: dict[str, str] = {}
    for token in _ID.findall(text):
        mapping.setdefault(token, f"ID{len(mapping):04d}")
    for token, canon in mapping.items():
        text = re.sub(rf"(?<![A-Za-z0-9_]){re.escape(token)}(?![A-Za-z0-9_])", canon, text)
    return text


def _expand_nested(text: str) -> str:
    """Replace a base64-embedded SVG with its normalised source.

    Left as-is when the payload is not XML (a rasterised PNG), which compares
    byte-stable on its own.
    """
    def repl(match: re.Match) -> str:
        try:
            raw = base64.b64decode(re.sub(r"\s", "", match.group(1)))
        except Exception:
            return match.group(0)
        if not raw.lstrip().startswith(b"<"):
            return match.group(0)
        inner = raw.decode("utf-8", errors="replace")
        return "base64,NESTED[" + _canonical_ids(_DATE.sub("", inner)) + "]"

    return _B64.sub(repl, text)


def normalise(path: Path) -> str:
    text = path.read_text(encoding="utf-8", errors="replace")
    text = _DATE.sub("<dc:date>NORMALISED</dc:date>", text)
    return _canonical_ids(_expand_nested(text))


def main() -> int:
    a, b = Path(sys.argv[1]), Path(sys.argv[2])
    filters = sys.argv[3:]
    files = sorted(p.relative_to(a) for p in a.rglob("*.svg"))
    if filters:
        files = [f for f in files if any(s in str(f) for s in filters)]
    same = differ = missing = 0
    for rel in files:
        other = b / rel
        if not other.exists():
            print(f"MISSING  {rel}")
            missing += 1
        elif normalise(a / rel) == normalise(other):
            same += 1
        else:
            print(f"DIFFER   {rel}")
            differ += 1
    print(f"\n{same} identical · {differ} differ · {missing} missing ({len(files)} compared)")
    return 1 if (differ or missing) else 0


if __name__ == "__main__":
    sys.exit(main())
