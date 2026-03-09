from __future__ import annotations

from pathlib import Path

from docx import Document

from .models import Account


def read_accounts_from_docx(path: str | Path) -> list[Account]:
    file_path = Path(path)
    if not file_path.exists():
        return []

    accounts: list[Account] = []
    try:
        doc = Document(str(file_path))
    except Exception:
        return []

    for table in doc.tables:
        for row in table.rows:
            if len(row.cells) < 2:
                continue
            username = (row.cells[0].text or "").strip()
            password = (row.cells[1].text or "").strip()
            if username and password:
                accounts.append(Account(username=username, password=password))
    return accounts
