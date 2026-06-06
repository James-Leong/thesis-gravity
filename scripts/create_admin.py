#!/usr/bin/env python3
"""Create an admin user directly in the database.

Usage:
    uv run scripts/create_admin.py admin@example.com password123
    .venv/bin/python scripts/create_admin.py admin@example.com password123
"""

import argparse
import sys
from pathlib import Path

# Allow running from repo root without package installation
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.security import hash_password
from app.db import SessionLocal, init_db
from app.models import User


def create_admin(email: str, password: str) -> None:
    init_db()
    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.email == email).first()
        if existing:
            if existing.role == "admin":
                existing.password_hash = hash_password(password)
                db.commit()
                print(f"Admin password updated: {email} (id={existing.id})")
                return
            # Promote existing user to admin
            existing.role = "admin"
            existing.password_hash = hash_password(password)
            db.commit()
            print(f"Promoted existing user to admin: {email} (id={existing.id})")
            return

        user = User(
            email=email,
            password_hash=hash_password(password),
            role="admin",
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        print(f"Admin user created: {email} (id={user.id})")
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Create an admin user in the database.")
    parser.add_argument("email", help="Admin email address")
    parser.add_argument("password", help="Admin password")
    args = parser.parse_args()

    create_admin(args.email, args.password)


if __name__ == "__main__":
    main()
