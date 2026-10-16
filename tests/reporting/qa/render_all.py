"""Offline visual QA only. Uses canonical skill DOCX renderer and Poppler."""

import subprocess
import sys
from pathlib import Path


def main():
    inputs, outputs, tool = (Path(value) for value in sys.argv[1:4])
    names = sorted(source.name.removesuffix(".view.json") for source in inputs.glob("*.view.json"))
    if len(sys.argv) > 4:
        names = [name for name in names if name in sys.argv[4].split(",")]
    for name in names:
        source = inputs / f"{name}.docx"
        target = outputs / f"docx-{source.stem}"
        subprocess.run([sys.executable, str(tool), str(source), "--output_dir", str(target),
                        "--dpi", "120", "--emit_pdf"], check=True, timeout=120)
        print("DOCX", source.stem, len(tuple(target.glob("page-*.png"))), flush=True)
    for name in names:
        source = inputs / f"{name}.pdf"
        target = outputs / f"pdf-{source.stem}"
        target.mkdir(parents=True, exist_ok=True)
        subprocess.run(["pdftoppm", "-r", "120", "-png", str(source), str(target / "page")],
                       check=True, timeout=120)
        print("PDF", source.stem, len(tuple(target.glob("page-*.png"))), flush=True)


if __name__ == "__main__":
    main()
