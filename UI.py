"""
NHL Analytics Hub — Streamlit Dashboard
Multi-page app over the MySQL database built by the NHL_ANALYTICS notebooks.
"""

import pandas as pd
import pymysql
import streamlit as st
from streamlit_option_menu import option_menu

st.set_page_config(page_title="NHL Analytics Hub", page_icon="🏒", layout="wide")


# Define the database configuration dictionary
DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': 'sabi3601',
    'database': 'nhl_analytics'
}

# Data access helpers

@st.cache_resource
def get_connection():
    return pymysql.connect(**DB_CONFIG, cursorclass=pymysql.cursors.DictCursor, autocommit=True)


def run_query(sql: str, params: tuple = ()) -> pd.DataFrame:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
        return pd.DataFrame(rows)
    except Exception as e:
        st.error(f"Query failed: {e}")
        return pd.DataFrame()


@st.cache_data(ttl=300)
def load_teams():
    return run_query("SELECT * FROM teams ORDER BY team_name")

# Sidebar navigation

with st.sidebar:
    st.markdown("### 🏒 NHL Analytics Hub")
    page = option_menu(
        menu_title=None,
        options=["Home", "Standings", "Team Info", "Player Search",
                 "Game Results", "Leaderboards", "SQL Query"],
        icons=["house", "list-ol", "shield", "search",
               "calendar-event", "bar-chart", "code-slash"],
        default_index=0,
    )

try:
    get_connection()
except Exception as e:
    st.error(
        f"Could not connect to MySQL database `nhl_analytics`: {e}\n\n"
        "Run the notebooks in `NHL_ANALYTICS/` first to create and populate the database, "
        "and check the host/user/password in `DB_CONFIG` at the top of this file."
    )
    st.stop()


# HOME

if page == "Home":
    st.title("🏒 NHL Analytics Hub")
    st.caption("API-driven hockey data pipeline with SQL analysis and Streamlit dashboard")

    teams_count = run_query("SELECT COUNT(*) AS n FROM teams")["n"][0]
    players_count = run_query("SELECT COUNT(*) AS n FROM players")["n"][0]
    games_count = run_query("SELECT COUNT(*) AS n FROM games")["n"][0]

    #Final goals
    goals_total = run_query(
        "SELECT SUM(home_score + away_score) AS n FROM games WHERE game_state = 'OFF'"
    )["n"][0] or 0

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        with st.container(border=True):
            st.metric("Total Teams", teams_count)
    with c2:
        with st.container(border=True):
            st.metric("Total Players", players_count)
    with c3:
        with st.container(border=True):
            st.metric("Total Games", games_count)
    with c4:
        with st.container(border=True):

            #Final goals
            st.metric("Total Goals Scored", int(goals_total))

    st.divider()

    top_scorer = run_query(
        """SELECT CONCAT(p.first_name, ' ', p.last_name) AS name, sk.points
           FROM skater_season_stats sk JOIN players p ON sk.player_id = p.player_id
           ORDER BY sk.points DESC LIMIT 1"""
    )
    best_goalie = run_query(
        """SELECT CONCAT(p.first_name, ' ', p.last_name) AS name, g.save_pct
           FROM goalie_season_stats g JOIN players p ON g.player_id = p.player_id
           WHERE g.games_played >= 10
           ORDER BY g.save_pct DESC LIMIT 1"""
    )
    league_leader = run_query(
        """SELECT t.team_name AS name, s.points
           FROM standings s JOIN teams t ON s.team_id = t.team_id
           ORDER BY s.points DESC LIMIT 1"""
    )

    c1, c2, c3 = st.columns(3)
    with c1:
        with st.container(border=True):
            st.markdown("⭐ **Top Scorer**")
            if not top_scorer.empty:
                st.subheader(top_scorer["name"][0])
                st.caption(f"{top_scorer['points'][0]} pts")
    with c2:
        with st.container(border=True):
            st.markdown("🥅 **Best Save %**")
            if not best_goalie.empty:
                st.subheader(best_goalie["name"][0])
                st.caption(f"{best_goalie['save_pct'][0]:.3f}")
    with c3:
        with st.container(border=True):
            st.markdown("🏆 **League Leader**")
            if not league_leader.empty:
                st.subheader(league_leader["name"][0])
                st.caption(f"{league_leader['points'][0]} pts")

    st.divider()
    st.subheader("Points by Team")
    chart_df = run_query(
        """SELECT t.team_name, s.points
           FROM standings s JOIN teams t ON s.team_id = t.team_id
           ORDER BY s.points DESC"""
    )
    if not chart_df.empty:
        st.bar_chart(chart_df.set_index("team_name"))


    # ANALYTICAL DASHBOARD 2 — League Structure (Conferences & Divisions)
    # Card-grid design instead of a chart: one card per division, grouped
    # into conference columns, with the division's teams listed inside.

    st.divider()
    st.subheader("🌍 League Structure: Conferences & Divisions")
    st.caption("Every division's teams, grouped by conference.")

    structure = run_query(
        """SELECT conference_name, division_name, team_name
           FROM teams
           ORDER BY conference_name, division_name, team_name"""
    )
    if structure.empty:
        st.info("No teams loaded yet.")
    else:
        conferences = [c for c in structure["conference_name"].dropna().unique()]
        conf_cols = st.columns(len(conferences)) if conferences else []
        for col, conf in zip(conf_cols, conferences):
            with col:
                st.markdown(f"#### {conf}")
                conf_df = structure[structure["conference_name"] == conf]
                for division in conf_df["division_name"].dropna().unique():
                    div_teams = conf_df[conf_df["division_name"] == division]["team_name"].tolist()
                    with st.container(border=True):
                        st.markdown(f"**{division}** &nbsp;·&nbsp; {len(div_teams)} teams")
                        st.caption(", ".join(div_teams))

    # ANALYTICAL DASHBOARD 3 — Tallest & Shortest Players
    # Podium-card design instead of a chart: headshot + height/weight
    # cards for the top 3 tallest and top 3 shortest skaters/goalies.

    st.divider()
    st.subheader("📏 Tallest & Shortest Players")
    st.caption("Player size extremes across the league, with the league average for context.")

    heights = run_query(
        """SELECT first_name, last_name, position, headshot_url, height_cm, weight_kg
           FROM players
           WHERE height_cm IS NOT NULL
           ORDER BY height_cm DESC"""
    )
    if heights.empty:
        st.info("No player height/weight data loaded yet.")
    else:
        avg_height = heights["height_cm"].mean()
        avg_weight = heights["weight_kg"].mean()

        m1, m2, m3 = st.columns(3)
        m1.metric("Tallest", f"{heights.iloc[0]['height_cm']:.0f} cm", heights.iloc[0]["last_name"])
        m2.metric("League Average", f"{avg_height:.0f} cm", f"{avg_weight:.0f} kg avg")
        m3.metric("Shortest", f"{heights.iloc[-1]['height_cm']:.0f} cm", heights.iloc[-1]["last_name"])

        st.markdown("**ᄉ Top 3 Tallest**")
        tall_cols = st.columns(3)
        for col, (_, row) in zip(tall_cols, heights.head(3).iterrows()):
            with col:
                with st.container(border=True):
                    if row["headshot_url"]:
                        st.image(row["headshot_url"], width=100)
                    st.markdown(f"**{row['first_name']} {row['last_name']}**")
                    st.caption(f"{row['position']}  {row['height_cm']:.0f} cm  {row['weight_kg']:.0f} kg")

        st.markdown("**ᄒ Top 3 Shortest**")
        short_cols = st.columns(3)
        for col, (_, row) in zip(short_cols, heights.tail(3).iloc[::-1].iterrows()):
            with col:
                with st.container(border=True):
                    if row["headshot_url"]:
                        st.image(row["headshot_url"], width=100)
                    st.markdown(f"**{row['first_name']} {row['last_name']}**")
                    st.caption(f"{row['position']}  {row['height_cm']:.0f} cm  {row['weight_kg']:.0f} kg")


# STANDINGS

elif page == "Standings":
    st.title("Standings")

    conferences = ["All"] + sorted(
        c for c in load_teams()["conference_name"].dropna().unique()
    )
    conf_filter = st.selectbox("Conference", conferences)

    sql = """
        SELECT t.logo_url AS Logo, t.team_name AS name, t.conference_name AS conference,
               t.division_name AS division, s.wins, s.losses, s.points,
               s.goals_for, s.goals_against
        FROM standings s
        JOIN teams t ON s.team_id = t.team_id
    """
    params = ()
    if conf_filter != "All":
        sql += " WHERE t.conference_name = %s"
        params = (conf_filter,)
    sql += " ORDER BY s.points DESC"

    df = run_query(sql, params)
    if df.empty:
        st.info("No standings data found.")
    else:
        st.dataframe(
            df,
            column_config={"Logo": st.column_config.ImageColumn("Logo", width="small")},
            use_container_width=True,
            hide_index=True,
        )


# TEAM INFO

elif page == "Team Info":
    st.title("Team Info")

    teams_df = load_teams()
    if teams_df.empty:
        st.info("No teams loaded yet.")
    else:
        team_name = st.selectbox("Select Team", teams_df["team_name"])
        team_row = teams_df[teams_df["team_name"] == team_name].iloc[0]

        c1, c2 = st.columns([1, 3])
        with c1:
            if team_row["logo_url"]:
                st.image(team_row["logo_url"], width=150)
        with c2:
            st.subheader(team_row["team_name"])
            st.write(f"**Conference:** {team_row['conference_name']}")
            st.write(f"**Division:** {team_row['division_name']}")

        st.divider()
        st.subheader("Team Roster")
        roster = run_query(
            """SELECT first_name, last_name, position, jersey_number
               FROM players WHERE team_id = %s ORDER BY position, last_name""",
            (int(team_row["team_id"]),),
        )
        if roster.empty:
            st.info("No roster data found for this team.")
        else:
            for pos_label, pos_codes in [
                ("Forwards", ["C", "LW", "RW"]),
                ("Defensemen", ["D"]),
                ("Goalies", ["G"]),
            ]:
                subset = roster[roster["position"].isin(pos_codes)]
                if not subset.empty:
                    st.markdown(f"**{pos_label}**")
                    st.dataframe(subset, use_container_width=True, hide_index=True)


# PLAYER SEARCH

elif page == "Player Search":
    st.title("Player Search")

    name_query = st.text_input("Enter player name")

    players_df = run_query(
        """SELECT player_id, first_name, last_name, headshot_url, position
           FROM players ORDER BY last_name"""
    )
    if name_query:
        mask = (
            players_df["first_name"].str.contains(name_query, case=False, na=False)
            | players_df["last_name"].str.contains(name_query, case=False, na=False)
        )
        players_df = players_df[mask]

    if players_df.empty:
        st.info("No players match that search.")
    else:
        players_df["display_name"] = players_df["first_name"] + " " + players_df["last_name"]
        selected = st.selectbox("Select Player", players_df["display_name"])
        prow = players_df[players_df["display_name"] == selected].iloc[0]

        c1, c2 = st.columns([1, 3])
        with c1:
            if prow["headshot_url"]:
                st.image(prow["headshot_url"], width=150)
        with c2:
            st.subheader(selected)
            st.caption(f"Position: {prow['position']}")

        stats = run_query(
            "SELECT * FROM skater_season_stats WHERE player_id = %s",
            (int(prow["player_id"]),),
        )
        if stats.empty:
            stats = run_query(
                "SELECT * FROM goalie_season_stats WHERE player_id = %s",
                (int(prow["player_id"]),),
            )
            if not stats.empty:
                s = stats.iloc[0]
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Wins", int(s["wins"]) if s["wins" ] is not None else 0)
                c2.metric("Save %", f"{s['save_pct']:.3f}" if s["save_pct"] else "—")
                c3.metric("GAA", f"{s['goals_against_avg']:.2f}" if s["goals_against_avg"] else "—")
                c4.metric("Shutouts", int(s["shutouts"]) if s["shutouts"] else 0)
        else:
            s = stats.iloc[0]
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Goals", int(s["goals"]) if s["goals"] is not None else 0)
            c2.metric("Assists", int(s["assists"]) if s["assists"] is not None else 0)
            c3.metric("Points", int(s["points"]) if s["points"] is not None else 0)
            c4.metric("Games Played", int(s["games_played"]) if s["games_played"] is not None else 0)


# GAME RESULTS

elif page == "Game Results":
    st.title("Game Results")

    state_choice = st.radio("Game State", ["All", "OFF (Final)", "FUT (Upcoming)", "LIVE"], horizontal=True)
    date_filter = st.date_input("Filter by date", value=None)

    sql = """
        SELECT g.game_date, ht.team_name AS home_team, at.team_name AS away_team,
               g.home_score, g.away_score, g.venue_name, g.game_state
        FROM games g
        JOIN teams ht ON g.home_team_id = ht.team_id
        JOIN teams at ON g.away_team_id = at.team_id
        WHERE 1=1
    """
    params = []
    if state_choice != "All":
        code = state_choice.split()[0]
        sql += " AND g.game_state = %s"
        params.append(code)
    if date_filter:
        sql += " AND g.game_date = %s"
        params.append(str(date_filter))
    sql += " ORDER BY g.game_date DESC"

    df = run_query(sql, tuple(params))
    if df.empty:
        st.info("No games match these filters.")
    else:
        st.dataframe(df, use_container_width=True, hide_index=True)


# LEADERBOARDS

elif page == "Leaderboards":
    st.title("Leaderboards")

    tabs = st.tabs(["Goals", "Assists", "Penalty Minutes", "Save %", "Team Wins"])

    with tabs[0]:
        df = run_query(
            """SELECT p.first_name, p.last_name, sk.goals
               FROM skater_season_stats sk JOIN players p ON sk.player_id = p.player_id
               ORDER BY sk.goals DESC LIMIT 10"""
        )
        st.dataframe(df, use_container_width=True, hide_index=True)

    with tabs[1]:
        df = run_query(
            """SELECT p.first_name, p.last_name, sk.assists
               FROM skater_season_stats sk JOIN players p ON sk.player_id = p.player_id
               ORDER BY sk.assists DESC LIMIT 10"""
        )
        st.dataframe(df, use_container_width=True, hide_index=True)

    with tabs[2]:
        df = run_query(
            """SELECT p.first_name, p.last_name, sk.penalty_min
               FROM skater_season_stats sk JOIN players p ON sk.player_id = p.player_id
               ORDER BY sk.penalty_min DESC LIMIT 10"""
        )
        st.dataframe(df, use_container_width=True, hide_index=True)

    with tabs[3]:
        df = run_query(
            """SELECT p.first_name, p.last_name, g.save_pct
               FROM goalie_season_stats g JOIN players p ON g.player_id = p.player_id
               WHERE g.games_played >= 10
               ORDER BY g.save_pct DESC LIMIT 10"""
        )
        st.dataframe(df, use_container_width=True, hide_index=True)

    with tabs[4]:
        df = run_query(
            """SELECT t.team_name, s.wins
               FROM standings s JOIN teams t ON s.team_id = t.team_id
               ORDER BY s.wins DESC LIMIT 10"""
        )
        st.dataframe(df, use_container_width=True, hide_index=True)


# SQL QUERY EXPLORER

elif page == "SQL Query":
    st.title("ᄃ SQL Query Explorer")
    st.caption("Pick a ready-made query below, or choose Custom Query to write your own.")

    PREBUILT_QUERIES = {
       "1. Which team has scored the most total goals this season?-(aggregation + ORDER BY)": """SELECT t.team_name, s.goals_for
FROM standings s
JOIN teams t ON s.team_id = t.team_id
ORDER BY s.goals_for DESC
LIMIT 1;""",
        "2. Who are the top 5 point scorers across the entire league?-(JOIN + ORDER BY)": """SELECT p.first_name, p.last_name, t.team_name, sk.points
FROM skater_season_stats sk
JOIN players p ON sk.player_id = p.player_id
JOIN teams t ON sk.team_id = t.team_id
ORDER BY sk.points DESC
LIMIT 5;""",
        "3. Which players have scored more than 20 goals AND recorded more than 30 assists in the season?-(WHERE with multiple conditions)": """SELECT p.first_name, p.last_name, sk.goals, sk.assists, sk.points
FROM skater_season_stats sk
JOIN players p ON sk.player_id = p.player_id
WHERE sk.goals > 20 AND sk.assists > 30
ORDER BY sk.points DESC;""",
        "4. Which teams have a season points total above the league average?-(subquery)": """SELECT t.team_name, s.points
FROM standings s
JOIN teams t ON s.team_id = t.team_id
WHERE s.points > (SELECT AVG(points) FROM standings)
ORDER BY s.points DESC;""",
        "5. Which divisions have an average team points total above 90?-(GROUP BY + HAVING)": """SELECT t.division_name, ROUND(AVG(s.points), 1) AS avg_points
FROM standings s
JOIN teams t ON s.team_id = t.team_id
GROUP BY t.division_name
HAVING AVG(s.points) > 90
ORDER BY avg_points DESC;""",
        "6. Who are the top 5 goalies by save percentage (minimum 20 games played)?-(WHERE + ORDER BY, guards against small sample sizes)": """SELECT p.first_name, p.last_name, t.team_name, g.save_pct, g.games_played
FROM goalie_season_stats g
JOIN players p ON g.player_id = p.player_id
JOIN teams t ON g.team_id = t.team_id
WHERE g.games_played >= 20
ORDER BY g.save_pct DESC
LIMIT 5;""",
        " 7. Which teams have the most regulation wins this season?-(aggregation + ORDER BY)": """SELECT t.team_name, s.wins
FROM standings s
JOIN teams t ON s.team_id = t.team_id
ORDER BY s.wins DESC
LIMIT 10;""",
        "8. What is each team's win percentage, ranked highest to lowest?-(derived metric via calculation)": """SELECT t.team_name,
       s.wins,
       s.games_played,
       ROUND(1.0 * s.wins / NULLIF(s.games_played, 0), 3) AS win_pct
FROM standings s
JOIN teams t ON s.team_id = t.team_id
ORDER BY win_pct DESC;""",
         "9. Who leads the league in penalty minutes among skaters?-(aggregation + ORDER BY)": """SELECT p.first_name, p.last_name, t.team_name, sk.penalty_min
FROM skater_season_stats sk
JOIN players p ON sk.player_id = p.player_id
JOIN teams t ON sk.team_id = t.team_id
ORDER BY sk.penalty_min DESC
LIMIT 10;""",
          "10. For each team, who is their leading scorer (top point-getter)?-(correlated subquery / per-group max)": """SELECT t.team_name,
       p.first_name,
       p.last_name,
       sk.points
FROM skater_season_stats sk
JOIN players p ON sk.player_id = p.player_id
JOIN teams t ON sk.team_id = t.team_id
WHERE sk.points = (
    SELECT MAX(sk2.points)
    FROM skater_season_stats sk2
    WHERE sk2.team_id = sk.team_id) ORDER BY sk.points DESC;""",
          "11. How many shutouts has each goalie recorded, and what's their GAA?-(filter + ORDER BY)": """SELECT p.first_name, p.last_name, t.team_name, g.shutouts, g.goals_against_avg
FROM goalie_season_stats g
JOIN players p ON g.player_id = p.player_id
JOIN teams t ON g.team_id = t.team_id
WHERE g.shutouts > 0
ORDER BY g.shutouts DESC, g.goals_against_avg ASC;""",
          "12. What are the 10 highest-scoring completed games this season?-(aggregation across two columns + ORDER BY)": """SELECT g.game_date,
       ht.team_name AS home_team,
       g.home_score,
       at.team_name AS away_team,
       g.away_score,
       (g.home_score + g.away_score) AS total_goals
FROM games g
JOIN teams ht ON g.home_team_id = ht.team_id
JOIN teams at ON g.away_team_id = at.team_id
WHERE g.game_state = 'OFF'
ORDER BY total_goals DESC
LIMIT 10;""",
          "13. Which conference has more total standings points accumulated?-(GROUP BY aggregation)": """SELECT t.conference_name, SUM(s.points) AS total_points
FROM standings s
JOIN teams t ON s.team_id = t.team_id
GROUP BY t.conference_name
ORDER BY total_points DESC;""",
          "14. Which players were born in Canada?-(simple WHERE filter)": """SELECT first_name, last_name, position, birth_country
FROM players
WHERE birth_country = 'CAN'
ORDER BY last_name;""",
          "15. What are all the NHL teams and their conferences/divisions?-(simple Order By Filter)": """SELECT team_name, conference_name, division_name
FROM teams ORDER BY conference_name, division_name, team_name;""",

        # "Custom Query": "",
    }

    choice = st.selectbox("Choose a query", list(PREBUILT_QUERIES.keys()))
    sql_text = st.text_area("SQL Query", value=PREBUILT_QUERIES[choice], height=150)

    if st.button("▶ Run Query"):
        if not sql_text.strip():
            st.warning("Enter a SQL query first.")
        else:
            df = run_query(sql_text)
            if not df.empty or sql_text.strip().lower().startswith("select"):
                st.success(f"{len(df)} rows returned")
                st.dataframe(df, use_container_width=True, hide_index=True)
            else:
                st.info("Query ran with no rows returned.")