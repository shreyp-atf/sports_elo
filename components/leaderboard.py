"""Leaderboard page: ELO ratings tables and individual ELO history charts."""

import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from components.charts import apply_dark_style


def _get_active_players_singles(matches):
    active = set()
    for m in matches:
        active.update([m["player1"], m["player2"]])
    return active


def _get_active_players_doubles(matches):
    active = set()
    for m in matches:
        active.update(m["team1"] + m["team2"])
    return active


def _get_active_players_ffa(matches):
    active = set()
    for m in matches:
        for r in m.get("results", []):
            active.add(r["player"])
    return active


def render_ratings_table(ratings, active_players, player_map, label="Rating"):
    """Render a sortable ELO ratings table."""
    data = [
        (player_map.get(p, f"#{p}"), ratings[p]) for p in ratings if p in active_players
    ]
    if not data:
        st.info("No rated players yet. Play some matches!")
        return

    df = pd.DataFrame(data, columns=["Player", label])
    df = df.sort_values(by=label, ascending=False).reset_index(drop=True)
    df.index += 1
    st.dataframe(df.style.format({label: "{:.1f}"}), use_container_width=True)


def render_elo_history_chart(history, active_players, player_map, key_prefix=""):
    """Render a single-player ELO history line chart."""
    graph_data = _build_graph_data(history, active_players, player_map)
    if not graph_data:
        return

    graph_df = pd.DataFrame(graph_data)
    unique_players = sorted(graph_df["Player"].unique())

    if not unique_players:
        return

    selected = st.selectbox(
        "Select a player to view their Elo trend:",
        unique_players,
        key=f"{key_prefix}_elo_history_player",
    )

    player_df = graph_df[graph_df["Player"] == selected].sort_values("Match #")
    player_actual = player_df[
        player_df["Elo Rating"] != player_df["Elo Rating"].shift()
    ].reset_index(drop=True)
    player_actual["Player Match #"] = player_actual.index + 1

    player_df = player_df.merge(
        player_actual[["Match #", "Player Match #"]],
        on="Match #",
        how="left",
    )
    player_df["Player Match #"] = player_df["Player Match #"].ffill()

    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(
        player_df["Player Match #"],
        player_df["Elo Rating"],
        marker="o",
        linewidth=2,
        color="#67cfff",
        label="Elo Rating",
    )
    ax.set_xlabel("Player's Match #", fontsize=12)
    ax.set_ylabel("Elo Rating", fontsize=12)
    ax.grid(alpha=0.3)
    apply_dark_style(fig, ax, title=f"Elo Progress: {selected}")
    st.pyplot(fig)


def _build_graph_data(history, active_players, player_map):
    """Build interpolated graph data from ELO history."""
    all_match_nums = [
        mn for series in history.values() for mn, _ in series
    ]
    if not all_match_nums:
        return []

    max_match_num = max(all_match_nums)
    graph_data = []

    for player_id, series in history.items():
        if player_id not in active_players or not series:
            continue

        player_name = player_map.get(player_id, f"#{player_id}")

        for i in range(len(series)):
            match_num, rating = series[i]
            graph_data.append(
                {"Player": player_name, "Match #": match_num, "Elo Rating": rating}
            )
            if i < len(series) - 1:
                next_match_num, _ = series[i + 1]
                for skipped in range(match_num + 1, next_match_num):
                    graph_data.append(
                        {"Player": player_name, "Match #": skipped, "Elo Rating": rating}
                    )

        last_match_num, last_rating = series[-1]
        if last_match_num < max_match_num:
            graph_data.append(
                {"Player": player_name, "Match #": max_match_num, "Elo Rating": last_rating}
            )

    return graph_data


def render_leaderboard(sport_data, sport_config, player_map):
    """Main leaderboard page renderer."""
    match_types = sport_config.get("match_types", [])

    for mtype in match_types:
        if mtype not in sport_data:
            continue

        ratings, history, matches = sport_data[mtype]
        label = mtype.replace("_", " ").title()

        st.header(f"📊 {label} Elo Ratings")

        if mtype == "singles":
            active = _get_active_players_singles(matches)
        elif mtype == "doubles":
            active = _get_active_players_doubles(matches)
        elif mtype == "ffa":
            active = _get_active_players_ffa(matches)
        else:
            active = set()

        render_ratings_table(ratings, active, player_map, label=f"{label} Elo")

        st.subheader(f"🔍 {label} Elo History")
        render_elo_history_chart(
            history, active, player_map,
            key_prefix=f"{sport_config['id']}_{mtype}",
        )
