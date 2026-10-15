"""ForgeGuard AI - write docs/SHA256SUMS.txt for every file in the package (run this LAST)."""

from pathlib import Path
import hashlib


ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "docs" / "SHA256SUMS.txt"
FOLDERS = ["config", "data", "docs", "knowledge", "scripts"]
METROPT_LINE = "db30ccb4ea402e3c8bf2c99db06e288d4f2a772f6928f9dbe26a920d69793e24  MetroPT3(AirCompressor).csv"


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main():
    files = sorted(
        p for folder in FOLDERS for p in (ROOT / folder).rglob("*")
        if p.is_file() and p != OUTPUT and "__pycache__" not in p.parts
    )
    lines = [f"{sha256(p)}  {p.relative_to(ROOT).as_posix()}" for p in files]
    lines.append(METROPT_LINE)
    OUTPUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {OUTPUT.relative_to(ROOT).as_posix()} with {len(lines)} lines:")
    for line in lines:
        print(f"  {line[:12]}...  {line[66:]}")


if __name__ == "__main__":
    main()
