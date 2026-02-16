"""Sidebar rendering: sport selector, page navigation, club stats."""

import streamlit as st
from elo import load_sports_config, load_players


def render_sport_selector():
    """Render the sport dropdown and return the selected sport config."""
    sports = load_sports_config()
    if not sports:
        st.sidebar.warning("No sports configured.")
        return None

    sport_labels = [f"{s['emoji']} {s['name']}" for s in sports]
    selected_idx = st.sidebar.selectbox(
        "Select Sport",
        range(len(sports)),
        format_func=lambda i: sport_labels[i],
        key="sport_selector",
    )
    return sports[selected_idx]


def render_page_selector():
    """Render page navigation and return the selected page."""
    pages = [
        "Leaderboard",
        "Analytics",
        "Match History",
        "Player Profile",
        "Club Members",
        "Admin",
    ]
    return st.sidebar.radio("Page", pages, key="page_selector")


def render_club_stats(sport_config, sport_data):
    """Render sidebar club stats for the selected sport."""
    st.sidebar.header(f"📊 {sport_config['name']} Stats")

    players = load_players()
    match_types = sport_config.get("match_types", {})

    total_matches = 0
    active_player_set = set()

    for mtype, data_file in match_types.items():
        matches = sport_data.get(mtype, (None, None, []))[2]
        total_matches += len(matches)

        if mtype == "singles":
            for m in matches:
                active_player_set.update([m["player1"], m["player2"]])
        elif mtype == "doubles":
            for m in matches:
                active_player_set.update(m["team1"] + m["team2"])
        elif mtype == "ffa":
            for m in matches:
                for r in m.get("results", []):
                    active_player_set.add(r["player"])

    st.sidebar.markdown(f"""
- 🧑 **Club Members:** {len(players)}
- 🏃 **Active Players:** {len(active_player_set)}
- 🎮 **Matches Played:** {total_matches}
""")
