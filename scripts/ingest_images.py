"""Ingest reviewed image batches: match each uploaded PNG to its batch entry by SHA-256 and write a web-sized JPEG
to docs/images/<path>.jpg (originals stay with the author). Usage: python scripts/ingest_images.py <upload_dir>"""
from __future__ import annotations

import glob
import hashlib
import json
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "images"
STATIC = ROOT / "decision_ladder" / "web" / "static" / "img"
# folder -> width of the copy served by the app (folders not listed are docs-only)
UI_SIZES = {"hero": 1600, "stages": 640, "icons": 160, "modules": 560, "desks": 1200, "states": 360, "samples": 560}


def main(src: str) -> None:
    by_hash = {hashlib.sha256(Path(p).read_bytes()).hexdigest(): p for p in glob.glob(f"{src}/*.png")}
    manifest_p = OUT / "manifest.json"
    manifest = json.loads(manifest_p.read_text()) if manifest_p.exists() else {}
    for b in sorted(glob.glob(f"{src}/*batch-*.json")):
        for e in json.loads(Path(b).read_text())["images"]:
            p = by_hash.get(e["sha256"])
            if not p:
                print("missing image for", e["id"], e["file"])
                continue
            dst = OUT / Path(e["file"]).with_suffix(".jpg")
            dst.parent.mkdir(parents=True, exist_ok=True)
            im = Image.open(p).convert("RGB")
            if im.width > 1600:
                im = im.resize((1600, round(im.height * 1600 / im.width)), Image.LANCZOS)
            im.save(dst, "JPEG", quality=84, optimize=True, progressive=True)
            manifest[e["id"]] = {"file": str(dst.relative_to(ROOT)), "brief_file": e["file"], "sha256_original": e["sha256"],
                                 "generated_with": "ChatGPT image generation (author's prompts)"}
            ui = UI_SIZES.get(Path(e["file"]).parts[0])
            if ui:   # copy used by the app itself, sized for where it is shown
                udst = STATIC / Path(e["file"]).with_suffix(".jpg")
                udst.parent.mkdir(parents=True, exist_ok=True)
                u = Image.open(p).convert("RGB")
                u = u.resize((ui, round(u.height * ui / u.width)), Image.LANCZOS) if u.width > ui else u
                u.save(udst, "JPEG", quality=80, optimize=True, progressive=True)
            print(e["id"], dst.relative_to(ROOT), dst.stat().st_size // 1024, "KB")
    manifest_p.write_text(json.dumps(dict(sorted(manifest.items())), indent=1))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "/mnt/user-data/uploads")
