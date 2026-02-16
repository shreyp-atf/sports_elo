"""Data I/O layer: config loading, player management, match storage, and
orchestration of ELO computation for sports.

All persistence is backed by PostgreSQL.  JSON is only used for the static
sports configuration file.
"""

import json
from datetime import datetime

from psycopg2.extras import RealDictCursor

from db import get_conn
from elo import MATCH_TYPE_COMPUTERS

SPORTS_CONFIG_FILE = "sports_config.json"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def today():
    return datetime.today().strftime("%Y-%m-%d")


# ---------------------------------------------------------------------------
# Config loading (still file-based)
# ---------------------------------------------------------------------------

def load_sports_config():
    """Load the sports configuration file."""
    try:
        with open(SPORTS_CONFIG_FILE, "r") as f:
            return json.load(f).get("sports", [])
    except FileNotFoundError:
        return []


def get_sport_config(sport_id):
    """Get config for a single sport by its id."""
    for sport in load_sports_config():
        if sport["id"] == sport_id:
            return sport
    return None


# ---------------------------------------------------------------------------
# Player management
# ---------------------------------------------------------------------------

def load_players():
    """Load all players from the database.

    Returns:
        dict mapping player id (int) -> name (str), ordered by name.
    """
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT id, name FROM players ORDER BY name")
            rows = cur.fetchall()
    return {row["id"]: row["name"] for row in rows}


def add_player(name):
    """Add a new player to the database.

    Returns:
        The new player's id (int).
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO players (name) VALUES (%(name)s) RETURNING id",
                {"name": name},
            )
            return cur.fetchone()[0]


# ---------------------------------------------------------------------------
# Match loading
# ---------------------------------------------------------------------------

def load_singles_matches(sport_id):
    """Load all singles matches for a sport, with player names resolved.

    Returns list of dicts with keys:
        player1, player2 (IDs), player1_name, player2_name,
        score1, score2, date
    """
    sql = """
        SELECT
            sm.match_date  AS date,
            sm.player1_id  AS player1,
            sm.player2_id  AS player2,
            p1.name        AS player1_name,
            p2.name        AS player2_name,
            sm.score1,
            sm.score2
        FROM singles_matches sm
        JOIN players p1 ON p1.id = sm.player1_id
        JOIN players p2 ON p2.id = sm.player2_id
        WHERE sm.sport_id = %(sport_id)s
        ORDER BY sm.id
    """
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, {"sport_id": sport_id})
            rows = cur.fetchall()
    result = []
    for r in rows:
        result.append({
            "date": r["date"].isoformat() if hasattr(r["date"], "isoformat") else str(r["date"]),
            "player1": r["player1"],
            "player2": r["player2"],
            "player1_name": r["player1_name"],
            "player2_name": r["player2_name"],
            "score1": r["score1"],
            "score2": r["score2"],
        })
    return result


def load_doubles_matches(sport_id):
    """Load all doubles matches for a sport, with player names resolved.

    Returns list of dicts with keys:
        team1 ([id, id]), team2 ([id, id]),
        team1_names ([name, name]), team2_names ([name, name]),
        score1, score2, date
    """
    sql = """
        SELECT
            dm.match_date       AS date,
            dm.team1_player1_id AS t1p1,
            dm.team1_player2_id AS t1p2,
            dm.team2_player1_id AS t2p1,
            dm.team2_player2_id AS t2p2,
            p1.name             AS t1p1_name,
            p2.name             AS t1p2_name,
            p3.name             AS t2p1_name,
            p4.name             AS t2p2_name,
            dm.score1,
            dm.score2
        FROM doubles_matches dm
        JOIN players p1 ON p1.id = dm.team1_player1_id
        JOIN players p2 ON p2.id = dm.team1_player2_id
        JOIN players p3 ON p3.id = dm.team2_player1_id
        JOIN players p4 ON p4.id = dm.team2_player2_id
        WHERE dm.sport_id = %(sport_id)s
        ORDER BY dm.id
    """
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, {"sport_id": sport_id})
            rows = cur.fetchall()
    result = []
    for r in rows:
        result.append({
            "date": r["date"].isoformat() if hasattr(r["date"], "isoformat") else str(r["date"]),
            "team1": [r["t1p1"], r["t1p2"]],
            "team2": [r["t2p1"], r["t2p2"]],
            "team1_names": [r["t1p1_name"], r["t1p2_name"]],
            "team2_names": [r["t2p1_name"], r["t2p2_name"]],
            "score1": r["score1"],
            "score2": r["score2"],
        })
    return result


def load_ffa_matches(sport_id):
    """Load all FFA matches for a sport, with player names resolved.

    Returns list of dicts with keys:
        date, results: [{player (id), player_name, score, rank}, ...]
    """
    header_sql = """
        SELECT id, match_date AS date
        FROM ffa_matches
        WHERE sport_id = %(sport_id)s
        ORDER BY id
    """
    results_sql = """
        SELECT
            fr.match_id,
            fr.player_id  AS player,
            p.name         AS player_name,
            fr.score,
            fr.rank
        FROM ffa_results fr
        JOIN players p ON p.id = fr.player_id
        WHERE fr.match_id = ANY(%(match_ids)s)
        ORDER BY fr.match_id, fr.rank
    """
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(header_sql, {"sport_id": sport_id})
            headers = cur.fetchall()

            if not headers:
                return []

            match_ids = [h["id"] for h in headers]
            cur.execute(results_sql, {"match_ids": match_ids})
            all_results = cur.fetchall()

    results_by_match = {}
    for r in all_results:
        mid = r["match_id"]
        results_by_match.setdefault(mid, []).append({
            "player": r["player"],
            "player_name": r["player_name"],
            "score": r["score"],
            "rank": r["rank"],
        })

    output = []
    for h in headers:
        output.append({
            "date": h["date"].isoformat() if hasattr(h["date"], "isoformat") else str(h["date"]),
            "results": results_by_match.get(h["id"], []),
        })
    return output


_MATCH_LOADERS = {
    "singles": load_singles_matches,
    "doubles": load_doubles_matches,
    "ffa": load_ffa_matches,
}


def load_sport_matches(sport_id):
    """Load all match data for a sport, keyed by match type.

    Returns dict like:
        {"singles": [...], "doubles": [...]}
    """
    config = get_sport_config(sport_id)
    if not config:
        return {}
    result = {}
    for match_type in config.get("match_types", []):
        loader = _MATCH_LOADERS.get(match_type)
        if loader:
            result[match_type] = loader(sport_id)
    return result


# ---------------------------------------------------------------------------
# Unified computation dispatcher
# ---------------------------------------------------------------------------

def compute_ratings_for_sport(sport_id):
    """Compute ratings for all match types in a sport.

    Returns dict keyed by match_type:
        {
            "singles": (ratings, history, matches),
            "doubles": (ratings, history, matches),
        }
    where ratings and history are keyed by player id (int).
    """
    config = get_sport_config(sport_id)
    if not config:
        return {}

    player_map = load_players()
    player_ids = set(player_map.keys())
    all_matches = load_sport_matches(sport_id)
    results = {}

    for match_type, matches in all_matches.items():
        compute_fn = MATCH_TYPE_COMPUTERS.get(match_type)
        if compute_fn:
            results[match_type] = compute_fn(matches, player_ids)

    return results


# ---------------------------------------------------------------------------
# Match entry helpers
# ---------------------------------------------------------------------------

def add_singles_match(sport_id, player1_id, player2_id, score1, score2):
    """Insert a singles match. Returns error string or None on success."""
    if player1_id == player2_id:
        return "Players must be different."
    if score1 == score2:
        return "No ties allowed."

    sql = """
        INSERT INTO singles_matches
            (sport_id, match_date, player1_id, player2_id, score1, score2)
        VALUES
            (%(sport_id)s, %(match_date)s, %(p1)s, %(p2)s, %(s1)s, %(s2)s)
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, {
                "sport_id": sport_id,
                "match_date": today(),
                "p1": player1_id,
                "p2": player2_id,
                "s1": score1,
                "s2": score2,
            })
    return None


def add_doubles_match(sport_id, t1p1_id, t1p2_id, t2p1_id, t2p2_id, score1, score2):
    """Insert a doubles match. Returns error string or None on success."""
    team1 = {t1p1_id, t1p2_id}
    team2 = {t2p1_id, t2p2_id}
    if team1 & team2:
        return "Teams cannot share players."
    if score1 == score2:
        return "No ties allowed."

    sql = """
        INSERT INTO doubles_matches
            (sport_id, match_date,
             team1_player1_id, team1_player2_id,
             team2_player1_id, team2_player2_id,
             score1, score2)
        VALUES
            (%(sport_id)s, %(match_date)s,
             %(t1p1)s, %(t1p2)s, %(t2p1)s, %(t2p2)s,
             %(s1)s, %(s2)s)
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, {
                "sport_id": sport_id,
                "match_date": today(),
                "t1p1": t1p1_id,
                "t1p2": t1p2_id,
                "t2p1": t2p1_id,
                "t2p2": t2p2_id,
                "s1": score1,
                "s2": score2,
            })
    return None


def add_ffa_match(sport_id, results):
    """Insert an FFA match with its results.

    Args:
        sport_id: sport identifier string
        results: list of dicts with keys player_id, score, rank

    Returns error string or None on success.
    """
    if len(results) < 2:
        return "Need at least 2 players."

    insert_header = """
        INSERT INTO ffa_matches (sport_id, match_date)
        VALUES (%(sport_id)s, %(match_date)s)
        RETURNING id
    """
    insert_result = """
        INSERT INTO ffa_results (match_id, player_id, score, rank)
        VALUES (%(match_id)s, %(player_id)s, %(score)s, %(rank)s)
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(insert_header, {
                "sport_id": sport_id,
                "match_date": today(),
            })
            match_id = cur.fetchone()[0]

            for r in results:
                cur.execute(insert_result, {
                    "match_id": match_id,
                    "player_id": r["player_id"],
                    "score": r["score"],
                    "rank": r["rank"],
                })
    return None
