"""Match history page: tables showing all matches for a sport."""

import streamlit as st
import pandas as pd


def render_match_history(sport_data, sport_config, player_map):
    """Render match history tables for all match types in a sport."""
    match_types = sport_config.get("match_types", [])

    for mtype in match_types:
        if mtype not in sport_data:
            continue

        _, _, matches = sport_data[mtype]
        label = mtype.replace("_", " ").title()

        st.header(f"📜 {label} Match History")

        if not matches:
            st.info(f"No {label.lower()} matches yet.")
            continue

        if mtype == "singles":
            rows = []
            for m in matches:
                rows.append({
                    "Date": m.get("date", ""),
                    "Player 1": m["player1_name"],
                    "Score 1": m["score1"],
                    "Score 2": m["score2"],
                    "Player 2": m["player2_name"],
                })
            df = pd.DataFrame(rows)
            st.dataframe(df[::-1].reset_index(drop=True), use_container_width=True)

        elif mtype == "doubles":
            rows = []
            for m in matches:
                rows.append({
                    "Date": m.get("date", ""),
                    "Team 1": " + ".join(m["team1_names"]),
                    "Score 1": m["score1"],
                    "Score 2": m["score2"],
                    "Team 2": " + ".join(m["team2_names"]),
                })
            df = pd.DataFrame(rows)
            st.dataframe(df[::-1].reset_index(drop=True), use_container_width=True)

        elif mtype == "ffa":
            rows = []
            for m in matches:
                results = m.get("results", [])
                sorted_results = sorted(results, key=lambda r: r.get("rank", 99))
                summary = ", ".join(
                    f"#{r['rank']} {r['player_name']} ({r.get('score', '-')})"
                    for r in sorted_results
                )
                rows.append({
                    "Date": m.get("date", ""),
                    "Results": summary,
                })
            df = pd.DataFrame(rows)
            st.dataframe(df[::-1].reset_index(drop=True), use_container_width=True)
