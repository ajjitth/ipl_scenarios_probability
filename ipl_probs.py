# %%
import datetime
import time
import pandas as pd
import random

# %%
def chop_microseconds(delta):
    return delta - datetime.timedelta(microseconds=delta.microseconds)


def run_ipl_simulation(basePoints_master, matches_master,
                       top_n=4, print_every=500000,
                       track_scenarios=True):
    """
    Same as v2, plus an optional tracking layer that records, for every
    (team, metric) pair, the scenario indices that contributed.

    A scenario is fully described by its index i in [0, 2^n). Bit k of i
    decides the winner of the k-th remaining match: bit = 0 means team1
    of the match string wins, bit = 1 means team2 wins. So given an
    index, we can rebuild the entire scenario without storing it.
    """
    basePoints = basePoints_master.copy()
    matches    = matches_master.copy()

    teams     = sorted(basePoints.keys())
    n         = len(matches)
    combos    = pow(2, n)
    formatStr = "0{}b".format(n)

    print("Pending matches    : {}".format(n))
    print("Possible scenarios : {:,}\n".format(combos))

    confirmed  = {t: 0   for t in teams}
    good_nrr   = {t: 0.0 for t in teams}
    confirmed2 = {t: 0   for t in teams}
    good_nrr2  = {t: 0.0 for t in teams}

    # Per-(team, metric) lists of scenario indices. Only populated if
    # track_scenarios is True. For 'good_nrr' metrics we record every
    # scenario where the team gets non-zero credit (ahead < cutoff);
    # the credit amount itself can always be recomputed from i.
    if track_scenarios:
        sc_top_n_confirmed = {t: [] for t in teams}
        sc_top_n_good_nrr  = {t: [] for t in teams}
        sc_top_2_confirmed = {t: [] for t in teams}
        sc_top_2_good_nrr  = {t: [] for t in teams}

    start_time = time.time()

    for i in range(combos):
        if print_every and (i + 1) % print_every == 0:
            elapsed = chop_microseconds(datetime.timedelta(seconds=time.time() - start_time))
            print("  {:,} / {:,} ({:.1f}%) | elapsed {}".format(
                i+1, combos, (i+1)*100/combos, elapsed))

        binaryStr = format(i, formatStr)
        simPoints = basePoints.copy()
        for matchCnt, seq in enumerate(binaryStr):
            team1, team2 = matches[matchCnt].split(":")
            simPoints[team1 if seq == "0" else team2] += 2

        for team in teams:
            my_pts = simPoints[team]
            ahead  = sum(1 for t in teams if t != team and simPoints[t] > my_pts)
            tied   = sum(1 for t in teams if t != team and simPoints[t] == my_pts)

            if ahead + tied <= top_n - 1:
                confirmed[team] += 1
                if track_scenarios:
                    sc_top_n_confirmed[team].append(i)

            if ahead < top_n:
                good_nrr[team] += min(1.0, (top_n - ahead) / (1 + tied))
                if track_scenarios:
                    sc_top_n_good_nrr[team].append(i)

            if ahead + tied <= 1:
                confirmed2[team] += 1
                if track_scenarios:
                    sc_top_2_confirmed[team].append(i)

            if ahead < 2:
                good_nrr2[team] += min(1.0, (2 - ahead) / (1 + tied))
                if track_scenarios:
                    sc_top_2_good_nrr[team].append(i)

    elapsed_total = chop_microseconds(datetime.timedelta(seconds=time.time() - start_time))

    summary = []
    for team in teams:
        summary.append({
            "team"               : team.upper(),
            "top2_confirmed_pct" : round(confirmed2[team] * 100.0 / combos, 6),
            "top2_good_nrr_pct"  : round(good_nrr2[team]  * 100.0 / combos, 6),
            "top4_confirmed_pct" : round(confirmed[team]  * 100.0 / combos, 6),
            "top4_good_nrr_pct"  : round(good_nrr[team]   * 100.0 / combos, 6),
        })
    summary.sort(key=lambda x: -x["top2_good_nrr_pct"])

    out = {
        "summary"         : summary,
        "total_scenarios" : combos,
        "elapsed"         : str(elapsed_total),
        "matches"         : list(matches_master),
        "basePoints"      : dict(basePoints_master),
        "top_n"           : top_n,
    }
    if track_scenarios:
        # Use upper-case team keys for consistency with the summary table.
        out["scenarios"] = {
            "top{}_confirmed".format(top_n) : {t.upper(): sc_top_n_confirmed[t] for t in teams},
            "top{}_good_nrr".format(top_n)  : {t.upper(): sc_top_n_good_nrr[t]  for t in teams},
            "top2_confirmed"                 : {t.upper(): sc_top_2_confirmed[t] for t in teams},
            "top2_good_nrr"                  : {t.upper(): sc_top_2_good_nrr[t]  for t in teams},
        }
    print("Completed {:,} scenarios in {}\n".format(combos, elapsed_total))
    return out


def decode_scenario(i, basePoints, matches):
    """
    Given a scenario index i, return everything you might want to know
    about that scenario:
      - 'winners'  : a flat list of winner team names, one entry per
                     remaining match, in the same order as `matches`.
                     e.g. ["kkr", "gt",......  ......, "dc"].
      - 'outcomes' : list of dicts {match, winner, loser}, in case you
                     want both teams of each match handy.
      - 'points'   : final simulated points table after applying every
                     match outcome to the starting basePoints.
      - 'standings': list of (team, points) sorted by points desc.

    All four are derived from the same single bit-walk over `i`, so
    decoding a scenario is O(n) where n is the number of pending matches.
    """
    n         = len(matches)
    binaryStr = format(i, "0{}b".format(n))
    simPoints = dict(basePoints)
    winners   = []
    outcomes  = []
    for k, seq in enumerate(binaryStr):
        team1, team2 = matches[k].split(":")
        # Bit convention: 0 means team1 wins, 1 means team2 wins. This
        # has to match the convention used in run_ipl_simulation, which
        # it does — same `if seq == "0"` branch.
        if seq == "0":
            winner, loser = team1, team2
        else:
            winner, loser = team2, team1
        simPoints[winner] += 2
        winners.append(winner)
        outcomes.append({"match": matches[k], "winner": winner, "loser": loser})
    standings = sorted(simPoints.items(), key=lambda kv: -kv[1])
    return {"index": i, "winners": winners, "outcomes": outcomes,
            "points": simPoints, "standings": standings}


def view_scenarios(results, team, metric, limit=10, show_winners=True):
    """
    Return a pandas DataFrame summarising the qualifying scenarios for
    (team, metric). Each row is one scenario.

    The `limit` parameter controls how many scenarios are returned:
      - limit = N (a positive integer) : return the first N scenarios.
      - limit = None                   : return ALL qualifying scenarios.
                                         Useful when you want to export
                                         or analyse the full set.
      - limit = 0                      : return an empty DataFrame
                                         (just the schema).

    Note on performance: for popular metrics like SRH's top4_good_nrr,
    `limit=None` may need to decode hundreds of thousands of scenarios.
    Each decode is fast (~20 string ops), so a few hundred thousand rows
    take a few seconds and a few hundred MB of RAM. If you hit memory
    pressure, write directly to disk in chunks instead of building one
    huge DataFrame in memory.

    Columns:
      - 'i'                 : the scenario index
      - '{team}_credit'     : 1.0 for confirmed metrics, possibly
                              fractional (e.g. 0.25) for good_nrr
      - '{team}_rank_min'   : best-case finishing rank in this scenario
      - '{team}_rank_max'   : worst-case finishing rank
      - one column per team : final simulated points
      - 'winners'           : (if show_winners) list of winners aligned
                              with results['matches'], so element k is
                              the winner of the k-th remaining match.

    Returns:
      (DataFrame, total_count) where total_count is the FULL number of
      qualifying scenarios — not the row count of the returned frame.
      That way, even if you ask for limit=10, you can see how many there
      are in total.
    """
    indices    = results["scenarios"][metric][team.upper()]
    matches    = results["matches"]
    basePoints = results["basePoints"]
    cutoff     = results["top_n"] if metric.startswith("top4") else 2

    # Decide how many scenarios to actually decode.
    # Python's slicing semantics let us treat None and a positive int
    # uniformly: indices[:None] is the full list, indices[:5] is the
    # first 5. So we can just pass `limit` directly into the slice.
    # The only special case worth handling is the user passing 0,
    # which Python would handle correctly anyway but we make explicit
    # for clarity below.
    selected = indices[:limit] if limit != 0 else []

    # Friendly heads-up when the export is large, so the user doesn't
    # think the cell is hung. We only print once per call so it stays
    # quiet for normal use.
    if limit is None and len(selected) > 100_000:
        print(f"Decoding all {len(selected):,} scenarios for "
              f"{team.upper()} / {metric}; this may take a few seconds.")

    rows = []
    for i in selected:
        d      = decode_scenario(i, basePoints, matches)
        my_pts = d["points"][team.lower()]
        ahead  = sum(1 for t, p in d["points"].items() if t != team.lower() and p > my_pts)
        tied   = sum(1 for t, p in d["points"].items() if t != team.lower() and p == my_pts)
        if "confirmed" in metric:
            credit = 1.0
        else:
            credit = min(1.0, (cutoff - ahead) / (1 + tied)) if ahead < cutoff else 0.0

        row = {"i": i,
               f"{team.upper()}_credit"  : credit,
               f"{team.upper()}_rank_min": ahead + 1,
               f"{team.upper()}_rank_max": ahead + 1 + tied}
        for t, p in sorted(d["points"].items()):
            row[t.upper()] = p
        if show_winners:
            row["winners"] = d["winners"]
        rows.append(row)
    return pd.DataFrame(rows), len(indices)

# %%
# ---------- run and verify ----------
basePoints = {
    "srh": 14, 
    "gt": 14,
    "pbks": 13, 
    "rcb": 12, 
    "rr": 12, 
    "csk": 12, 
    "kkr": 9, 
    "dc": 8, 
    "mi": 6, 
    "lsg": 6,
}
matches = [
    "rcb:mi", 
    "pbks:dc",
    "gt:srh", 
    "rcb:kkr", 
    "pbks:mi", 
    "lsg:csk", 
    "kkr:gt",
    "pbks:rcb", 
    "dc:rr", 
    "csk:srh", 
    "rr:lsg", 
    "kkr:mi",
    "gt:csk", 
    "srh:rcb", 
    "lsg:pbks", 
    "mi:rr", 
    "kkr:dc",
]
results = run_ipl_simulation(basePoints, matches, top_n=4)

# %%
pd.DataFrame(results["summary"])

# %%
# top2_good_nrr, top2_confirmed, top4_good_nrr, top4_confirmed
df, total = view_scenarios(results, "MI", "top4_confirmed", limit=None)
print(df.shape)
total

# %%
df

# %%
mi_conf = results["scenarios"]["top4_confirmed"]["MI"]
print("List of scenario indices for MI's top4_confirmed:\n", mi_conf)

random_choice = random.choice(mi_conf)
print("\nDecoding a random scenario for MI's top4_confirmed:\n", random_choice)
d = decode_scenario(random_choice, basePoints, matches)

# %%
print(f"\nPaired with the matches:")
for match, matchwinner in zip(matches, d["winners"]):
    loser = [t for t in match.split(":") if t != matchwinner][0]
    print(f"  {match.upper():>10}  ->  {matchwinner.upper():>4}  beats  {loser.upper():>4}")

print(f"\nFinal standings:")
for t, p in d["standings"]:
    print(f"  {t.upper():>4}: {p}")


