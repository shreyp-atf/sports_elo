"""Admin page: login gate, player registration, and match score entry."""

import streamlit as st
from data_utils import (
    add_player,
    load_players,
    load_sports_config,
    add_singles_match,
    add_doubles_match,
)


def render_admin_login():
    """Show the admin login form. Sets session state on success."""
    st.header("Admin Login")

    with st.form("admin_login_form"):
        user = st.text_input("Login ID")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Log in")

    if submitted:
        if user == st.secrets["admin_user"] and password == st.secrets["admin_pass"]:
            st.session_state["admin_authenticated"] = True
            st.rerun()
        else:
            st.error("Invalid credentials.")


def render_admin_panel():
    """Authenticated admin UI: register players and record matches."""
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
        else:
            try:
                new_id = add_player(name)
                st.success(f"**{name}** has been registered (ID {new_id}).")
            except Exception:
                st.error("Failed to register player. Please try again.")

    st.subheader("Current Players")
    player_map = load_players()
    if player_map:
        for pid, pname in sorted(player_map.items(), key=lambda x: x[1]):
            st.write(f"- {pname} (#{pid})")
    else:
        st.info("No players registered yet.")

    st.divider()

    # ------------------------------------------------------------------
    # Match score entry
    # ------------------------------------------------------------------
    render_match_entry(player_map)


def render_match_entry(player_map):
    """Render the match score entry form."""
    st.subheader("Record Match Score")

    if len(player_map) < 2:
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
    match_types = sport.get("match_types", [])

    if not match_types:
        st.warning("This sport has no match types configured.")
        return

    match_type = st.selectbox(
        "Match type",
        options=match_types,
        format_func=lambda t: t.capitalize(),
        key="match_type",
    )

    if match_type == "singles":
        _render_singles_form(player_map, sport_id, sport["name"])
    elif match_type == "doubles":
        _render_doubles_form(player_map, sport_id, sport["name"])
    else:
        st.info(f"Score entry for **{match_type}** matches is not yet supported.")


def _player_options(player_map):
    """Return sorted (id, name) pairs for select-box options."""
    return sorted(player_map.items(), key=lambda x: x[1])


def _render_singles_form(player_map, sport_id, sport_name):
    """Form for recording a singles match."""
    opts = _player_options(player_map)
    player_ids = [pid for pid, _ in opts]
    player_labels = {pid: name for pid, name in opts}

    with st.form("singles_match_form"):
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Player 1**")
            p1 = st.selectbox(
                "Player 1", options=player_ids,
                format_func=lambda pid: player_labels[pid],
                key="singles_p1",
            )
            s1 = st.number_input("Score", min_value=0, step=1, key="singles_s1")
        with col2:
            st.markdown("**Player 2**")
            p2 = st.selectbox(
                "Player 2", options=player_ids,
                format_func=lambda pid: player_labels[pid],
                key="singles_p2",
            )
            s2 = st.number_input("Score", min_value=0, step=1, key="singles_s2")

        submitted = st.form_submit_button("Submit Match")

    if submitted:
        try:
            err = add_singles_match(sport_id, p1, p2, int(s1), int(s2))
            if err:
                st.error(err)
            else:
                st.success(
                    f"Recorded {sport_name} singles: "
                    f"**{player_labels[p1]}** {int(s1)} – {int(s2)} **{player_labels[p2]}**"
                )
        except Exception:
            st.error("Failed to record match. Please try again.")


def _render_doubles_form(player_map, sport_id, sport_name):
    """Form for recording a doubles match."""
    opts = _player_options(player_map)
    player_ids = [pid for pid, _ in opts]
    player_labels = {pid: name for pid, name in opts}

    with st.form("doubles_match_form"):
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Team 1**")
            t1_p1 = st.selectbox(
                "Team 1 – Player A", options=player_ids,
                format_func=lambda pid: player_labels[pid],
                key="doubles_t1p1",
            )
            t1_p2 = st.selectbox(
                "Team 1 – Player B", options=player_ids,
                format_func=lambda pid: player_labels[pid],
                key="doubles_t1p2",
            )
            s1 = st.number_input("Team 1 Score", min_value=0, step=1, key="doubles_s1")
        with col2:
            st.markdown("**Team 2**")
            t2_p1 = st.selectbox(
                "Team 2 – Player A", options=player_ids,
                format_func=lambda pid: player_labels[pid],
                key="doubles_t2p1",
            )
            t2_p2 = st.selectbox(
                "Team 2 – Player B", options=player_ids,
                format_func=lambda pid: player_labels[pid],
                key="doubles_t2p2",
            )
            s2 = st.number_input("Team 2 Score", min_value=0, step=1, key="doubles_s2")

        submitted = st.form_submit_button("Submit Match")

    if submitted:
        all_selected = [t1_p1, t1_p2, t2_p1, t2_p2]
        if len(set(all_selected)) != 4:
            st.error("All four players must be different.")
        else:
            try:
                err = add_doubles_match(
                    sport_id, t1_p1, t1_p2, t2_p1, t2_p2, int(s1), int(s2)
                )
                if err:
                    st.error(err)
                else:
                    st.success(
                        f"Recorded {sport_name} doubles: "
                        f"**{player_labels[t1_p1]} & {player_labels[t1_p2]}** "
                        f"{int(s1)} – {int(s2)} "
                        f"**{player_labels[t2_p1]} & {player_labels[t2_p2]}**"
                    )
            except Exception:
                st.error("Failed to record match. Please try again.")


def render_admin_page():
    """Entry point: show login or panel depending on auth state."""
    if st.session_state.get("admin_authenticated"):
        render_admin_panel()
    else:
        render_admin_login()
