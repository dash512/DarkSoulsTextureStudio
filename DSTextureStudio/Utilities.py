import json
import sys
from pathlib import Path
from PIL import Image

def replaceTerms(text, terms: dict) -> str:
    """Replaces all instances of substrings in a string.
    eg. replaceTerms("file.tpf", {'.tpf': '.dcx'}) will replace any tpf file's extension to dcx"""
    if text:
        for term, replacement in terms.items():
            text = text.replace(term, replacement)
    return text
    

def path_has_sequence(parts, sequence) -> bool:
    """Checks if any given path contains a sequence of elements.
    eg. [\"steamapps\", \"common\", \"Sekiro\"] in potential game path."""
    for i in range(len(parts) - len(sequence) + 1):
        if parts[i:i+len(sequence)] == tuple(sequence):
            return True
    return False

def morton8(i) -> tuple[int, int]:
    """Convert a Morton (Z-order) index in an 8x8 tile to (x, y) block coordinates.

    Decodes a linear Morton index (0-63) into its corresponding block coordinates inside the tile.

    For example:
        0 -> (0, 0)
        1 -> (1, 0)
        2 -> (0, 1)
        3 -> (1, 1)
        4 -> (2, 0)
        ...
    """
    def compact1by1(n):
        n &= 0x5555
        n = (n ^ (n >> 1)) & 0x3333
        n = (n ^ (n >> 2)) & 0x0F0F
        n = (n ^ (n >> 4)) & 0x00FF
        return n

    return compact1by1(i), compact1by1(i >> 1)

def getDSTSdir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    else:
        return Path(__file__).resolve().parents[1] # extra step up due to Utils being in a subdir

def loadJson(name: str, dir: str = "defs"):
    with open(getDSTSdir() / dir / f"{name}.json", 'r') as file:
        return json.load(file)

def align_up(value: int, align: int = 8) -> int:
    return (value + align - 1) & ~(align - 1)

def checkBlockSize(img: Image.Image|tuple, align=8) -> bool:
    """Return True if image dimensions are divisible by alignment, else False"""
    w,h = img if isinstance(img, tuple) else img.size
    return not (w % align or h % align)

def tupleAdd(tuples: list[tuple]) -> tuple:
    return tuple(map(sum, zip(*tuples)))

def findLast(lst: list, _type: type):
    """Find last instance of a type in a list, return None if not found"""
    for r_idx, element in enumerate(reversed(lst)):
        if isinstance(element, _type):
            return len(lst) - 1 - r_idx
    return None

if __name__ == "__main__":
    pass

