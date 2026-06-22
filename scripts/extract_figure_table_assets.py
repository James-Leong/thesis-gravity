from __future__ import annotations

import argparse
from pathlib import Path

from app.services.figure_table_assets import extract_figure_table_assets


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract figure/table screenshots and index from a thesis PDF.")
    parser.add_argument("pdf", type=Path, help="PDF file path")
    parser.add_argument("output_dir", type=Path, help="Directory for screenshots and index.json")
    args = parser.parse_args()

    assets = extract_figure_table_assets(args.pdf, args.output_dir)
    print(f"extracted {len(assets)} figure/table assets")
    print(f"index: {args.output_dir / 'index.json'}")


if __name__ == "__main__":
    main()
