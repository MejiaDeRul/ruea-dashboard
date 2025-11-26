import duckdb
from . import paths
from ..core.config import settings

class Duck:
    _rw = None
    _ro = None

    @classmethod
    def ro(cls):
        if cls._ro is None:
            cls._ro = duckdb.connect(settings.DB_PATH, read_only=True)
        return cls._ro

    @classmethod
    def rw(cls, db_path: str | None = None):
        if cls._rw is None:
            cls._rw = duckdb.connect(db_path or settings.DB_PATH, read_only=False)
        return cls._rw
