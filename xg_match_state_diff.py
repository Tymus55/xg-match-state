"""
xG difference by match state (Winning / Drawing / Losing)
for Polonia Bytom vs Pogon Grodzisk Mazowiecki (StatsBomb events).

Important: "same state" means the same scoreline periods on the pitch,
not the same label from each team's own perspective.
When Team A is Winning, the opponent is Losing — those shots happen in
the same time windows and must be paired together.
"""

from pathlib import Path

import pandas as pd

# ---------------------------------------------------------------------------
# 1. Load the CSV
# ---------------------------------------------------------------------------
INPUT_CSV = Path(__file__).resolve().parent / (
    "Polonia Bytom_Pogo  Grodzisk Mazowiecki_4068759.csv"
)

df = pd.read_csv(INPUT_CSV, low_memory=False)

# Normalize team name: "Pogoń" → "Pogon" (ASCII-safe for any console)
df["team_name"] = df["team_name"].str.replace("Pogoń", "Pogon", regex=False)

# ---------------------------------------------------------------------------
# 2. Deduplicate events (StatsBomb 360 duplicates rows via freeze_frame)
# ---------------------------------------------------------------------------
df = df.drop_duplicates(subset=["id"]).copy()

# ---------------------------------------------------------------------------
# 3. Sort chronologically
# ---------------------------------------------------------------------------
df = df.sort_values(
    by=["period", "minute", "second", "timestamp"],
    kind="mergesort",  # stable sort
).reset_index(drop=True)

# ---------------------------------------------------------------------------
# 4. Running score (pre-event score via shift)
# ---------------------------------------------------------------------------
# A goal is a Shot with outcome Goal
is_goal = (df["event_type_name"] == "Shot") & (df["outcome_name"] == "Goal")

teams = list(df["team_name"].dropna().unique())
if len(teams) != 2:
    raise ValueError(f"Expected exactly 2 teams, found: {teams}")

# Stable order: Polonia Bytom first when present
preferred = ["Polonia Bytom"]
teams = [t for t in preferred if t in teams] + [
    t for t in teams if t not in preferred
]
team_a, team_b = teams[0], teams[1]

# Goal flags per team (0/1) on each row
df["goal_team_a"] = (is_goal & (df["team_name"] == team_a)).astype(int)
df["goal_team_b"] = (is_goal & (df["team_name"] == team_b)).astype(int)

# Cumulative goals *after* the event, then shift(1) → score before the event.
# The goal-scoring shot itself stays in the state that was active before it.
df["score_a"] = df["goal_team_a"].cumsum().shift(1, fill_value=0).astype(int)
df["score_b"] = df["goal_team_b"].cumsum().shift(1, fill_value=0).astype(int)

# ---------------------------------------------------------------------------
# 5. Match state from the perspective of the team that owns the event
# ---------------------------------------------------------------------------
STATE_ORDER = ["Winning", "Drawing", "Losing"]

# When Team A is Winning, Team B is Losing (same scoreline / time window)
COMPLEMENT = {"Winning": "Losing", "Drawing": "Drawing", "Losing": "Winning"}


def match_state(own_score: int, opp_score: int) -> str:
    if own_score > opp_score:
        return "Winning"
    if own_score < opp_score:
        return "Losing"
    return "Drawing"


def match_state_for_row(row: pd.Series) -> str:
    if row["team_name"] == team_a:
        return match_state(row["score_a"], row["score_b"])
    return match_state(row["score_b"], row["score_a"])


df["match_state"] = df.apply(match_state_for_row, axis=1)

# ---------------------------------------------------------------------------
# 6. Keep shots only
# ---------------------------------------------------------------------------
shots = df[df["event_type_name"] == "Shot"].copy()
shots["statsbomb_xg"] = pd.to_numeric(shots["statsbomb_xg"], errors="coerce").fillna(
    0.0
)

# ---------------------------------------------------------------------------
# 7. Sum xG by team and match state (each team's own perspective)
# ---------------------------------------------------------------------------
xg_by_team_state = (
    shots.groupby(["team_name", "match_state"], as_index=False)["statsbomb_xg"]
    .sum()
    .rename(columns={"statsbomb_xg": "xg_sum"})
)

# Full team × state grid (missing combos → 0)
full_index = pd.MultiIndex.from_product(
    [teams, STATE_ORDER], names=["team_name", "match_state"]
)
xg_by_team_state = (
    xg_by_team_state.set_index(["team_name", "match_state"])
    .reindex(full_index, fill_value=0.0)
    .reset_index()
)

# Lookup: (team, state) → xG
xg_lookup = xg_by_team_state.set_index(["team_name", "match_state"])["xg_sum"]

# ---------------------------------------------------------------------------
# 8. xG difference vs opponent in the same scoreline periods
# ---------------------------------------------------------------------------
# Pair each team's state with the opponent's complementary state:
#   Winning ↔ Losing, Drawing ↔ Drawing, Losing ↔ Winning
# Otherwise "Winning" would wrongly compare two different halves of the match.


def fmt_xg(value: float) -> str:
    return f"{value:.3f}"


def fmt_diff(value: float) -> str:
    return f"{value:+.3f}"


rows = []
for team in teams:
    opponent = team_b if team == team_a else team_a
    for state in STATE_ORDER:
        team_xg = float(xg_lookup.loc[(team, state)])
        opp_xg = float(xg_lookup.loc[(opponent, COMPLEMENT[state])])
        rows.append(
            {
                "Team": team,
                "Match state": state,
                "Team xG": fmt_xg(team_xg),
                "Opponent xG (same periods)": fmt_xg(opp_xg),
                "xG difference": fmt_diff(team_xg - opp_xg),
            }
        )

result = pd.DataFrame(rows)

# ---------------------------------------------------------------------------
# 9. Print a readable Markdown table
# ---------------------------------------------------------------------------
def to_markdown_table(frame: pd.DataFrame) -> str:
    """Aligned Markdown table (readable in a terminal)."""
    cols = list(frame.columns)
    str_rows = [[str(c) for c in cols]]
    for _, row in frame.iterrows():
        str_rows.append([str(row[c]) for c in cols])

    widths = [max(len(r[i]) for r in str_rows) for i in range(len(cols))]

    def fmt_row(cells: list[str]) -> str:
        return "| " + " | ".join(c.ljust(widths[i]) for i, c in enumerate(cells)) + " |"

    header = fmt_row(str_rows[0])
    sep = "| " + " | ".join("-" * widths[i] for i in range(len(cols))) + " |"
    body = [fmt_row(r) for r in str_rows[1:]]
    return "\n".join([header, sep, *body])


print("xG difference by match state")
print(f"Match: {team_a} vs {team_b}")
print(
    "Match state = score from that team's perspective before the shot. "
    "Opponent xG uses the complementary state (same scoreline periods)."
)
print("xG difference = Team xG - Opponent xG in those periods.")
print()
print(to_markdown_table(result))
