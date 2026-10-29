"""Rebuild site/ and export a clean copy to Downloads: folder + zip, preview-only/tool metadata removed, neutral file dates.

  python pipeline/export_site.py
"""
import os, pathlib, shutil, subprocess, sys, time, zipfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
subprocess.run([sys.executable, str(ROOT / "pipeline" / "build_site.py")], check=True)
src = ROOT / "site"
dst = pathlib.Path.home() / "Downloads" / "canada-home-value-site"
zp = pathlib.Path.home() / "Downloads" / "canada-home-value-site.zip"
if dst.exists():
    shutil.rmtree(dst)
shutil.copytree(src, dst)
T = time.mktime((2026, 1, 1, 0, 0, 0, 0, 0, -1))
files = sorted(p for p in dst.rglob("*") if p.is_file())
for p in files + [dst] + [d for d in dst.rglob("*") if d.is_dir()]:
    os.utime(p, (T, T))
if zp.exists():
    zp.unlink()
with zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
    for p in files:
        zi = zipfile.ZipInfo(str(p.relative_to(dst.parent)).replace("\\", "/"), date_time=(2026, 1, 1, 0, 0, 0))
        zi.external_attr = 0o644 << 16; zi.compress_type = zipfile.ZIP_DEFLATED; zi.create_system = 3
        z.writestr(zi, p.read_bytes())
os.utime(zp, (T, T))
print("exported", len(files), "files to", dst, "and", zp, round(zp.stat().st_size / 1e6, 1), "MB")
