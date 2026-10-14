from contextlib import contextmanager
import os
from typing import Any, Iterator
import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor


class DatabasePool:
    _instance: "DatabasePool | None" = None

    def __init__(
        self,
        db_url: str | None = None,
        minconn: int = 1,
        maxconn: int = 20,
    ) -> None:
        self.db_url = db_url or os.getenv("DATABASE_URL")
        if not self.db_url:
            raise RuntimeError("DATABASE_URL is not configured")
        self.pool = pool.ThreadedConnectionPool(
            minconn=minconn,
            maxconn=maxconn,
            dsn=self.db_url,
            cursor_factory=RealDictCursor,
        )

    @classmethod
    def get_instance(cls, db_url: str | None = None) -> "DatabasePool":
        if cls._instance is None:
            cls._instance = cls(db_url=db_url)
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        if cls._instance is not None:
            cls._instance.close()
            cls._instance = None

    @contextmanager
    def get_connection(self) -> Iterator[Any]:
        conn = self.pool.getconn()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            self.pool.putconn(conn)

    @contextmanager
    def get_cursor(self) -> Iterator[Any]:
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                yield cur

    def close(self) -> None:
        if self.pool and not self.pool.closed:
            self.pool.closeall()


def get_db_pool(db_url: str | None = None) -> DatabasePool:
    return DatabasePool.get_instance(db_url)


def get_raw_connection(db_url: str | None = None) -> Any:
    url = db_url or os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is not configured")
    return psycopg2.connect(url, cursor_factory=RealDictCursor)
