"""Player profile page: cross-sport view of a single player."""

import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

from data_utils import load_sports_config, compute_ratings_for_sport
from components.charts import apply_dark_style, apply_dark_legend


def _get_player_sport_stats(player_id, sport_config, sport_data, player_map):
    """Gather per-match-type stats for a player in a sport."""
    results = []
    for mtype, (ratings, history, matches) in sport_data.items():
        elo = ratings.get(player_id)
        if elo is None:
            continue

        ph = history.get(player_id, [])
        match_count = len(ph) - 1 if len(ph) > 1 else 0
        if match_count <= 0:
            continue

        wins = 0
        losses = 0
        if mtype == "singles":
            for m in matches:
                if m["player1"] == player_id:
                    if m["score1"] > m["score2"]:
                        wins += 1
                    elif m["score1"] < m["score2"]:
                        losses += 1
                elif m["player2"] == player_id:
                    if m["score2"] > m["score1"]:
                        wins += 1
                    elif m["score2"] < m["score1"]:
                        losses += 1
        elif mtype == "doubles":
            for m in matches:
                in_t1 = player_id in m["team1"]
                in_t2 = player_id in m["team2"]
                if not in_t1 and not in_t2:
                    continue
                if in_t1:
                    if m["score1"] > m["score2"]:
                        wins += 1
                    else:
                        losses += 1
                else:
                    if m["score2"] > m["score1"]:
                        wins += 1
                    else:
                        losses += 1
        elif mtype == "ffa":
            for m in matches:
                for r in m.get("results", []):
                    if r["player"] == player_id:
                        if r["rank"] == 1:
                            wins += 1
                        else:
                            losses += 1

        results.append({
            "match_type": mtype,
            "elo": elo,
            "matches": wins + losses,
            "wins": wins,
            "losses": losses,
            "win_pct": round(wins / (wins + losses) * 100, 1) if (wins + losses) > 0 else 0,
            "history": ph,
        })

    return results


def render_player_profile(player_map):
    """Render the cross-sport player profile page."""
    if not player_map:
        st.info("No players registered yet.")
        return

    sorted_ids = sorted(player_map.keys(), key=lambda pid: player_map[pid])
    labels = {pid: player_map[pid] for pid in sorted_ids}

    selected_id = st.selectbox(
        "Select a player:",
        sorted_ids,
        format_func=lambda pid: labels[pid],
        key="profile_player",
    )
    selected_name = player_map[selected_id]

    sports = load_sports_config()

    all_sport_stats = []
    for sport in sports:
        sport_data = compute_ratings_for_sport(sport["id"])
        player_stats = _get_player_sport_stats(selected_id, sport, sport_data, player_map)
        for ps in player_stats:
            ps["sport"] = sport["name"]
            ps["sport_emoji"] = sport["emoji"]
            ps["sport_id"] = sport["id"]
            all_sport_stats.append(ps)

    if not all_sport_stats:
        st.info(f"{selected_name} hasn't played any matches yet.")
        return

    # Summary cards
    st.header(f"Player Profile: {selected_name}")

    cols = st.columns(len(all_sport_stats))
    for i, ps in enumerate(all_sport_stats):
        with cols[i]:
            st.markdown(f"### {ps['sport_emoji']} {ps['sport']} ({ps['match_type'].title()})")
            st.metric("ELO", f"{ps['elo']:.1f}")
            st.metric("Record", f"{ps['wins']}W - {ps['losses']}L")
            st.metric("Win %", f"{ps['win_pct']:.1f}%")

    # Overlaid ELO over time chart
    st.header("ELO Over Time (All Sports)")

    fig, ax = plt.subplots(figsize=(12, 5))
    colors = plt.cm.tab10(np.linspace(0, 1, max(len(all_sport_stats), 1)))

    for idx, ps in enumerate(all_sport_stats):
        ph = ps["history"]
        if len(ph) < 2:
            continue
        match_nums = list(range(len(ph)))
        elos = [r for _, r in ph]
        label = f"{ps['sport_emoji']} {ps['sport']} {ps['match_type'].title()}"
        ax.plot(match_nums, elos, marker="o", linewidth=2, label=label, color=colors[idx], alpha=0.8)

    ax.set_xlabel("Player's Match #", fontsize=12, fontweight="bold")
    ax.set_ylabel("ELO Rating", fontsize=12, fontweight="bold")
    apply_dark_style(fig, ax, title=f"ELO Journey: {selected_name}")
    apply_dark_legend(ax)
    ax.grid(alpha=0.3)
    st.pyplot(fig)

    # Recent matches table
    st.header("Recent Matches")
    recent_rows = []
    for sport in sports:
        sport_data = compute_ratings_for_sport(sport["id"])
        for mtype, (_, _, matches) in sport_data.items():
            if mtype == "singles":
                for m in matches:
                    if m["player1"] == selected_id or m["player2"] == selected_id:
                        if m["player1"] == selected_id:
                            opponent_name = m["player2_name"]
                            my_score = m["score1"]
                            opp_score = m["score2"]
                        else:
                            opponent_name = m["player1_name"]
                            my_score = m["score2"]
                            opp_score = m["score1"]
                        result = "W" if my_score > opp_score else "L"
                        recent_rows.append({
                            "Date": m.get("date", ""),
                            "Sport": f"{sport['emoji']} {sport['name']}",
                            "Type": mtype.title(),
                            "Opponent": opponent_name,
                            "Score": f"{my_score}-{opp_score}",
                            "Result": result,
                        })
            elif mtype == "doubles":
                for m in matches:
                    in_t1 = selected_id in m["team1"]
                    in_t2 = selected_id in m["team2"]
                    if not in_t1 and not in_t2:
                        continue
                    my_team_names = m["team1_names"] if in_t1 else m["team2_names"]
                    opp_team_names = m["team2_names"] if in_t1 else m["team1_names"]
                    my_score = m["score1"] if in_t1 else m["score2"]
                    opp_score = m["score2"] if in_t1 else m["score1"]
                    result = "W" if my_score > opp_score else "L"
                    recent_rows.append({
                        "Date": m.get("date", ""),
                        "Sport": f"{sport['emoji']} {sport['name']}",
                        "Type": mtype.title(),
                        "Opponent": " + ".join(opp_team_names),
                        "Score": f"{my_score}-{opp_score}",
                        "Result": result,
                    })

    if recent_rows:
        df = pd.DataFrame(recent_rows)
        df = df.sort_values("Date", ascending=False).reset_index(drop=True)
        st.dataframe(df.head(50), use_container_width=True)
    else:
        st.info("No matches found.")
