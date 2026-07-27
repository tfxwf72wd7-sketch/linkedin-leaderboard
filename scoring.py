"""Daily scoring: each day is out of 8 points.

- 6 timed games (tango, zip, queens, mini-sudoku, crossclimb, patches):
  fastest time wins the point; identical times = 0.5 each.
- pinpoint: lowest (best) ranking wins; identical rank = 0.5 each.
- 8th point: lowest total time across the 6 timed games wins; tie = 0.5 each.

If only one player has a result for a game, that player takes the point.
If neither played a game, no point is awarded for it.
For total time, a player with an incomplete set of timed results can only
win if the other player's set is at least as incomplete (completeness first,
then total).
"""
from __future__ import annotations

TIMED_GAMES = ["tango", "zip", "queens", "mini-sudoku", "crossclimb", "patches"]
RANK_GAME = "pinpoint"
ALL_GAMES = TIMED_GAMES + [RANK_GAME]


def _duel(a, b):
    """Lower value wins. Returns (alex_pts, liz_pts) for one game."""
    if a is None and b is None:
        return 0.0, 0.0
    if a is None:
        return 0.0, 1.0
    if b is None:
        return 1.0, 0.0
    if a < b:
        return 1.0, 0.0
    if b < a:
        return 0.0, 1.0
    return 0.5, 0.5


def score_day(results: dict) -> dict:
    """results: {game: {"alex": {"time": int|None, "rank": int|None},
                        "liz":  {...}}}  (missing game/player = didn't play)
    Returns dict with points breakdown and totals.
    """
    alex_total = 0.0
    liz_total = 0.0
    detail = {}

    for g in TIMED_GAMES:
        a = (results.get(g, {}).get("alex") or {}).get("time")
        b = (results.get(g, {}).get("liz") or {}).get("time")
        pa, pb = _duel(a, b)
        alex_total += pa
        liz_total += pb
        detail[g] = {"alex_time": a, "liz_time": b, "alex_pts": pa, "liz_pts": pb}

    a = (results.get(RANK_GAME, {}).get("alex") or {}).get("rank")
    b = (results.get(RANK_GAME, {}).get("liz") or {}).get("rank")
    pa, pb = _duel(a, b)
    alex_total += pa
    liz_total += pb
    detail[RANK_GAME] = {"alex_rank": a, "liz_rank": b, "alex_pts": pa, "liz_pts": pb}

    # 8th point: total time over the 6 timed games
    a_times = [detail[g]["alex_time"] for g in TIMED_GAMES]
    b_times = [detail[g]["liz_time"] for g in TIMED_GAMES]
    a_missing = sum(t is None for t in a_times)
    b_missing = sum(t is None for t in b_times)
    a_sum = sum(t for t in a_times if t is not None)
    b_sum = sum(t for t in b_times if t is not None)

    if a_missing == 6 and b_missing == 6:
        pa, pb = 0.0, 0.0
    elif a_missing != b_missing:
        # fewer missing games wins the total-time point
        pa, pb = (1.0, 0.0) if a_missing < b_missing else (0.0, 1.0)
    else:
        pa, pb = _duel(a_sum, b_sum)
    alex_total += pa
    liz_total += pb
    detail["total-time"] = {
        "alex_total_seconds": a_sum if a_missing < 6 else None,
        "liz_total_seconds": b_sum if b_missing < 6 else None,
        "alex_missing": a_missing, "liz_missing": b_missing,
        "alex_pts": pa, "liz_pts": pb,
    }

    played_all = all(
        (results.get(g, {}).get(p) or {}).get("time" if g != RANK_GAME else "rank") is not None
        for g in ALL_GAMES for p in ("alex", "liz")
    )
    return {
        "alex": alex_total,
        "liz": liz_total,
        "complete": played_all,
        "detail": detail,
    }
