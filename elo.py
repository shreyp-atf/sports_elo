"""Pure ELO math: rating computations for singles, doubles, and FFA matches."""

from collections import defaultdict
from math import pow

DEFAULT_RATING = 1000
K = 32


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


# ---------------------------------------------------------------------------
# Singles ELO computation
# ---------------------------------------------------------------------------

def compute_singles_ratings(matches, players=None):
    """Compute ELO ratings and history from a list of singles matches.

    Args:
        matches: list of {date, player1, player2, score1, score2}
                 player1/player2 are player IDs (int).
        players: optional set of player IDs to seed with default ratings

    Returns:
        (ratings, history, matches)
        - ratings: dict player_id -> current rating
        - history: dict player_id -> list of (match_number, rating)
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
        matches: list of {date, team1: [id, id], team2: [id, id], score1, score2}
                 team members are player IDs (int).
        players: optional set of player IDs to seed with default ratings

    Returns:
        (ratings, history, matches)
        Ratings and history are keyed by player ID.
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
                 player values are player IDs (int).
        players: optional set of player IDs to seed with default ratings

    Returns:
        (ratings, history, matches)
        Ratings and history are keyed by player ID.
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
