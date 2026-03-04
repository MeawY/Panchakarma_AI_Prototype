import os
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text


def _ensure_sslmode(url: str) -> str:
    """Ensure sslmode=require for non-local hosts."""
    parsed = urlparse(url)
    if not parsed.hostname:
        return url
    if parsed.hostname in {"localhost", "127.0.0.1"}:
        return url

    query_pairs = dict(parse_qsl(parsed.query, keep_blank_values=True))
    if "sslmode" not in query_pairs:
        query_pairs["sslmode"] = "require"
    new_query = urlencode(query_pairs)
    parsed = parsed._replace(query=new_query)
    return urlunparse(parsed)


def _ensure_psycopg_driver(url: str) -> str:
    """Force SQLAlchemy to use psycopg (v3) driver instead of psycopg2."""
    parsed = urlparse(url)
    if parsed.scheme in {"postgresql+psycopg", "postgres+psycopg"}:
        return url
    if parsed.scheme in {"postgresql", "postgres"}:
        # Rewrite scheme but keep the rest (netloc, path, params, query, fragment)
        return urlunparse(parsed._replace(scheme="postgresql+psycopg"))
    return url


def get_database_url() -> str:
    # Load .env from project root deterministically
    project_root = Path(__file__).resolve().parents[1]
    env_path = project_root / ".env"
    load_dotenv(dotenv_path=env_path)

    url = os.getenv("DATABASE_URL", "").strip()
    if not url:
        raise RuntimeError("DATABASE_URL is not set in .env (expected at: %s)" % env_path)
    url = _ensure_sslmode(url)
    url = _ensure_psycopg_driver(url)
    return url


# Create a global engine for simple scripts/tools
engine = create_engine(get_database_url(), pool_pre_ping=True)


def test_connection() -> bool:
    """Run a simple SELECT 1 to verify connectivity."""
    with engine.connect() as conn:
        value = conn.execute(text("select 1"))
        return value.scalar_one() == 1
