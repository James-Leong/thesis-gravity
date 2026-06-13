import os
from pathlib import Path

TEST_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "test.db"
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB_PATH}"
