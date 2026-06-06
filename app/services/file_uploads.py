from __future__ import annotations

import shutil
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, UploadFile

import fitz

from app.core.config import settings
from app.core.constants import ALLOWED_UPLOAD_EXTENSIONS


def save_pdf(upload_file: UploadFile, student_id: int) -> str:
    if not upload_file.filename:
        raise HTTPException(status_code=400, detail="Missing filename.")

    ext = Path(upload_file.filename).suffix.lower()
    if ext not in ALLOWED_UPLOAD_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    dest_dir = settings.data_dir / "theses" / str(student_id)
    dest_dir.mkdir(parents=True, exist_ok=True)

    file_name = f"{uuid4().hex}{ext}"
    dest_path = dest_dir / file_name

    with dest_path.open("wb") as target:
        shutil.copyfileobj(upload_file.file, target)

    return str(dest_path.relative_to(settings.base_dir))


def validate_pdf_content(pdf_path: Path) -> None:
    try:
        doc = fitz.open(str(pdf_path))
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail="PDF 文件无法正常解析，请确认上传的是可读取的 PDF。",
        ) from exc

    if len(doc) == 0:
        doc.close()
        raise HTTPException(
            status_code=400,
            detail="PDF 文件为空，请检查文件内容。",
        )

    has_meaningful_text = False
    for page in doc:
        text = page.get_text().strip()
        if text:
            has_meaningful_text = True
            break

    doc.close()

    if not has_meaningful_text:
        raise HTTPException(
            status_code=400,
            detail="PDF 文件中未能提取到有效文本，请确认文件为可读的 PDF 格式（非扫描件或纯图片）。",
        )


def remove_uploaded_file(file_path: Path) -> None:
    try:
        file_path.unlink(missing_ok=True)
    except OSError:
        return
