from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

import fitz


@dataclass(frozen=True)
class FigureTableAsset:
    kind: Literal["figure", "table"]
    label: str
    title: str
    pdf_page: int
    caption_bbox: tuple[float, float, float, float]
    content_bbox: tuple[float, float, float, float] | None
    image_path: str | None
    caption_position: Literal["above", "below", "overlap", "unknown"]
    detection_method: str


CaptionKind = Literal["figure", "table"]


@dataclass(frozen=True)
class _CaptionCandidate:
    kind: CaptionKind
    label: str
    title: str
    pdf_page: int
    bbox: fitz.Rect


def extract_figure_table_assets(pdf_path: Path, output_dir: Path) -> list[FigureTableAsset]:
    """Extract figure/table captions, locate nearby content, and save cropped PNG assets."""
    output_dir.mkdir(parents=True, exist_ok=True)
    figures_dir = output_dir / "figures"
    tables_dir = output_dir / "tables"
    figures_dir.mkdir(parents=True, exist_ok=True)
    tables_dir.mkdir(parents=True, exist_ok=True)
    _clear_previous_asset_files(figures_dir, "figure")
    _clear_previous_asset_files(tables_dir, "table")

    assets: list[FigureTableAsset] = []
    doc = fitz.open(str(pdf_path))
    try:
        for page_index in range(len(doc)):
            page = doc.load_page(page_index)
            if _is_likely_directory_page(page):
                continue
            captions = _extract_caption_candidates(page, page_index + 1)
            table_regions = _extract_table_regions(page)
            visual_regions = _extract_visual_regions(page)

            for caption in captions:
                content_bbox, method = _match_content_bbox(caption, page, table_regions, visual_regions)
                image_path = None
                if content_bbox is not None:
                    crop_bbox = _build_crop_bbox(caption.bbox, content_bbox, page.rect)
                    target_dir = figures_dir if caption.kind == "figure" else tables_dir
                    image_path = str(target_dir / _asset_filename(caption))
                    _save_page_crop(page, crop_bbox, Path(image_path))

                assets.append(
                    FigureTableAsset(
                        kind=caption.kind,
                        label=caption.label,
                        title=caption.title,
                        pdf_page=caption.pdf_page,
                        caption_bbox=_rect_tuple(caption.bbox),
                        content_bbox=_rect_tuple(content_bbox) if content_bbox is not None else None,
                        image_path=image_path,
                        caption_position=_caption_position(caption.bbox, content_bbox),
                        detection_method=method,
                    )
                )
    finally:
        doc.close()

    index_path = output_dir / "index.json"
    index_path.write_text(
        json.dumps([asdict(asset) for asset in assets], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return assets


def _extract_caption_candidates(page: fitz.Page, pdf_page: int) -> list[_CaptionCandidate]:
    candidates: list[_CaptionCandidate] = []
    caption_pattern = re.compile(r"^(图|表)\s*([0-9]{1,2})[-.．]([0-9]{1,3})\s*(.*)$")
    text_dict = page.get_text("dict")
    for block in text_dict.get("blocks", []):
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            line_text = "".join(span.get("text", "") for span in line.get("spans", [])).strip()
            if _looks_like_directory_line(line_text):
                continue
            match = caption_pattern.match(line_text)
            if not match:
                continue
            kind_text, chapter, sequence, title = match.groups()
            kind: CaptionKind = "figure" if kind_text == "图" else "table"
            normalized_label = f"{kind_text}{int(chapter)}.{int(sequence)}"
            bbox = fitz.Rect(line.get("bbox"))
            candidates.append(
                _CaptionCandidate(
                    kind=kind,
                    label=normalized_label,
                    title=title.strip(),
                    pdf_page=pdf_page,
                    bbox=bbox,
                )
            )
    return candidates


def _is_likely_directory_page(page: fitz.Page) -> bool:
    text = page.get_text("text")
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return False
    if any(line in {"目录", "图目录", "表目录", "Contents"} for line in lines[:6]):
        return True
    return sum(1 for line in lines if _looks_like_directory_line(line)) >= 3


def _looks_like_directory_line(line: str) -> bool:
    normalized = line.replace("　", " ")
    return bool(re.search(r"[.·]{4,}\s*\d+\s*$", normalized))


def _extract_table_regions(page: fitz.Page) -> list[fitz.Rect]:
    regions: list[fitz.Rect] = []
    try:
        tables = page.find_tables()
    except Exception:
        return regions
    for table in getattr(tables, "tables", []):
        bbox = getattr(table, "bbox", None)
        if bbox:
            regions.append(fitz.Rect(bbox))
    return regions


def _extract_visual_regions(page: fitz.Page) -> list[fitz.Rect]:
    regions: list[fitz.Rect] = []
    for block in page.get_text("dict").get("blocks", []):
        if block.get("type") == 1:
            regions.append(fitz.Rect(block.get("bbox")))

    drawing_rects: list[fitz.Rect] = []
    try:
        drawings = page.get_drawings()
    except Exception:
        drawings = []
    for drawing in drawings:
        rect = drawing.get("rect")
        if rect is None:
            continue
        candidate = fitz.Rect(rect)
        if candidate.width >= 40 and candidate.height >= 20:
            drawing_rects.append(candidate)
    regions.extend(_merge_nearby_rects(drawing_rects))
    return _filter_content_regions(regions, page.rect)


def _match_content_bbox(
    caption: _CaptionCandidate,
    page: fitz.Page,
    table_regions: list[fitz.Rect],
    visual_regions: list[fitz.Rect],
) -> tuple[fitz.Rect | None, str]:
    if caption.kind == "table":
        region = _nearest_region(caption.bbox, table_regions, prefer="below")
        if region is not None:
            return region, "pymupdf_table"
        region = _infer_table_region_from_lines(caption.bbox, page)
        if region is not None:
            return region, "line_based_table"
        return None, "caption_only"

    region = _nearest_region(caption.bbox, visual_regions, prefer="above")
    if region is not None:
        return region, "visual_region"
    region = _infer_figure_region_from_caption(caption.bbox, page)
    if region is not None:
        return region, "caption_gap"
    return None, "caption_only"


def _nearest_region(
    caption_bbox: fitz.Rect, regions: list[fitz.Rect], *, prefer: Literal["above", "below"]
) -> fitz.Rect | None:
    candidates: list[tuple[float, fitz.Rect]] = []
    caption_center_x = (caption_bbox.x0 + caption_bbox.x1) / 2
    for region in regions:
        horizontal_overlap = min(caption_bbox.x1, region.x1) - max(caption_bbox.x0, region.x0)
        center_distance = abs(((region.x0 + region.x1) / 2) - caption_center_x)
        if prefer == "above":
            distance = caption_bbox.y0 - region.y1
        else:
            distance = region.y0 - caption_bbox.y1
        if distance < -8 or distance > 180:
            continue
        if horizontal_overlap < -20 and center_distance > 220:
            continue
        candidates.append((abs(distance) + center_distance * 0.05, region))
    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0])
    return candidates[0][1]


def _infer_table_region_from_lines(caption_bbox: fitz.Rect, page: fitz.Page) -> fitz.Rect | None:
    footer_cutoff = page.rect.y0 + page.rect.height * 0.93
    words = page.get_text("words")
    below_words = [
        fitz.Rect(word[:4])
        for word in words
        if caption_bbox.y1 <= word[1] <= min(footer_cutoff, caption_bbox.y1 + 220)
    ]
    if len(below_words) < 6:
        return None
    return _pad_rect(_union_many(below_words), page.rect, 4)


def _infer_figure_region_from_caption(caption_bbox: fitz.Rect, page: fitz.Page) -> fitz.Rect | None:
    words = page.get_text("words")
    above_words = [
        fitz.Rect(word[:4])
        for word in words
        if max(page.rect.y0, caption_bbox.y0 - 360) <= word[3] <= caption_bbox.y0 - 8
    ]
    if len(above_words) < 3:
        return None
    region = _union_many(above_words)
    if region.height < 40:
        return None
    return _pad_rect(region, page.rect, 8)


def _merge_nearby_rects(rects: list[fitz.Rect]) -> list[fitz.Rect]:
    merged: list[fitz.Rect] = []
    for rect in sorted(rects, key=lambda item: (item.y0, item.x0)):
        matched = False
        for index, existing in enumerate(merged):
            expanded = _pad_rect(existing, fitz.Rect(-10000, -10000, 10000, 10000), 20)
            if expanded.intersects(rect):
                merged[index] = _union_rect(existing, rect)
                matched = True
                break
        if not matched:
            merged.append(rect)
    return merged


def _filter_content_regions(regions: list[fitz.Rect], page_rect: fitz.Rect) -> list[fitz.Rect]:
    filtered: list[fitz.Rect] = []
    for region in regions:
        if region.width < 50 or region.height < 30:
            continue
        if region.width > page_rect.width * 0.98 and region.height < 25:
            continue
        filtered.append(region)
    return filtered


def _caption_position(
    caption_bbox: fitz.Rect, content_bbox: fitz.Rect | None
) -> Literal["above", "below", "overlap", "unknown"]:
    if content_bbox is None:
        return "unknown"
    if caption_bbox.y1 <= content_bbox.y0:
        return "above"
    if caption_bbox.y0 >= content_bbox.y1:
        return "below"
    return "overlap"


def _save_page_crop(page: fitz.Page, bbox: fitz.Rect, image_path: Path) -> None:
    pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), clip=bbox, alpha=False)
    pix.save(image_path)


def _build_crop_bbox(caption_bbox: fitz.Rect, content_bbox: fitz.Rect, page_rect: fitz.Rect) -> fitz.Rect:
    left = min(caption_bbox.x0, content_bbox.x0) - 12
    right = max(caption_bbox.x1, content_bbox.x1) + 12
    if caption_bbox.y1 <= content_bbox.y0:
        top = caption_bbox.y0 - 4
        bottom = content_bbox.y1 + 8
    elif caption_bbox.y0 >= content_bbox.y1:
        top = content_bbox.y0 - 8
        bottom = caption_bbox.y1 + 4
    else:
        top = min(caption_bbox.y0, content_bbox.y0) - 8
        bottom = max(caption_bbox.y1, content_bbox.y1) + 8
    return fitz.Rect(left, top, right, bottom) & page_rect


def _clear_previous_asset_files(directory: Path, prefix: str) -> None:
    for path in directory.glob(f"{prefix}_*_page_*.png"):
        path.unlink()


def _asset_filename(caption: _CaptionCandidate) -> str:
    safe_label = re.sub(r"[^0-9A-Za-z一-鿿._-]+", "_", caption.label)
    return f"{caption.kind}_{safe_label}_page_{caption.pdf_page}.png"


def _rect_tuple(rect: fitz.Rect) -> tuple[float, float, float, float]:
    return (round(rect.x0, 2), round(rect.y0, 2), round(rect.x1, 2), round(rect.y1, 2))


def _union_rect(a: fitz.Rect, b: fitz.Rect) -> fitz.Rect:
    result = fitz.Rect(a)
    result.include_rect(b)
    return result


def _union_many(rects: list[fitz.Rect]) -> fitz.Rect:
    result = fitz.Rect(rects[0])
    for rect in rects[1:]:
        result.include_rect(rect)
    return result


def _pad_rect(rect: fitz.Rect, bounds: fitz.Rect, padding: float) -> fitz.Rect:
    padded = fitz.Rect(rect.x0 - padding, rect.y0 - padding, rect.x1 + padding, rect.y1 + padding)
    return padded & bounds
