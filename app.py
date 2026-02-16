import streamlit as st

from elo import compute_ratings_for_sport, load_players
from components.sidebar import render_sport_selector, render_page_selector, render_club_stats
from components.leaderboard import render_leaderboard
from components.analytics import render_analytics
from components.match_history import render_match_history
from components.player_profile import render_player_profile
from components.admin import render_admin_page


st.set_page_config(page_title="Sports Elo Tracker", layout="wide")

# --- Sidebar ---
sport = render_sport_selector()
if sport is None:
    st.stop()

page = render_page_selector()

# Compute data for the selected sport
sport_data = compute_ratings_for_sport(sport["id"])

render_club_stats(sport, sport_data)

# --- Main content ---
st.title(f"{sport['emoji']} {sport['name']} Dashboard")

if page == "Leaderboard":
    render_leaderboard(sport_data, sport)

elif page == "Analytics":
    render_analytics(sport_data, sport)

elif page == "Match History":
    render_match_history(sport_data, sport)

elif page == "Player Profile":
    render_player_profile()

elif page == "Admin":
    render_admin_page()

elif page == "Club Members":
    st.header("Club Members")
    all_players = sorted(load_players())
    if not all_players:
        st.info("No players registered yet. Add players to data/players.json.")
    else:
        # Determine which players are active in current sport
        active = set()
        for mtype, (ratings, history, matches) in sport_data.items():
            if mtype == "singles":
                for m in matches:
                    active.update([m["player1"], m["player2"]])
            elif mtype == "doubles":
                for m in matches:
                    active.update(m["team1"] + m["team2"])
            elif mtype == "ffa":
                for m in matches:
                    for r in m.get("results", []):
                        active.add(r["player"])

        import pandas as pd
        members_df = pd.DataFrame([
            {
                "Player": p,
                "Status": "🟢 Active" if p in active else "⚪ Inactive",
            }
            for p in all_players
        ])
        st.dataframe(members_df, use_container_width=True)
