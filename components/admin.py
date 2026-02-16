"""Admin page: login gate and player registration panel."""

import streamlit as st
from elo import (
    add_player,
    load_players,
    load_sports_config,
    add_singles_match,
    add_doubles_match,
)

ADMIN_USER = "atf123"
ADMIN_PASS = "1771"


def render_admin_login():
    """Show the admin login form. Sets session state on success."""
    st.header("Admin Login")

    with st.form("admin_login_form"):
        user = st.text_input("Login ID")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Log in")

    if submitted:
        if user == ADMIN_USER and password == ADMIN_PASS:
            st.session_state["admin_authenticated"] = True
            st.rerun()
        else:
            st.error("Invalid credentials.")


def render_admin_panel():
    """Authenticated admin UI: register players."""
    st.header("Admin Panel")
    st.caption("(All players start at 1000 Elo)")

    if st.button("Log out", key="admin_logout"):
        st.session_state["admin_authenticated"] = False
        st.rerun()

    st.subheader("Register New Player")

    with st.form("register_player_form"):
        name = st.text_input("Player name")
        submitted = st.form_submit_button("Register")

    if submitted:
        name = name.strip()
        if not name:
            st.warning("Player name cannot be empty.")
        elif add_player(name):
            st.success(f"**{name}** has been registered.")
        else:
            st.warning(f"**{name}** is already registered.")

    st.subheader("Current Players")
    players = sorted(load_players())
    if players:
        for p in players:
            st.write(f"- {p}")
    else:
        st.info("No players registered yet.")

    st.divider()

    # ------------------------------------------------------------------
    # Match score entry
    # ------------------------------------------------------------------
    render_match_entry(players)


def render_match_entry(players):
    """Render the match score entry form."""
    st.subheader("Record Match Score")

    if len(players) < 2:
        st.info("Register at least 2 players before recording matches.")
        return

    sports = load_sports_config()
    if not sports:
        st.warning("No sports configured.")
        return

    sport_labels = {s["id"]: f"{s['emoji']} {s['name']}" for s in sports}
    sport_id = st.selectbox(
        "Sport",
        options=[s["id"] for s in sports],
        format_func=lambda sid: sport_labels[sid],
        key="match_sport",
    )

    sport = next(s for s in sports if s["id"] == sport_id)
    match_types = list(sport.get("match_types", {}).keys())

    if not match_types:
        st.warning("This sport has no match types configured.")
        return

    match_type = st.selectbox(
        "Match type",
        options=match_types,
        format_func=lambda t: t.capitalize(),
        key="match_type",
    )

    data_file = sport["match_types"][match_type]

    if match_type == "singles":
        _render_singles_form(players, data_file, sport["name"])
    elif match_type == "doubles":
        _render_doubles_form(players, data_file, sport["name"])
    else:
        st.info(f"Score entry for **{match_type}** matches is not yet supported.")


def _render_singles_form(players, data_file, sport_name):
    """Form for recording a singles match."""
    with st.form("singles_match_form"):
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Player 1**")
            p1 = st.selectbox("Player 1", options=players, key="singles_p1")
            s1 = st.number_input("Score", min_value=0, step=1, key="singles_s1")
        with col2:
            st.markdown("**Player 2**")
            p2 = st.selectbox("Player 2", options=players, key="singles_p2")
            s2 = st.number_input("Score", min_value=0, step=1, key="singles_s2")

        submitted = st.form_submit_button("Submit Match")

    if submitted:
        err = add_singles_match(data_file, p1, p2, int(s1), int(s2))
        if err:
            st.error(err)
        else:
            st.success(
                f"Recorded {sport_name} singles: **{p1}** {int(s1)} – {int(s2)} **{p2}**"
            )


def _render_doubles_form(players, data_file, sport_name):
    """Form for recording a doubles match."""
    with st.form("doubles_match_form"):
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Team 1**")
            t1_p1 = st.selectbox("Team 1 – Player A", options=players, key="doubles_t1p1")
            t1_p2 = st.selectbox("Team 1 – Player B", options=players, key="doubles_t1p2")
            s1 = st.number_input("Team 1 Score", min_value=0, step=1, key="doubles_s1")
        with col2:
            st.markdown("**Team 2**")
            t2_p1 = st.selectbox("Team 2 – Player A", options=players, key="doubles_t2p1")
            t2_p2 = st.selectbox("Team 2 – Player B", options=players, key="doubles_t2p2")
            s2 = st.number_input("Team 2 Score", min_value=0, step=1, key="doubles_s2")

        submitted = st.form_submit_button("Submit Match")

    if submitted:
        team1 = [t1_p1, t1_p2]
        team2 = [t2_p1, t2_p2]

        # Validate: no duplicate players across or within teams
        all_selected = team1 + team2
        if len(set(all_selected)) != 4:
            st.error("All four players must be different.")
        else:
            err = add_doubles_match(data_file, team1, team2, int(s1), int(s2))
            if err:
                st.error(err)
            else:
                st.success(
                    f"Recorded {sport_name} doubles: "
                    f"**{t1_p1} & {t1_p2}** {int(s1)} – {int(s2)} **{t2_p1} & {t2_p2}**"
                )


def render_admin_page():
    """Entry point: show login or panel depending on auth state."""
    if st.session_state.get("admin_authenticated"):
        render_admin_panel()
    else:
        render_admin_login()
