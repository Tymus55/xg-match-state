"""
Rożnica xG według stanu meczu (Zwycięstwo / Remis / Przegrana)
    for Polonia Bytom vs Pogon Grodzisk Mazowiecki (StatsBomb events).


"""

import pandas as pd

# ---------------------------------------------------------------------------
# 1. Wczytanie CSV
# ---------------------------------------------------------------------------

df = pd.read_csv(
    "Polonia Bytom_Pogo  Grodzisk Mazowiecki_4068759.csv",
    low_memory=False,
)

# Normalizacja nazwy zespołu: "Pogoń" → "Pogon" (nie wymaga zmiany UTF-8)
df["team_name"] = df["team_name"].str.replace("Pogoń", "Pogon", regex=False)

# ---------------------------------------------------------------------------
# Usunięcie duplikatów
# ---------------------------------------------------------------------------
df = df.drop_duplicates(subset=["id"]).copy()

# ---------------------------------------------------------------------------
# Sortowanie chronologiczne
# ---------------------------------------------------------------------------
df = df.sort_values(
    by=["period", "minute", "second", "timestamp"],
    kind="mergesort",  # stable sort
).reset_index(drop=True)

# ---------------------------------------------------------------------------
# 4. Biężacy wynik (wynik przed zdarzenmiem uzyskany przez shift)
# ---------------------------------------------------------------------------
# Goal to strzał zakończony bramką
is_goal = (df["event_type_name"] == "Shot") & (df["outcome_name"] == "Goal")

teams = list(df["team_name"].dropna().unique())
if len(teams) != 2:
    raise ValueError(f"Expected exactly 2 teams, found: {teams}")

# Stable order: Polonia Bytom 1 jeśli występuje
preferred = ["Polonia Bytom"]
teams = [t for t in preferred if t in teams] + [
    t for t in teams if t not in preferred
]
team_a, team_b = teams[0], teams[1]

# Goals flags dla drużyn (0/1) na każdym wierszu
df["goal_team_a"] = (is_goal & (df["team_name"] == team_a)).astype(int)
df["goal_team_b"] = (is_goal & (df["team_name"] == team_b)).astype(int)

# Skumulowane gole *po* zdarzeniu, następnie shift(1) → wynik przed zdarzeniem.
# Sam strzał zakończony golem pozostaje w stanie meczu, który obowiązywał przed nim.
df["score_a"] = df["goal_team_a"].cumsum().shift(1, fill_value=0).astype(int)
df["score_b"] = df["goal_team_b"].cumsum().shift(1, fill_value=0).astype(int)

# ---------------------------------------------------------------------------
# 5. Wynik meczu z perspektywy drużyny, której dotyczy zdarzenie
# ---------------------------------------------------------------------------
STATE_ORDER = ["Zwycięstwo", "Remis", "Przegrana"]

# Jeśli drużyna A wygrywa, drużyna B przegrywa (ten sam wynik)
COMPLEMENT = {
    "Zwycięstwo": "Przegrana",
    "Remis": "Remis",
    "Przegrana": "Zwycięstwo",
}


def match_state(own_score: int, opp_score: int) -> str:
    if own_score > opp_score:
        return "Zwycięstwo"
    if own_score < opp_score:
        return "Przegrana"
    return "Remis"


def match_state_for_row(row: pd.Series) -> str:
    if row["team_name"] == team_a:
        return match_state(row["score_a"], row["score_b"])
    return match_state(row["score_b"], row["score_a"])


df["match_state"] = df.apply(match_state_for_row, axis=1)

# ---------------------------------------------------------------------------
# 6. Zachowanie tylko i wyłącznie strzałów
# ---------------------------------------------------------------------------
shots = df[df["event_type_name"] == "Shot"].copy()
shots["statsbomb_xg"] = pd.to_numeric(shots["statsbomb_xg"], errors="coerce").fillna(
    0.0
)

# ---------------------------------------------------------------------------
# 7. Suma xG według drużyny i wyniku meczu (perspektywa dla obu drużyn oddzielnie)
# ---------------------------------------------------------------------------
xg_by_team_state = (
    shots.groupby(["team_name", "match_state"], as_index=False)["statsbomb_xg"]
    .sum()
    .rename(columns={"statsbomb_xg": "xg_sum"})
)

# Pełna siatka drużyn × stan (brakujące kombinacje → 0)
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
# 8. Różnica xG względem przeciwnika w tych samych okresach stanu meczu
# ---------------------------------------------------------------------------
# Sparuj stan każdej drużyny z komplementarnym (odpowiadającym) stanem przeciwnika:
#   Prowadzenie ↔ Przegrywanie, Remis ↔ Remis, Przegrywanie ↔ Prowadzenie
# W przeciwnym razie stan "Prowadzenie" błędnie porównywałby dwie różne części meczu.


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
                "druzyna": team,
                "stan meczu": state,
                "xG druzyny": fmt_xg(team_xg),
                "xg przeciwnika (ten sam stan)": fmt_xg(opp_xg),
                "roznica xg": fmt_diff(team_xg - opp_xg),
            }
        )

result = pd.DataFrame(rows)

# ---------------------------------------------------------------------------
# 9. Wypisanie czytelnej tabeli Markdown
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


print("Rożnica xG według stanu meczu")
print(f"Match: {team_a} vs {team_b}")
print(
    "Stan meczu = wynik z perspektywy drużyny, której dotyczy zdarzenie. "
    "xG przeciwnika używa komplementarnego stanu (ten sam wynik)."
)
print("Różnica xG = xG drużyny - xG przeciwnika w tym samym stanie meczu.")
print()
print(to_markdown_table(result))
