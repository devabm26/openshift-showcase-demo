"""
Database connection layer for the thoughts dashboard.

Implements:
  - Connection pooling (psycopg2.pool.SimpleConnectionPool)
  - Context managers for connection lifecycle
  - 100% parameterized queries — NO string formatting in SQL
  - Centralised error handling and logging

Spec: specs/architecture/database_layer.spec
Spec: specs/security/sql_injection_prevention.spec
Spec: specs/security/secrets_management.spec
"""
import logging
from contextlib import contextmanager
from typing import Any, Dict, Generator, List, Optional

import psycopg2
import psycopg2.extras
import psycopg2.pool

from src.config import Config

logger = logging.getLogger(__name__)


class DatabaseConnection:
    """
    Manages the PostgreSQL connection pool and provides query execution helpers.

    Layer 1 of the database architecture (database_layer.spec REQ-3).
    All credentials are read from Config — never hardcoded.
    """

    def __init__(self, config: type = Config) -> None:
        """
        Initialise the connection pool from environment-based configuration.

        Raises:
            ValueError: If required configuration is missing.
            psycopg2.OperationalError: If the database cannot be reached.
        """
        self._pool: Optional[psycopg2.pool.SimpleConnectionPool] = None
        self._config = config
        self._init_pool()

    def _init_pool(self) -> None:
        """Create the connection pool. Called once at startup."""
        try:
            self._pool = psycopg2.pool.SimpleConnectionPool(
                minconn=self._config.DB_POOL_MIN,
                maxconn=self._config.DB_POOL_MAX,
                host=self._config.DB_HOST,
                port=self._config.DB_PORT,
                dbname=self._config.DB_NAME,
                user=self._config.DB_USER,
                password=self._config.DB_PASSWORD,
                connect_timeout=self._config.DB_TIMEOUT,
            )
            logger.info(
                "Database connection pool initialised (min=%d, max=%d, host=%s)",
                self._config.DB_POOL_MIN,
                self._config.DB_POOL_MAX,
                self._config.DB_HOST,
            )
        except psycopg2.OperationalError as exc:
            logger.error("Failed to initialise database connection pool: %s", exc)
            raise

    @contextmanager
    def get_connection(self) -> Generator[psycopg2.extensions.connection, None, None]:
        """
        Context manager that acquires a connection from the pool and returns
        it automatically after use, even if an exception is raised.

        Spec: specs/architecture/database_layer.spec (REQ-2)
        """
        assert self._pool is not None, "Pool has not been initialised"
        conn = self._pool.getconn()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            self._pool.putconn(conn)

    def execute_query(
        self,
        query: str,
        params: Optional[tuple] = None,
    ) -> List[Dict[str, Any]]:
        """
        Execute a SELECT query and return results as a list of dicts.

        IMPORTANT: The `query` string MUST use %s placeholders.
                   User-controlled values MUST be passed via `params`.
                   NEVER format values directly into the query string.

        Spec: specs/security/sql_injection_prevention.spec
        Spec: specs/architecture/database_layer.spec (PATTERN 1)

        Args:
            query:  SQL string with %s placeholders (never f-strings or %).
            params: Tuple of parameter values to bind safely.

        Returns:
            List of row dicts (column name → value).
        """
        logger.debug("Executing query (params redacted for security)")
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(query, params)
                rows = cur.fetchall()
                return [dict(row) for row in rows]

    def execute_update(
        self,
        query: str,
        params: Optional[tuple] = None,
    ) -> int:
        """
        Execute an INSERT/UPDATE/DELETE query and return the row count.

        Spec: specs/architecture/database_layer.spec (PATTERN 2)
        """
        logger.debug("Executing update (params redacted for security)")
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                return cur.rowcount

    def close(self) -> None:
        """Close all connections in the pool. Call during application shutdown."""
        if self._pool:
            self._pool.closeall()
            logger.info("Database connection pool closed")

    def health_check(self) -> bool:
        """
        Perform a lightweight connectivity check for the /health endpoint.

        Returns:
            True if the database responds; False otherwise.
        """
        try:
            self.execute_query("SELECT 1")
            return True
        except Exception as exc:
            logger.error("Database health check failed: %s", exc)
            return False


# ---------------------------------------------------------------------------
# Domain query functions — Layer 2 (database_layer.spec REQ-4)
# ---------------------------------------------------------------------------

def get_all_thoughts(db: DatabaseConnection) -> List[Dict[str, Any]]:
    """
    Retrieve all thoughts with computed net_rating column.

    All columns are fetched from the database; no user input is interpolated.
    Spec: specs/security/sql_injection_prevention.spec

    Args:
        db: Initialised DatabaseConnection instance.

    Returns:
        List of thought dicts including net_rating (thumbs_up - thumbs_down).
    """
    query = """
        SELECT
            id,
            content,
            author,
            status,
            thumbs_up,
            thumbs_down,
            (thumbs_up - thumbs_down) AS net_rating
        FROM thoughts
        ORDER BY id DESC
    """
    # No user input → no params needed; still uses parameterized execute path
    return db.execute_query(query)
