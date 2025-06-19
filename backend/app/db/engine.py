from sqlmodel import create_engine
import os

# 支援 Docker 環境的資料庫路徑
if os.getenv("DOCKER_ENV"):
    # Docker 環境，使用 volume 路徑
    DB_PATH = "/app/db/db.sqlite3"
else:
    # 本地開發環境
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    DB_PATH = os.path.join(BASE_DIR, "db.sqlite3")

DATABASE_URL = f"sqlite:///{DB_PATH}"
engine = create_engine(DATABASE_URL, echo=True)
