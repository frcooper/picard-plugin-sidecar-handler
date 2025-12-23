from __future__ import annotations

import hashlib
import sys
import zipfile
from pathlib import Path


def _read_manifest_version(manifest_path: Path) -> str:
    if sys.version_info >= (3, 11):
        import tomllib  # type: ignore

        data = tomllib.loads(manifest_path.read_text(encoding="utf-8"))
    else:
        raise RuntimeError("Python 3.11+ required to build deterministically")

    version = data.get("version")
    if not isinstance(version, str) or not version:
        raise RuntimeError("MANIFEST.toml missing version")
    return version


def _iter_plugin_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for rel in ("MANIFEST.toml", "__init__.py"):
        p = root / rel
        if p.is_file():
            files.append(p)

    pkg = root / "sidecar_handler"
    if pkg.is_dir():
        for file_path in sorted(pkg.rglob("*.py")):
            if file_path.is_file():
                files.append(file_path)

    return files


def build() -> Path:
    repo_root = Path(__file__).resolve().parents[1]
    manifest = repo_root / "MANIFEST.toml"
    version = _read_manifest_version(manifest)

    dist = repo_root / "dist"
    dist.mkdir(exist_ok=True)

    out_zip = dist / f"sidecar-handler_{version}.zip"

    fixed_time = (1980, 1, 1, 0, 0, 0)

    with zipfile.ZipFile(out_zip, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for file_path in _iter_plugin_files(repo_root):
            arcname = file_path.relative_to(repo_root).as_posix()
            info = zipfile.ZipInfo(arcname)
            info.date_time = fixed_time
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            zf.writestr(info, file_path.read_bytes())

    sha256 = hashlib.sha256(out_zip.read_bytes()).hexdigest()
    (dist / "SHA256SUMS").write_text(f"{sha256}  {out_zip.name}\n", encoding="utf-8")

    return out_zip


if __name__ == "__main__":
    path = build()
    print(path)
