from pathlib import Path

import fitz

from app.services.figure_table_assets import extract_figure_table_assets


def test_extract_figure_table_assets_skips_directory_pages(tmp_path: Path) -> None:
    pdf_path = tmp_path / "sample.pdf"
    doc = fitz.open()
    directory_page = doc.new_page()
    directory_page.insert_text((72, 72), "图目录", fontname="china-s")
    directory_page.insert_text((72, 100), "图4.1 示例框架图·························· 21", fontname="china-s")
    directory_page.insert_text((72, 120), "图4.2 示例折线图·························· 22", fontname="china-s")
    directory_page.insert_text((72, 140), "表4.1 示例数据表·························· 21", fontname="china-s")

    content_page = doc.new_page()
    content_page.draw_rect(fitz.Rect(120, 120, 360, 220))
    content_page.insert_text((200, 245), "图4.1 示例框架图", fontname="china-s")
    content_page.insert_text((185, 300), "表4.1 示例数据表", fontname="china-s")
    content_page.draw_line((120, 325), (430, 325), width=1.2)
    content_page.insert_text((140, 350), "2019 年        2020 年        2021 年", fontname="china-s")
    content_page.insert_text((140, 375), "10             20             30", fontname="china-s")
    content_page.draw_line((120, 395), (430, 395), width=1.2)

    doc.save(pdf_path)
    doc.close()

    assets = extract_figure_table_assets(pdf_path, tmp_path / "assets")

    assert [(asset.label, asset.pdf_page) for asset in assets] == [("图4.1", 2), ("表4.1", 2)]
    assert all(asset.image_path and Path(asset.image_path).exists() for asset in assets)
    assert not list((tmp_path / "assets" / "figures").glob("*page_1.png"))
