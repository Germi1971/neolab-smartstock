import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()  # reads .env if present

@dataclass
class DBConfig:
    host: str
    port: int
    user: str
    password: str
    database: str

def load_db_config() -> DBConfig:
    return DBConfig(
        host=os.getenv("MYSQL_HOST", "190.228.29.65"),
        port=int(os.getenv("MYSQL_PORT", "3306")),
        user=os.getenv("MYSQL_USER", "neolab"),
        password=os.getenv("MYSQL_PASSWORD", ""),
        database=os.getenv("MYSQL_DB", "neobd"),
    )
