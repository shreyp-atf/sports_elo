"""Analytics page: player comparison, ELO distribution, top players,
recent form, competitiveness, activity, performance metrics, doubles partnership."""

import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from collections import defaultdict, Counter
from datetime import datetime

from components.charts import apply_dark_style, apply_dark_legend


# -----------------------------------------------------------------------
# Shared stat computation
# -----------------------------------------------------------------------

def compute_singles_stats(matches, active_players):
    """Compute per-player performance stats from singles matches."""
    stats = defaultdict(lambda: {
        "Wins": 0, "Losses": 0, "Games": 0,
        "Points Won": 0, "Points Lost": 0, "Streak History": [],
    })

    for match in matches:
        p1, p2 = match["player1"], match["player2"]
        s1, s2 = match["score1"], match["score2"]

        if s1 > s2:
            winner, loser = p1, p2
        else:
            winner, loser = p2, p1

        stats[winner]["Wins"] += 1
        stats[loser]["Losses"] += 1
        stats[p1]["Points Won"] += s1
        stats[p1]["Points Lost"] += s2
        stats[p2]["Points Won"] += s2
        stats[p2]["Points Lost"] += s1
        stats[p1]["Games"] += 1
        stats[p2]["Games"] += 1

        for player in [p1, p2]:
            result = "W" if player == winner else "L"
            stats[player]["Streak History"].append(result)

    return _process_stats(stats, active_players)


def compute_doubles_stats(matches, active_players):
    """Compute per-player performance stats from doubles matches."""
    stats = defaultdict(lambda: {
        "Wins": 0, "Losses": 0, "Games": 0,
        "Points Won": 0, "Points Lost": 0, "Streak History": [],
    })

    for match in matches:
        team1, team2 = match["team1"], match["team2"]
        s1, s2 = match["score1"], match["score2"]

        winners = team1 if s1 > s2 else team2
        losers = team2 if s1 > s2 else team1

        for p in winners:
            stats[p]["Wins"] += 1
            stats[p]["Streak History"].append("W")
        for p in losers:
            stats[p]["Losses"] += 1
            stats[p]["Streak History"].append("L")
        for p in team1 + team2:
            stats[p]["Games"] += 1
        for p in team1:
            stats[p]["Points Won"] += s1
            stats[p]["Points Lost"] += s2
        for p in team2:
            stats[p]["Points Won"] += s2
            stats[p]["Points Lost"] += s1

    return _process_stats(stats, active_players)


def _max_streak(seq, target):
    max_count = count = 0
    for res in seq:
        if res == target:
            count += 1
            max_count = max(max_count, count)
        else:
            count = 0
    return max_count


def _process_stats(stats, active_players):
    processed = []
    for player, data in stats.items():
        if player not in active_players:
            continue
        games = data["Games"]
        wins = data["Wins"]
        losses = data["Losses"]
        pw = data["Points Won"]
        pl = data["Points Lost"]
        history = data["Streak History"]

        current_streak = ""
        if history:
            last = history[-1]
            count = 0
            for res in reversed(history):
                if res == last:
                    count += 1
                else:
                    break
            current_streak = f"{count}{last}"

        processed.append({
            "Player": player,
            "Matches": wins + losses,
            "Wins": wins,
            "Losses": losses,
            "W/L %": round(wins / games * 100, 1) if games > 0 else 0,
            "Current Streak": current_streak,
            "Longest Win Streak": _max_streak(history, "W"),
            "Longest Loss Streak": _max_streak(history, "L"),
            "Avg Points Won": round(pw / games, 1) if games > 0 else 0,
            "Avg Points Lost": round(pl / games, 1) if games > 0 else 0,
        })

    return processed


# -----------------------------------------------------------------------
# Player stats table
# -----------------------------------------------------------------------

def render_player_stats(processed_stats):
    """Render the player performance stats table."""
    if not processed_stats:
        st.info("No match data yet.")
        return
    df = pd.DataFrame(processed_stats)
    df = df.sort_values("Wins", ascending=False).reset_index(drop=True)
    st.dataframe(df, use_container_width=True)


# -----------------------------------------------------------------------
# Player comparison tool (singles)
# -----------------------------------------------------------------------

def render_player_comparison(ratings, processed_stats, matches, active_players, key_prefix=""):
    """Radar chart comparing two players."""
    if len(active_players) < 2:
        st.info("Need at least 2 active players for comparison.")
        return

    sorted_players = sorted(active_players)

    col1, col2 = st.columns(2)
    with col1:
        p1 = st.selectbox("Player 1:", sorted_players, index=0, key=f"{key_prefix}_cmp1")
    with col2:
        idx2 = min(1, len(sorted_players) - 1)
        p2 = st.selectbox("Player 2:", sorted_players, index=idx2, key=f"{key_prefix}_cmp2")

    if p1 == p2:
        st.warning("Select two different players.")
        return

    p1_stats = next((s for s in processed_stats if s["Player"] == p1), None)
    p2_stats = next((s for s in processed_stats if s["Player"] == p2), None)

    if not p1_stats or not p2_stats:
        st.info("One or both players have no stats yet.")
        return

    col1, col2, col3 = st.columns([1, 2, 1])

    with col1:
        st.markdown(f"### {p1}")
        st.metric("ELO", f"{ratings.get(p1, 1000):.0f}")
        st.metric("Wins", p1_stats["Wins"])
        st.metric("Win %", f"{p1_stats['W/L %']:.1f}%")

    with col2:
        _render_radar_chart(ratings, p1, p2, p1_stats, p2_stats)

    with col3:
        st.markdown(f"### {p2}")
        st.metric("ELO", f"{ratings.get(p2, 1000):.0f}")
        st.metric("Wins", p2_stats["Wins"])
        st.metric("Win %", f"{p2_stats['W/L %']:.1f}%")

    # Head to head
    st.markdown("### Head-to-Head Record")
    h2h = [m for m in matches if
           (m["player1"] == p1 and m["player2"] == p2) or
           (m["player1"] == p2 and m["player2"] == p1)]

    if h2h:
        p1_wins = sum(1 for m in h2h if
                      (m["player1"] == p1 and m["score1"] > m["score2"]) or
                      (m["player2"] == p1 and m["score2"] > m["score1"]))
        p2_wins = len(h2h) - p1_wins
        c1, c2, c3 = st.columns(3)
        c1.metric(f"{p1} Wins", p1_wins)
        c2.metric("Total Matches", len(h2h))
        c3.metric(f"{p2} Wins", p2_wins)
    else:
        st.info("These players haven't faced each other yet!")


def _render_radar_chart(ratings, p1, p2, p1_stats, p2_stats):
    categories = ["ELO\n(norm)", "Win Rate", "Avg Pts\nWon", "Longest\nWin Streak", "Matches\nPlayed"]

    all_ratings = list(ratings.values())
    max_elo = max(all_ratings) if all_ratings else 1100
    min_elo = min(all_ratings) if all_ratings else 900
    elo_range = max_elo - min_elo or 1

    def vals(player, pstats):
        return [
            ((ratings.get(player, 1000) - min_elo) / elo_range) * 100,
            pstats["W/L %"],
            (pstats["Avg Points Won"] / 11) * 100,
            min(pstats["Longest Win Streak"] / 10 * 100, 100),
            min(pstats["Matches"] / 50 * 100, 100),
        ]

    p1_vals = vals(p1, p1_stats)
    p2_vals = vals(p2, p2_stats)

    angles = np.linspace(0, 2 * np.pi, len(categories), endpoint=False).tolist()
    p1_vals += p1_vals[:1]
    p2_vals += p2_vals[:1]
    angles += angles[:1]

    fig, ax = plt.subplots(figsize=(6, 6), subplot_kw=dict(projection="polar"))
    ax.plot(angles, p1_vals, "o-", linewidth=2, label=p1, color="#2196F3")
    ax.fill(angles, p1_vals, alpha=0.25, color="#2196F3")
    ax.plot(angles, p2_vals, "o-", linewidth=2, label=p2, color="#FF5722")
    ax.fill(angles, p2_vals, alpha=0.25, color="#FF5722")

    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(categories, size=9)
    ax.set_ylim(0, 100)
    ax.set_yticks([25, 50, 75, 100])
    ax.set_yticklabels(["25", "50", "75", "100"], size=8)
    ax.grid(True)

    # Dark mode
    ax.set_facecolor("#1e1e1e")
    fig.patch.set_facecolor("#1e1e1e")
    ax.tick_params(colors="white")
    ax.spines["polar"].set_color("white")
    for label in ax.get_xticklabels():
        label.set_color("white")
    for label in ax.get_yticklabels():
        label.set_color("white")
    legend = ax.legend(loc="upper right", bbox_to_anchor=(1.3, 1.1))
    legend.get_frame().set_facecolor("#2e2e2e")
    for text in legend.get_texts():
        text.set_color("white")

    st.pyplot(fig)


# -----------------------------------------------------------------------
# ELO distribution
# -----------------------------------------------------------------------

def render_elo_distribution(ratings, active_players):
    """Histogram of ELO ratings with tier colouring."""
    active_ratings = [ratings[p] for p in active_players if p in ratings]
    if not active_ratings:
        st.info("No rated players yet.")
        return

    col1, col2 = st.columns([2, 1])

    tiers = {
        "Elite": (1100, max(active_ratings) + 50, "#FFD700"),
        "Advanced": (1050, 1100, "#C0C0C0"),
        "Intermediate": (1000, 1050, "#CD7F32"),
        "Beginner": (min(active_ratings) - 50, 1000, "#87CEEB"),
    }

    with col1:
        fig, ax = plt.subplots(figsize=(10, 5))
        n, bins, patches = ax.hist(active_ratings, bins=15, edgecolor="black", alpha=0.7)
        for patch, left_edge in zip(patches, bins[:-1]):
            for _, (tmin, tmax, color) in tiers.items():
                if tmin <= left_edge < tmax:
                    patch.set_facecolor(color)
                    break
        ax.set_xlabel("ELO Rating", fontsize=12, fontweight="bold")
        ax.set_ylabel("Number of Players", fontsize=12, fontweight="bold")
        apply_dark_style(fig, ax, title="Player Rating Distribution")
        ax.grid(axis="y", alpha=0.3)
        st.pyplot(fig)

    with col2:
        st.markdown("### Player Tiers")
        for tier_name in ["Elite", "Advanced", "Intermediate", "Beginner"]:
            tmin, tmax, _ = tiers[tier_name]
            count = sum(1 for r in active_ratings if tmin <= r < tmax)
            st.markdown(f"**{tier_name}** ({tmin}-{tmax}): {count} players")
        st.markdown("---")
        st.metric("Median ELO", f"{np.median(active_ratings):.1f}")


# -----------------------------------------------------------------------
# Top players progression
# -----------------------------------------------------------------------

def render_top_players_progression(ratings, history, active_players, n=5):
    """Line chart showing ELO journey of top-N players."""
    if not active_players:
        return

    top_n = min(n, len(active_players))
    top_sorted = sorted(
        [(p, ratings[p]) for p in active_players if p in ratings],
        key=lambda x: x[1], reverse=True,
    )
    top_players = [p for p, _ in top_sorted[:top_n]]

    fig, ax = plt.subplots(figsize=(12, 6))
    colors = plt.cm.tab10(np.linspace(0, 1, top_n))

    for idx, player in enumerate(top_players):
        ph = history.get(player, [])
        if len(ph) > 1:
            match_nums = [m for m, _ in ph]
            elos = [r for _, r in ph]
            ax.plot(match_nums, elos, marker="o", linewidth=2.5,
                    label=player, color=colors[idx], alpha=0.8)

    ax.set_xlabel("Match Number", fontsize=12, fontweight="bold")
    ax.set_ylabel("ELO Rating", fontsize=12, fontweight="bold")
    apply_dark_style(fig, ax, title="Top Players ELO Journey")
    apply_dark_legend(ax)
    ax.grid(alpha=0.3)
    st.pyplot(fig)


# -----------------------------------------------------------------------
# Recent form
# -----------------------------------------------------------------------

def render_recent_form(matches, active_players, min_matches=10):
    """Table showing recent form based on last 10 matches."""
    form_data = []
    for player in active_players:
        pm = [m for m in matches if m["player1"] == player or m["player2"] == player]
        if len(pm) < min_matches:
            continue
        last = pm[-10:]
        wins = sum(
            1 for m in last
            if (m["player1"] == player and m["score1"] > m["score2"])
            or (m["player2"] == player and m["score2"] > m["score1"])
        )
        wr = (wins / len(last)) * 100
        if wr >= 70:
            form = "🔥 Hot"
        elif wr >= 50:
            form = "⚡ Solid"
        elif wr >= 30:
            form = "📉 Cooling"
        else:
            form = "🧊 Cold"
        form_data.append({
            "Player": player,
            "Last 10 W-L": f"{wins}-{len(last) - wins}",
            "Win Rate %": round(wr, 1),
            "Form": form,
        })

    if not form_data:
        st.info(f"No players with {min_matches}+ matches yet.")
        return
    df = pd.DataFrame(form_data).sort_values("Win Rate %", ascending=False).reset_index(drop=True)
    st.dataframe(df, use_container_width=True)


# -----------------------------------------------------------------------
# Match competitiveness
# -----------------------------------------------------------------------

def render_match_competitiveness(matches):
    """Score differential histogram and stats."""
    if not matches:
        st.info("No matches yet.")
        return

    diffs = [abs(m["score1"] - m["score2"]) for m in matches]

    col1, col2 = st.columns(2)
    with col1:
        fig, ax = plt.subplots(figsize=(6, 4))
        ax.hist(diffs, bins=range(0, max(diffs) + 2), edgecolor="black", color="#4CAF50", alpha=0.7)
        ax.set_xlabel("Score Differential", fontsize=10, fontweight="bold")
        ax.set_ylabel("Number of Matches", fontsize=10, fontweight="bold")
        apply_dark_style(fig, ax, title="How Close Are the Matches?")
        ax.grid(axis="y", alpha=0.3)
        st.pyplot(fig)

    with col2:
        st.markdown("### Match Stats")
        close = sum(1 for d in diffs if d <= 2)
        blowouts = sum(1 for d in diffs if d >= 5)
        avg = np.mean(diffs)
        n = len(diffs)
        st.metric("Close Matches (<=2 pts)", f"{close} ({close / n * 100:.1f}%)")
        st.metric("Blowouts (>=5 pts)", f"{blowouts} ({blowouts / n * 100:.1f}%)")
        st.metric("Avg Score Differential", f"{avg:.1f} points")


# -----------------------------------------------------------------------
# Activity chart
# -----------------------------------------------------------------------

def render_activity(matches, active_players):
    """Match activity over time + most active players."""
    dates = []
    for m in matches:
        try:
            dates.append(datetime.strptime(m["date"], "%Y-%m-%d"))
        except (KeyError, ValueError):
            continue

    if not dates:
        st.info("No dated matches yet.")
        return

    col1, col2 = st.columns([2, 1])

    with col1:
        date_counts = Counter([d.date() for d in dates])
        fig, ax = plt.subplots(figsize=(10, 4))
        sorted_dates = sorted(date_counts.keys())
        counts = [date_counts[d] for d in sorted_dates]
        ax.bar(sorted_dates, counts, color="#4CAF50", alpha=0.7, edgecolor="black")
        ax.set_xlabel("Date", fontsize=10, fontweight="bold")
        ax.set_ylabel("Matches Played", fontsize=10, fontweight="bold")
        apply_dark_style(fig, ax, title="Match Activity Over Time")
        ax.grid(axis="y", alpha=0.3)
        plt.xticks(rotation=45, ha="right")
        plt.tight_layout()
        st.pyplot(fig)

    with col2:
        st.markdown("### Activity Stats")
        player_counts = {}
        for player in active_players:
            count = sum(
                1 for m in matches
                if m.get("player1") == player or m.get("player2") == player
            )
            player_counts[player] = count
        top_active = sorted(player_counts.items(), key=lambda x: x[1], reverse=True)[:4]
        st.markdown("**Most Active Players:**")
        for i, (player, count) in enumerate(top_active, 1):
            st.markdown(f"{i}. **{player}**: {count} matches")


# -----------------------------------------------------------------------
# Performance metrics (ELO-based)
# -----------------------------------------------------------------------

def render_performance_metrics(ratings, history, processed_stats, matches, active_players):
    """Advanced performance metrics table + peak performance chart."""
    metrics = []
    for player in active_players:
        pstat = next((s for s in processed_stats if s["Player"] == player), None)
        if not pstat:
            continue
        ph = history.get(player, [])
        if len(ph) < 2:
            continue

        elos = [r for _, r in ph[1:]]
        current = ratings.get(player, 1000)
        peak = max(elos)
        elo_std = np.std(elos) if len(elos) > 1 else 0
        changes = [elos[i] - elos[i - 1] for i in range(1, len(elos))]

        metrics.append({
            "Player": player,
            "Current ELO": round(current, 1),
            "Peak ELO": round(peak, 1),
            "ELO vs Peak": round(current - peak, 1),
            "Consistency": round(max(0, 100 - elo_std), 1),
            "Biggest Gain": f"+{max(changes):.1f}" if changes else "-",
            "Biggest Loss": f"{min(changes):.1f}" if changes else "-",
        })

    if not metrics:
        st.info("Not enough data for performance metrics yet.")
        return

    df = pd.DataFrame(metrics)

    tab1, tab2 = st.tabs(["All Metrics", "Peak Performance"])
    with tab1:
        st.dataframe(df.sort_values("Current ELO", ascending=False), use_container_width=True)
    with tab2:
        peak_df = df[["Player", "Current ELO", "Peak ELO", "ELO vs Peak"]].sort_values("Peak ELO", ascending=False)
        st.dataframe(peak_df, use_container_width=True)

        top10 = peak_df.head(10)
        if len(top10) >= 2:
            fig, ax = plt.subplots(figsize=(10, 6))
            x = np.arange(len(top10))
            w = 0.35
            ax.bar(x - w / 2, top10["Current ELO"], w, label="Current ELO", color="#2196F3", alpha=0.8)
            ax.bar(x + w / 2, top10["Peak ELO"], w, label="Peak ELO", color="#FFD700", alpha=0.8)
            ax.set_xlabel("Player", fontsize=10, fontweight="bold")
            ax.set_ylabel("ELO Rating", fontsize=10, fontweight="bold")
            ax.set_xticks(x)
            ax.set_xticklabels(top10["Player"], rotation=45, ha="right")
            apply_dark_style(fig, ax, title="Current vs Peak ELO (Top 10)")
            apply_dark_legend(ax)
            ax.grid(axis="y", alpha=0.3)
            plt.tight_layout()
            st.pyplot(fig)


# -----------------------------------------------------------------------
# Doubles partnership
# -----------------------------------------------------------------------

def render_doubles_partnership(doubles_matches, doubles_ratings):
    """Best partner and matchup records for doubles."""
    if not doubles_matches:
        st.info("No doubles matches yet.")
        return

    partner_stats = defaultdict(lambda: defaultdict(lambda: {"matches": 0, "wins": 0}))
    matchup_stats = defaultdict(lambda: defaultdict(lambda: {"wins": 0, "losses": 0, "total": 0}))

    for match in doubles_matches:
        t1, t2 = match["team1"], match["team2"]
        s1, s2 = match["score1"], match["score2"]
        wt = t1 if s1 > s2 else t2

        for team in [t1, t2]:
            for p1 in team:
                for p2 in team:
                    if p1 != p2:
                        partner_stats[p1][p2]["matches"] += 1
                        if team == wt:
                            partner_stats[p1][p2]["wins"] += 1

        t1k = " & ".join(sorted(t1))
        t2k = " & ".join(sorted(t2))
        if s1 > s2:
            matchup_stats[t1k][t2k]["wins"] += 1
            matchup_stats[t1k][t2k]["total"] += 1
            matchup_stats[t2k][t1k]["losses"] += 1
            matchup_stats[t2k][t1k]["total"] += 1
        else:
            matchup_stats[t2k][t1k]["wins"] += 1
            matchup_stats[t2k][t1k]["total"] += 1
            matchup_stats[t1k][t2k]["losses"] += 1
            matchup_stats[t1k][t2k]["total"] += 1

    # Best partner table
    st.subheader("Best Doubles Partner (by Win %)")
    bp_data = []
    for player, partners in partner_stats.items():
        best = max(partners.items(), key=lambda x: x[1]["wins"], default=(None, {"wins": 0, "matches": 0}))
        bp, bstats = best
        total = bstats["matches"]
        wins = bstats["wins"]
        bp_data.append({
            "Player": player,
            "Best Partner": bp,
            "Matches Together": total,
            "Wins Together": wins,
            "Win %": round(100 * wins / total, 1) if total > 0 else 0,
        })
    st.dataframe(pd.DataFrame(bp_data).sort_values("Win %", ascending=False), use_container_width=True)

    # Matchup table
    st.subheader("Doubles Matchup Records")
    mu_data = []
    for t1, opponents in matchup_stats.items():
        for t2, mstats in opponents.items():
            if t1 < t2:
                mu_data.append({
                    "Team 1": t1, "Team 2": t2,
                    "Wins": mstats["wins"], "Losses": mstats["losses"],
                    "Total Matches": mstats["total"],
                    "Win %": round(100 * mstats["wins"] / mstats["total"], 1) if mstats["total"] > 0 else 0,
                })
    if mu_data:
        st.dataframe(pd.DataFrame(mu_data).sort_values("Total Matches", ascending=False), use_container_width=True)


# -----------------------------------------------------------------------
# Main analytics page renderer
# -----------------------------------------------------------------------

def render_analytics(sport_data, sport_config):
    """Main analytics page."""
    match_types = sport_config.get("match_types", {})

    for mtype in match_types:
        if mtype not in sport_data:
            continue

        ratings, history, matches = sport_data[mtype]
        label = mtype.replace("_", " ").title()

        if mtype == "singles":
            active = set()
            for m in matches:
                active.update([m["player1"], m["player2"]])

            stats = compute_singles_stats(matches, active)

            st.header(f"📊 {label} Player Stats")
            render_player_stats(stats)

            if len(active) >= 2:
                st.header(f"🔬 {label} Player Comparison")
                render_player_comparison(
                    ratings, stats, matches, active,
                    key_prefix=f"{sport_config['id']}_{mtype}",
                )

                st.header(f"🎯 {label} ELO Distribution")
                render_elo_distribution(ratings, active)

                st.header(f"🏅 Top Players Progression")
                render_top_players_progression(ratings, history, active)

            st.header(f"🔥 {label} Recent Form")
            render_recent_form(matches, active)

            st.header(f"⚔️ {label} Match Competitiveness")
            render_match_competitiveness(matches)

            st.header(f"📅 {label} Activity")
            render_activity(matches, active)

            st.header(f"🎯 {label} Performance Metrics")
            render_performance_metrics(ratings, history, stats, matches, active)

        elif mtype == "doubles":
            active = set()
            for m in matches:
                active.update(m["team1"] + m["team2"])

            stats = compute_doubles_stats(matches, active)

            st.header(f"📊 {label} Player Stats")
            render_player_stats(stats)

            st.header(f"🤝 {label} Partnership & Matchups")
            render_doubles_partnership(matches, ratings)

        elif mtype == "ffa":
            st.header(f"📊 {label} Stats")
            st.info("Free-for-all analytics coming soon.")
