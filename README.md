# xG difference by match state

Answer to task 1 of the internship assignment: calculate the xG (expected goals)
difference for each match state (Winning / Drawing / Losing) for both teams in
Polonia Bytom vs Pogon Grodzisk Mazowiecki, based on StatsBomb event data.

## Run

```bash
pip install -r requirements.txt
python xg_match_state_diff.py
```

## Requirements

| Package | Version | Purpose                     |
| ------- | ------- | --------------------------- |
| Python  | >= 3.9  | runtime                     |
| pandas  | >= 2.0  | data loading & aggregation  |

## Method

1. Load the CSV and deduplicate events by `id` (StatsBomb 360 repeats rows per
   `freeze_frame` player).
2. Sort chronologically by `period`, `minute`, `second`, `timestamp`.
3. Recreate the running score: a goal is `event_type_name == "Shot"` with
   `outcome_name == "Goal"`. Cumulative goals per team are shifted by one event
   (`shift(1)`), so the score changes from the event *after* the goal and the
   goal shot itself is counted in the state that was active before it.
4. Assign `match_state` (Winning / Drawing / Losing) from the perspective of
   the team owning the event.
5. Keep shots only and sum `statsbomb_xg` by team and match state.
6. xG difference = team xG in a state minus opponent xG in the **same scoreline
   periods**. Because the states are relative to each team, the opponent's state
   is the complementary one: Winning <-> Losing, Drawing <-> Drawing. Pairing by
   identical label would compare shots from different parts of the match.

## Result

Match finished 2-2 (Pogon 21', Polonia 27' and 36', Pogon 45' 2nd half).

| Team                      | Match state | Team xG | Opponent xG (same periods) | xG difference |
| ------------------------- | ----------- | ------- | -------------------------- | ------------- |
| Polonia Bytom             | Winning     | 0.066   | 0.017                      | +0.050        |
| Polonia Bytom             | Drawing     | 0.923   | 0.609                      | +0.314        |
| Polonia Bytom             | Losing      | 0.079   | 0.117                      | -0.038        |
| Pogon Grodzisk Mazowiecki | Winning     | 0.117   | 0.079                      | +0.038        |
| Pogon Grodzisk Mazowiecki | Drawing     | 0.609   | 0.923                      | -0.314        |
| Pogon Grodzisk Mazowiecki | Losing      | 0.017   | 0.066                      | -0.050        |

Sanity checks: 34 shots total (Polonia 20, Pogon 14), per-state xG sums match
team totals (1.069 / 0.743), and the numbers were cross-checked by summing xG
directly over the time windows between goals.

## Files

- `xg_match_state_diff.py` - the script
- `Polonia Bytom_Pogo  Grodzisk Mazowiecki_4068759.csv` - input data (StatsBomb)
- `requirements.txt` - dependencies
