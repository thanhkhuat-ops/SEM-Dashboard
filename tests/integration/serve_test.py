"""Chạy web app trên MySQL thử nghiệm (đọc tests/integration/test.env thay cho .env)."""
import os
from pathlib import Path

for line in (Path(__file__).resolve().parent / "test.env").read_text(encoding="utf-8").splitlines():
    if line.strip() and not line.startswith("#") and "=" in line:
        k, v = line.split("=", 1)
        os.environ[k.strip()] = v.strip()

import uvicorn  # noqa: E402

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="127.0.0.1", port=int(os.getenv("PORT", "8010")))
