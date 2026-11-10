"""Add the telescope name to light frames whose file names don't have one.

Older NINA file names had no scope, e.g.
    2023-11-14_01-57-36__-9.80_300.00s_0017.fits
Current names do:
    2026-11-09_05-28-11_C8HD__LUltimateHaOiii_-9.80_300.00s__HFR6.53_STR7s_0019.fits

For each LIGHT folder with unnamed frames, this reads the TELESCOP header of the first and last frame
(only the first few KB of each file) and inserts that name after the timestamp in every file of that frame
set (images and their .info.txt side files). Older profiles wrote other names in TELESCOP (e.g.
"Williams Optics Z81"), so the header value is mapped to the name current file names use (see SCOPE_NAMES).
Folders whose TELESCOP doesn't map are skipped and reported with the value found.

Dry run by default: it only lists what it would rename. Add --apply to rename.

    python add-scope-to-names.py --root "\\\\nasbox\\homes\\backupAstro\\NINA"
    python add-scope-to-names.py --root "\\\\nasbox\\homes\\backupAstro\\NINA" --apply

After renaming on the NAS, do the same on any local copies, then use Rebuild NAS DB in ap-image-backup,
or the renamed files will look new to it.
"""
import argparse
import logging
import os
import re
from datetime import datetime

IMAGE_EXTENSIONS = (".fits", ".fit", ".xisf")
TIMESTAMP_NO_SCOPE = re.compile(r"^(\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2})__(.+)$")
HAS_SCOPE = re.compile(r"^\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}_[^_]+_")
SKIP_PARTS = ("wbpp", "processing")

logs_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
os.makedirs(logs_dir, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(logs_dir, f"add-scope-to-names.{datetime.now():%Y%m%d}.log"), encoding="utf-8"),
        logging.StreamHandler(),
    ],
)


def telescope(path):
    """TELESCOP from a FITS or XISF header, reading only the header. None if not found or empty."""
    with open(path, "rb") as f:
        if path.lower().endswith(".xisf"):
            head = f.read(256 * 1024).decode("latin-1")
            m = re.search(r'name="TELESCOP"\s+value="\s*\'?([^\'"]*)', head)
            return clean(m.group(1)) if m else None
        for _ in range(100):   # FITS header: 2880-byte blocks of 80-character cards, ends with END
            block = f.read(2880)
            if len(block) < 2880:
                return None
            for i in range(0, 2880, 80):
                card = block[i:i + 80].decode("latin-1")
                if card.startswith("TELESCOP="):
                    m = re.match(r"TELESCOP=\s*'([^']*)'", card)
                    return clean(m.group(1)) if m else None
                if card.startswith("END") and card[3:].strip() == "":
                    return None
    return None


# header TELESCOP (upper-cased, any of these words in it) -> name used in current file names
SCOPE_NAMES = [
    (("Z81",), "WO-Z81-FFR"),
    (("C8HD", "CELESTRON-EDGE-8-HD"), "C8HD"),
]


def file_scope_name(header_value):
    upper = header_value.upper()
    for words, name in SCOPE_NAMES:
        if any(w in upper for w in words):
            return name
    return None


def clean(name):
    """Telescope name as it goes in a file name: no spaces or underscores (underscores separate fields)."""
    name = re.sub(r"[\s_]+", "-", name.strip()).strip("-")
    return name or None


def process(root, apply):
    renamed = skipped = 0
    for folder, dirs, files in os.walk(root):
        rel = os.path.relpath(folder, root)
        top = rel.split(os.sep)[0]
        if top.startswith("_") or any(p in rel.lower() for p in SKIP_PARTS):
            dirs.clear()
            continue
        if os.path.basename(folder) != "LIGHT":
            continue

        frames = sorted(f for f in files if f.lower().endswith(IMAGE_EXTENSIONS) and TIMESTAMP_NO_SCOPE.match(f))
        for f in files:
            if f.lower().endswith(IMAGE_EXTENSIONS) and not TIMESTAMP_NO_SCOPE.match(f) and not HAS_SCOPE.match(f):
                logging.warning(f"Not a frame name I recognize, left alone: {os.path.join(rel, f)}")
        if not frames:
            continue

        headers = {telescope(os.path.join(folder, frames[0])), telescope(os.path.join(folder, frames[-1]))}
        scopes = {file_scope_name(h) if h else None for h in headers}
        if len(scopes) != 1 or None in scopes:
            logging.error(f"Skipped {rel}: TELESCOP {sorted(headers, key=str)} is missing, differs between frames, "
                          "or isn't a known scope")
            skipped += len(frames)
            continue
        scope = scopes.pop()
        logging.info(f"{rel}: {len(frames)} frames, TELESCOP {sorted(headers)[0]} -> {scope}")

        # rename every file of each frame (image and side files share the timestamp prefix)
        stems = {TIMESTAMP_NO_SCOPE.match(f).group(1) for f in frames}
        for f in sorted(files):
            m = TIMESTAMP_NO_SCOPE.match(f)
            if not m or m.group(1) not in stems:
                continue
            new = f"{m.group(1)}_{scope}__{m.group(2)}"
            src, dst = os.path.join(folder, f), os.path.join(folder, new)
            if os.path.exists(dst):
                logging.error(f"Not renamed, target exists: {os.path.join(rel, new)}")
                continue
            if apply:
                os.rename(src, dst)
            logging.info(f"  {'renamed' if apply else 'would rename'}: {f} -> {new}")
            renamed += 1

    logging.info(f"{'Renamed' if apply else 'Would rename'} {renamed} files; {skipped} frames skipped."
                 + ("" if apply else " Dry run only: add --apply to rename."))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", required=True, help="Image root folder (NAS or local), containing the target folders")
    parser.add_argument("--apply", action="store_true", help="Actually rename (default is a dry run)")
    args = parser.parse_args()
    logging.info(f"Starting with root={args.root} apply={args.apply}")
    process(args.root, args.apply)
