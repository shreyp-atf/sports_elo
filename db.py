"""Database connection management and schema initialisation for PostgreSQL."""

import re
from contextlib import contextmanager
from urllib.parse import quote

import streamlit as st
from psycopg2 import pool
from psycopg2.extras import RealDictCursor


def _encode_dsn(dsn):
    """URL-encode the password in a postgresql:// DSN.

    Passwords containing special characters (like ``/``) break URI parsing
    unless they are percent-encoded.
    """
    m = re.match(r"^(postgresql://[^:]+:)(.+)(@.+)$", dsn)
    if m:
        prefix, password, suffix = m.groups()
        return prefix + quote(password, safe="") + suffix
    return dsn


@st.cache_resource
def get_connection_pool():
    """Create and cache a PostgreSQL connection pool (one per app lifetime)."""
    dsn = _encode_dsn(st.secrets["connection_string"])
    return pool.SimpleConnectionPool(
        minconn=1,
        maxconn=5,
        dsn=dsn,
    )


@contextmanager
def get_conn():
    """Yield a connection from the pool as a context manager.

    Commits on success, rolls back on exception, and always returns the
    connection to the pool.
    """
    p = get_connection_pool()
    conn = p.getconn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        p.putconn(conn)


def _run_ddl(conn, statements):
    """Execute a list of DDL statements inside the given connection."""
    with conn.cursor() as cur:
        for stmt in statements:
            cur.execute(stmt)


_TABLE_STATEMENTS = [
    # Players
    """
    CREATE TABLE IF NOT EXISTS players (
        id SERIAL PRIMARY KEY,
        name TEXT NOT NULL,
        created_at TIMESTAMPTZ DEFAULT NOW()
    )
    """,
    # Singles matches
    """
    CREATE TABLE IF NOT EXISTS singles_matches (
        id SERIAL PRIMARY KEY,
        sport_id TEXT NOT NULL,
        match_date DATE NOT NULL,
        player1_id INTEGER NOT NULL REFERENCES players(id) ON DELETE RESTRICT,
        player2_id INTEGER NOT NULL REFERENCES players(id) ON DELETE RESTRICT,
        score1 SMALLINT NOT NULL,
        score2 SMALLINT NOT NULL,
        created_at TIMESTAMPTZ DEFAULT NOW()
    )
    """,
    # Doubles matches
    """
    CREATE TABLE IF NOT EXISTS doubles_matches (
        id SERIAL PRIMARY KEY,
        sport_id TEXT NOT NULL,
        match_date DATE NOT NULL,
        team1_player1_id INTEGER NOT NULL REFERENCES players(id) ON DELETE RESTRICT,
        team1_player2_id INTEGER NOT NULL REFERENCES players(id) ON DELETE RESTRICT,
        team2_player1_id INTEGER NOT NULL REFERENCES players(id) ON DELETE RESTRICT,
        team2_player2_id INTEGER NOT NULL REFERENCES players(id) ON DELETE RESTRICT,
        score1 SMALLINT NOT NULL,
        score2 SMALLINT NOT NULL,
        created_at TIMESTAMPTZ DEFAULT NOW()
    )
    """,
    # FFA matches (header)
    """
    CREATE TABLE IF NOT EXISTS ffa_matches (
        id SERIAL PRIMARY KEY,
        sport_id TEXT NOT NULL,
        match_date DATE NOT NULL,
        created_at TIMESTAMPTZ DEFAULT NOW()
    )
    """,
    # FFA results (child rows)
    """
    CREATE TABLE IF NOT EXISTS ffa_results (
        id SERIAL PRIMARY KEY,
        match_id INTEGER NOT NULL REFERENCES ffa_matches(id) ON DELETE CASCADE,
        player_id INTEGER NOT NULL REFERENCES players(id) ON DELETE RESTRICT,
        score SMALLINT NOT NULL,
        rank SMALLINT NOT NULL
    )
    """,
]

_INDEX_STATEMENTS = [
    # Singles indexes
    "CREATE INDEX IF NOT EXISTS idx_singles_sport ON singles_matches (sport_id)",
    "CREATE INDEX IF NOT EXISTS idx_singles_date ON singles_matches (match_date)",
    "CREATE INDEX IF NOT EXISTS idx_singles_p1 ON singles_matches (player1_id)",
    "CREATE INDEX IF NOT EXISTS idx_singles_p2 ON singles_matches (player2_id)",
    # Doubles indexes
    "CREATE INDEX IF NOT EXISTS idx_doubles_sport ON doubles_matches (sport_id)",
    "CREATE INDEX IF NOT EXISTS idx_doubles_date ON doubles_matches (match_date)",
    "CREATE INDEX IF NOT EXISTS idx_doubles_t1p1 ON doubles_matches (team1_player1_id)",
    "CREATE INDEX IF NOT EXISTS idx_doubles_t1p2 ON doubles_matches (team1_player2_id)",
    "CREATE INDEX IF NOT EXISTS idx_doubles_t2p1 ON doubles_matches (team2_player1_id)",
    "CREATE INDEX IF NOT EXISTS idx_doubles_t2p2 ON doubles_matches (team2_player2_id)",
    # FFA indexes
    "CREATE INDEX IF NOT EXISTS idx_ffa_sport ON ffa_matches (sport_id)",
    "CREATE INDEX IF NOT EXISTS idx_ffa_date ON ffa_matches (match_date)",
    "CREATE INDEX IF NOT EXISTS idx_ffa_results_match ON ffa_results (match_id)",
    "CREATE INDEX IF NOT EXISTS idx_ffa_results_player ON ffa_results (player_id)",
]


def init_db():
    """Create all tables and indexes if they do not already exist."""
    with get_conn() as conn:
        _run_ddl(conn, _TABLE_STATEMENTS)
        _run_ddl(conn, _INDEX_STATEMENTS)
