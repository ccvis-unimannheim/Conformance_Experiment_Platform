"""Canonicalise a matplotlib SVG so two renders of the same figure compare equal.

Regression-checking a chart means comparing the file, and a naive diff is
useless here: two runs of identical code differ on hundreds of lines. Worse, a
comparison that only looks at text nodes finds nothing at all — matplotlib draws
glyphs as paths, so an SVG holds no readable text to compare.

Matplotlib names each glyph and clip path with a random id, and writes it in both
the definition and every reference, so a byte diff of two identical figures shows
hundreds of changed lines. Renumbering the ids in order of first appearance keeps
the structure and drops the noise; the embedded creation date goes too.
"""
import re, sys

_ID = re.compile(r'\b([a-zA-Z][0-9a-f]{8,})\b')

def normalise(path):
    text = open(path, encoding="utf-8").read()
    text = re.sub(r"<dc:date>.*?</dc:date>", "<dc:date/>", text, flags=re.S)
    mapping, order = {}, []
    def repl(m):
        name = m.group(1)
        if name not in mapping:
            mapping[name] = f"ID{len(order)}"
            order.append(name)
        return mapping[name]
    return _ID.sub(repl, text)

#: Idioms this cannot compare. A heatmap (and task10's calendar) embeds the mesh
#: as a base64 PNG, whose encoding is not byte-stable; parallel_sets emits
#: different ribbon coordinates run to run, so it is not reproducible at all.
UNCOMPARABLE = ("heatmap", "calendar", "parallel_sets")


def comparable(path) -> bool:
    return not any(name in str(path) for name in UNCOMPARABLE)


if __name__ == "__main__":
    a, b = sys.argv[1], sys.argv[2]
    na, nb = normalise(a), normalise(b)
    print("SAME" if na == nb else "DIFF")
