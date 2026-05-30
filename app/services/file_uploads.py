from __future__ import annotations

import shutil
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, UploadFile

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
