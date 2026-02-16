import json
import os
from collections import defaultdict
from datetime import datetime
from math import pow

DEFAULT_RATING = 1000
K = 32

PLAYERS_FILE = "data/players.json"
SPORTS_CONFIG_FILE = "sports_config.json"


# ---------------------------------------------------------------------------
# Core ELO math
# ---------------------------------------------------------------------------

def expected_score(ra, rb):
    return 1 / (1 + pow(10, (rb - ra) / 400))


def update_elo(ra, rb, result_a):
    ea = expected_score(ra, rb)
    ra_new = ra + K * (result_a - ea)
    rb_new = rb + K * ((1 - result_a) - (1 - ea))
    return ra_new, rb_new


def today():
    return datetime.today().strftime("%Y-%m-%d")


# ---------------------------------------------------------------------------
# JSON I/O helpers
# ---------------------------------------------------------------------------

def _load_json(path):
    if not os.path.exists(path):
        return [] if path.endswith(".json") else {}
    with open(path, "r") as f:
        return json.load(f)


def _save_json(path, data):
    dir_name = os.path.dirname(path)
    if dir_name:
        os.makedirs(dir_name, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


# ---------------------------------------------------------------------------
# Config & player loading
# ---------------------------------------------------------------------------

def load_sports_config():
    """Load the sports configuration file."""
    return _load_json(SPORTS_CONFIG_FILE).get("sports", [])


def get_sport_config(sport_id):
    """Get config for a single sport by its id."""
    for sport in load_sports_config():
        if sport["id"] == sport_id:
            return sport
    return None


def load_players():
    """Load the central player list from data/players.json."""
    data = _load_json(PLAYERS_FILE)
    if isinstance(data, dict):
        return set(data.get("players", []))
    return set()


def save_players(players):
    """Save the player list to data/players.json."""
    _save_json(PLAYERS_FILE, {"players": sorted(players)})


def add_player(name):
    """Add a new player to the central registry. Returns True if added, False if already exists."""
    players = load_players()
    if name in players:
        return False
    players.add(name)
    save_players(players)
    return True


# ---------------------------------------------------------------------------
# Match data loading
# ---------------------------------------------------------------------------

def load_matches(data_file):
    """Load matches from a sport-specific data file."""
    return _load_json(data_file)


def save_matches(data_file, matches):
    """Save matches to a sport-specific data file."""
    _save_json(data_file, matches)


def load_sport_matches(sport_id):
    """Load all match data for a sport, keyed by match type.

    Returns dict like:
        {"singles": [...], "doubles": [...]}
    """
    config = get_sport_config(sport_id)
    if not config:
        return {}
    result = {}
    for match_type, data_file in config.get("match_types", {}).items():
        result[match_type] = load_matches(data_file)
    return result


# ---------------------------------------------------------------------------
# Singles ELO computation
# ---------------------------------------------------------------------------

def compute_singles_ratings(matches, players=None):
    """Compute ELO ratings and history from a list of singles matches.

    Args:
        matches: list of {date, player1, player2, score1, score2}
        players: optional set of player names to seed with default ratings

    Returns:
        (ratings, history, matches)
        - ratings: dict player -> current rating
        - history: dict player -> list of (match_number, rating)
        - matches: the input match list (passthrough for convenience)
    """
    if players is None:
        players = set()

    ratings = {p: DEFAULT_RATING for p in players}
    history = {p: [(0, DEFAULT_RATING)] for p in players}

    match_number = 1

    for match in matches:
        p1, p2 = match["player1"], match["player2"]
        s1, s2 = match["score1"], match["score2"]

        for p in [p1, p2]:
            if p not in ratings:
                ratings[p] = DEFAULT_RATING
                history[p] = [(0, DEFAULT_RATING)]

        if s1 == s2:
            continue

        winner, loser = (p1, p2) if s1 > s2 else (p2, p1)
        rw, rl = ratings[winner], ratings[loser]
        rw_new, rl_new = update_elo(rw, rl, 1)

        ratings[winner] = round(rw_new, 2)
        ratings[loser] = round(rl_new, 2)
        history[winner].append((match_number, round(rw_new, 2)))
        history[loser].append((match_number, round(rl_new, 2)))

        match_number += 1

    return ratings, history, matches


# ---------------------------------------------------------------------------
# Doubles ELO computation
# ---------------------------------------------------------------------------

def compute_doubles_ratings(matches, players=None):
    """Compute ELO ratings and history from a list of doubles matches.

    Args:
        matches: list of {date, team1: [p, p], team2: [p, p], score1, score2}
        players: optional set of player names to seed with default ratings

    Returns:
        (ratings, history, matches)
    """
    if players is None:
        players = set()

    ratings = defaultdict(lambda: DEFAULT_RATING)
    history = defaultdict(lambda: [(0, DEFAULT_RATING)])

    for p in players:
        ratings[p] = DEFAULT_RATING
        history[p] = [(0, DEFAULT_RATING)]

    match_number = 1

    for match in matches:
        team1 = match["team1"]
        team2 = match["team2"]
        s1 = match["score1"]
        s2 = match["score2"]

        if s1 == s2 or set(team1) & set(team2):
            continue

        r1 = sum(ratings[p] for p in team1) / len(team1)
        r2 = sum(ratings[p] for p in team2) / len(team2)

        result = 1 if s1 > s2 else 0
        r1_new, r2_new = update_elo(r1, r2, result)

        for p in team1:
            delta = r1_new - r1
            ratings[p] = round(ratings[p] + delta, 2)
            history[p].append((match_number, ratings[p]))

        for p in team2:
            delta = r2_new - r2
            ratings[p] = round(ratings[p] + delta, 2)
            history[p].append((match_number, ratings[p]))

        match_number += 1

    return dict(ratings), dict(history), matches


# ---------------------------------------------------------------------------
# Free-for-all ELO computation (for board games like Catan, Splendor)
# ---------------------------------------------------------------------------

def compute_ffa_ratings(matches, players=None):
    """Compute ELO ratings from free-for-all matches.

    Each match has a list of results with player, score, and rank.
    ELO is updated by treating each pair of players as a head-to-head,
    weighted by 1/(N-1) where N is the number of players.

    Args:
        matches: list of {date, results: [{player, score, rank}, ...]}
        players: optional set of player names to seed with default ratings

    Returns:
        (ratings, history, matches)
    """
    if players is None:
        players = set()

    ratings = defaultdict(lambda: DEFAULT_RATING)
    history = defaultdict(lambda: [(0, DEFAULT_RATING)])

    for p in players:
        ratings[p] = DEFAULT_RATING
        history[p] = [(0, DEFAULT_RATING)]

    match_number = 1

    for match in matches:
        results = match.get("results", [])
        if len(results) < 2:
            continue

        n = len(results)
        weight = 1 / (n - 1)

        elo_deltas = defaultdict(float)

        for i in range(n):
            for j in range(i + 1, n):
                pi = results[i]["player"]
                pj = results[j]["player"]
                ri = ratings[pi]
                rj = ratings[pj]

                # Lower rank = better (1st beats 2nd)
                rank_i = results[i]["rank"]
                rank_j = results[j]["rank"]

                if rank_i < rank_j:
                    result_i = 1
                elif rank_i > rank_j:
                    result_i = 0
                else:
                    result_i = 0.5

                ei = expected_score(ri, rj)
                elo_deltas[pi] += K * weight * (result_i - ei)
                elo_deltas[pj] += K * weight * ((1 - result_i) - (1 - ei))

        for result in results:
            p = result["player"]
            ratings[p] = round(ratings[p] + elo_deltas[p], 2)
            history[p].append((match_number, ratings[p]))

        match_number += 1

    return dict(ratings), dict(history), matches


# ---------------------------------------------------------------------------
# Unified computation dispatcher
# ---------------------------------------------------------------------------

MATCH_TYPE_COMPUTERS = {
    "singles": compute_singles_ratings,
    "doubles": compute_doubles_ratings,
    "ffa": compute_ffa_ratings,
}


def compute_ratings_for_sport(sport_id):
    """Compute ratings for all match types in a sport.

    Returns dict keyed by match_type:
        {
            "singles": (ratings, history, matches),
            "doubles": (ratings, history, matches),
        }
    """
    config = get_sport_config(sport_id)
    if not config:
        return {}

    players = load_players()
    all_matches = load_sport_matches(sport_id)
    results = {}

    for match_type, matches in all_matches.items():
        compute_fn = MATCH_TYPE_COMPUTERS.get(match_type)
        if compute_fn:
            results[match_type] = compute_fn(matches, players)

    return results


# ---------------------------------------------------------------------------
# Match entry helpers
# ---------------------------------------------------------------------------

def add_singles_match(data_file, player1, player2, score1, score2):
    """Add a singles match to a data file."""
    if player1 == player2:
        return "Players must be different."
    if score1 == score2:
        return "No ties allowed."

    match = {
        "date": today(),
        "player1": player1,
        "player2": player2,
        "score1": score1,
        "score2": score2,
    }

    existing = load_matches(data_file)
    existing.append(match)
    save_matches(data_file, existing)
    return None


def add_doubles_match(data_file, team1, team2, score1, score2):
    """Add a doubles match to a data file."""
    if set(team1) & set(team2):
        return "Teams cannot share players."
    if score1 == score2:
        return "No ties allowed."

    match = {
        "date": today(),
        "team1": team1,
        "team2": team2,
        "score1": score1,
        "score2": score2,
    }

    existing = load_matches(data_file)
    existing.append(match)
    save_matches(data_file, existing)
    return None


def add_ffa_match(data_file, results):
    """Add a free-for-all match to a data file.

    Args:
        results: list of {player, score, rank}
    """
    if len(results) < 2:
        return "Need at least 2 players."

    match = {
        "date": today(),
        "results": results,
    }

    existing = load_matches(data_file)
    existing.append(match)
    save_matches(data_file, existing)
    return None
