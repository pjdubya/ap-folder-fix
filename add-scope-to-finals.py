"""Add the scope to finished-image file names in each target's Processing folder.

Finals used to be named without the scope:
    Crab Nebula/Processing/CrabNebula_HOO.png
Now the scope sits between the object name and the palette, using the same names the light frames use:
    Crab Nebula/Processing/CrabNebula_C8HD_HOO.png

For each target, the scope comes from its light frame names (e.g. 2026-11-09_05-28-11_C8HD__...). A target
whose lights show more than one scope, or any frames without a scope, or no lights at all, is skipped and
listed, since its finals could have come from either. The object name is whatever already comes before the
palette in the existing files; it's kept as is. A target whose finals use more than one object name is
skipped and listed.

Renamed, directly in Processing/ (.png and .xisf):
    <Object>_<Palette>  for HOO, Foraxx-cool, Foraxx-warm, SHO-synthetic, Foraxx, palettes
    <Object>_processing-log.md
and in Processing/checkpoints/:
    <Object>_starless.xisf, <Object>_stars.xisf
Anything else (your own files, names already carrying a scope) is left alone. Nothing is deleted, and a
rename whose new name already exists is skipped.

Dry run by default: it only lists what it would rename. Add --apply to rename.

    python add-scope-to-finals.py --root "\\\\nasbox\\homes\\backupAstro\\NINA"
    python add-scope-to-finals.py --root "\\\\nasbox\\homes\\backupAstro\\NINA" --apply

After renaming on the NAS, use Rebuild NAS DB in ap-image-backup so ap-hub sees the new names.
"""
import argparse
import logging
import os
import re
from datetime import datetime

IMAGE_EXTENSIONS = (".fits", ".fit", ".xisf")
FRAME_SCOPE = re.compile(r"^\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}_([^_]+)_")
FRAME_NO_SCOPE = re.compile(r"^\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}__")
SKIP_PARTS = ("wbpp", "processing")
SCOPES = ("C8HD", "WO-Z81-FFR")   # scope names as they appear in light frame names

PALETTES = ("HOO", "Foraxx-cool", "Foraxx-warm", "SHO-synthetic", "Foraxx", "palettes")
FINAL = re.compile(r"^(.+)_(" + "|".join(re.escape(p) for p in PALETTES) + r")\.(png|xisf)$")
LOG = re.compile(r"^(.+)_(processing-log)\.(md)$")
CHECKPOINT = re.compile(r"^(.+)_(starless|stars)\.(xisf)$")

logs_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
os.makedirs(logs_dir, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(logs_dir, f"add-scope-to-finals.{datetime.now():%Y%m%d}.log"), encoding="utf-8"),
        logging.StreamHandler(),
    ],
)


def light_scopes(target_dir):
    """Scopes named in the target's light frames, and how many frames have no scope in the name."""
    scopes, unscoped = set(), 0
    for folder, dirs, files in os.walk(target_dir):
        rel = os.path.relpath(folder, target_dir).lower()
        if any(p in rel for p in SKIP_PARTS):
            dirs.clear()
            continue
        if os.path.basename(folder) != "LIGHT":
            continue
        for f in files:
            if not f.lower().endswith(IMAGE_EXTENSIONS):
                continue
            m = FRAME_SCOPE.match(f)
            if m:
                scopes.add(m.group(1))
            elif FRAME_NO_SCOPE.match(f):
                unscoped += 1
    return scopes, unscoped


def find_dir(parent, name):
    """Child folder of parent with this name, any letter case. None if there isn't one."""
    try:
        for entry in os.scandir(parent):
            if entry.is_dir() and entry.name.lower() == name.lower():
                return entry.path
    except FileNotFoundError:
        pass
    return None


def candidates(processing_dir):
    """(folder, file name, object, rest) for every file this script would rename."""
    found = []
    checkpoints_dir = find_dir(processing_dir, "checkpoints")
    for folder, patterns in ((processing_dir, (FINAL, LOG)), (checkpoints_dir, (CHECKPOINT,))):
        if not folder:
            continue
        for entry in os.scandir(folder):
            if not entry.is_file():
                continue
            for pattern in patterns:
                m = pattern.match(entry.name)
                if not m:
                    continue
                obj = m.group(1)
                if obj.rsplit("_", 1)[-1] in SCOPES:   # already has a scope
                    break
                found.append((folder, entry.name, obj, f"{m.group(2)}.{m.group(3)}"))
                break
    return found


def process(root, apply):
    renamed = 0
    skipped_targets = []
    for entry in sorted(os.scandir(root), key=lambda e: e.name.lower()):
        if not entry.is_dir() or entry.name[0] in "_@#.":
            continue
        processing_dir = find_dir(entry.path, "processing")
        if not processing_dir:
            continue
        files = candidates(processing_dir)
        if not files:
            continue

        scopes, unscoped = light_scopes(entry.path)
        objects = sorted({obj for _, _, obj, _ in files})
        if len(scopes) != 1 or unscoped:
            reason = (f"lights show scopes {sorted(scopes)}" if scopes else "no lights with a scope in the name")
            if unscoped:
                reason += f", plus {unscoped} frames without a scope"
            logging.warning(f"Skipped {entry.name}: {reason}")
            skipped_targets.append(entry.name)
            continue
        if len(objects) != 1:
            logging.warning(f"Skipped {entry.name}: finals use more than one object name {objects}")
            skipped_targets.append(entry.name)
            continue

        scope = scopes.pop()
        logging.info(f"{entry.name}: scope {scope}, object name {objects[0]}")
        for folder, name, obj, rest in files:
            new = f"{obj}_{scope}_{rest}"
            src, dst = os.path.join(folder, name), os.path.join(folder, new)
            rel = os.path.relpath(src, root)
            if os.path.exists(dst):
                logging.error(f"  Not renamed, new name already exists: {os.path.relpath(dst, root)}")
                continue
            if apply:
                os.rename(src, dst)
            logging.info(f"  {'renamed' if apply else 'would rename'}: {rel} -> {new}")
            renamed += 1

    logging.info(f"{'Renamed' if apply else 'Would rename'} {renamed} files."
                 + (f" Skipped targets (decide these yourself): {', '.join(skipped_targets)}." if skipped_targets else "")
                 + ("" if apply else " Dry run only: add --apply to rename."))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", required=True, help="Image root folder (NAS or local), containing the target folders")
    parser.add_argument("--apply", action="store_true", help="Actually rename (default is a dry run)")
    args = parser.parse_args()
    logging.info(f"Starting with root={args.root} apply={args.apply}")
    process(args.root, args.apply)
