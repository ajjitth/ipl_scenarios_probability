# %%
import datetime
import time
import pandas as pd

# %%
# ─── CORE ENGINE ──────────────────────────────────────────────────────────────

def chop_microseconds(delta):
    return delta - datetime.timedelta(microseconds=delta.microseconds)

def run_ipl_simulation(basePoints_master, matches_master, winner=None, top_n=4, print_every=500000):
    """
    Run IPL playoff probability simulation.

    Parameters:
        basePoints_master : dict  - current points table
        matches_master    : list  - remaining matches
        winner            : str   - assumed winner of next game, or None for current state
        top_n             : int   - how many teams qualify (default 4, use 2 for top-2 check)
        print_every       : int   - print progress every N simulations (set 0 to silence)

    Returns:
        dict with keys:
            "summary"            - list of dicts, one per team, sorted by top_n_possible desc
            "simulation_condition" - description string
            "total_scenarios"    - total number of simulated scenarios
            "elapsed"            - time taken
    """

    basePoints = basePoints_master.copy()
    matches    = matches_master.copy()

    # ── handle winner assumption ──
    if winner is not None:
        nextMatch = matches[0]
        simulation_condition = "{} wins {}".format(winner.upper(), nextMatch)
        if winner not in nextMatch:
            raise ValueError("{} is not playing in next game '{}'".format(winner, nextMatch))
        print("Assuming {} wins → points +2, removing {} from schedule\n".format(winner.upper(), nextMatch))
        basePoints[winner] += 2
        matches = matches[1:]
    else:
        simulation_condition = "before {}".format(matches[0])
        print("Simulating from current standings (next game: {})\n".format(matches[0]))

    # ── setup ──
    teams     = sorted(basePoints.keys())
    n         = len(matches)
    combos    = pow(2, n)
    formatStr = "0{}b".format(n)

    print("Pending matches    : {}".format(n))
    print("Possible scenarios : {:,}\n".format(combos))

    confirmed = {t: 0 for t in teams}   # guaranteed top_n finish
    possible  = {t: 0 for t in teams}   # possible top_n finish
    confirmed2 = {t: 0 for t in teams}
    possible2  = {t: 0 for t in teams}

    start_time = time.time()

    # ── simulate every scenario ──
    for i in range(combos):

        if print_every and (i + 1) % print_every == 0:
            elapsed = chop_microseconds(datetime.timedelta(seconds=time.time() - start_time))
            eta     = chop_microseconds(datetime.timedelta(seconds=(time.time() - start_time) * (combos - i + 1) / (i + 1)))
            print("  {:,} / {:,} ({:.1f}%) | elapsed {} | eta {}".format(i+1, combos, (i+1)*100/combos, elapsed, eta))

        binaryStr = format(i, formatStr)
        simPoints = basePoints.copy()

        for matchCnt, seq in enumerate(binaryStr):
            team1, team2 = matches[matchCnt].split(":")
            simPoints[team1 if seq == "0" else team2] += 2

        for team in teams:
            ahead  = sum(1 for t in teams if t != team and simPoints[t] > simPoints[team])
            behind = sum(1 for t in teams if t != team and simPoints[t] < simPoints[team])

            n_teams = len(teams)
            if ahead  <= (top_n - 1):        possible[team]   += 1
            if behind >= (n_teams - top_n):  confirmed[team]  += 1
            if ahead  <= 1:                  possible2[team]  += 1
            if behind >= (n_teams - 2):      confirmed2[team] += 1

    # ── build results ──
    elapsed_total = chop_microseconds(datetime.timedelta(seconds=time.time() - start_time))

    summary = []
    for team in teams:
        summary.append({
            "team"              : team.upper(),
            "top2_possible_pct" : round(possible2[team]  * 100.0 / combos, 2),
            "top2_confirmed_pct": round(confirmed2[team] * 100.0 / combos, 2),
            "top4_possible_pct" : round(possible[team]   * 100.0 / combos, 2),
            "top4_confirmed_pct": round(confirmed[team]  * 100.0 / combos, 2),
        })

    summary.sort(key=lambda x: -x["top4_possible_pct"])

    # ── print results table ──
    print('='*70)
    print("  RESULTS: {}".format(simulation_condition))
    print("="*70)
    print("{:>6} | {:>14} | {:>13} | {:>14} | {:>13}".format(
        "Team", "Top2 Confirmed", "Top2 Possible", "Top4 Confirmed", "Top4 Possible"))
    print("-" * 70)
    for row in summary:
        print("{:>6} | {:>13.1f}% | {:>12.1f}% | {:>13.1f}% | {:>12.1f}%".format(
            row["team"],
            row["top2_confirmed_pct"], row["top2_possible_pct"],
            row["top4_confirmed_pct"], row["top4_possible_pct"],
        ))
        
    print("="*70)
    print("Completed {:,} scenarios in {}\n".format(combos, elapsed_total))

    return {
        "summary"              : summary,
        "simulation_condition" : simulation_condition,
        "total_scenarios"      : combos,
        "elapsed"              : str(elapsed_total),
    }

# %%
# ─── CONFIGURATION & RUN ─────────────────────────────────────────────────────
# May 3, 2026

basePoints = {
    "pbks": 13,
    "rcb":  12,
    "srh":  14,
    "rr":   12,
    "gt":   12,
    "csk":  10,
    "dc":    8,
    "kkr":   7,
    "mi":    6,
    "lsg":   6,
}

# Remaining matches: 51–70 (matches 1–50 already completed)
matches = [
    "dc:kkr",    # 51 - May 08
    "rr:gt",     # 52 - May 09
    "csk:lsg",   # 53 - May 10
    "rcb:mi",    # 54 - May 10
    "pbks:dc",   # 55 - May 11
    "gt:srh",    # 56 - May 12
    "rcb:kkr",   # 57 - May 13
    "pbks:mi",   # 58 - May 14
    "lsg:csk",   # 59 - May 15
    "kkr:gt",    # 60 - May 16
    "pbks:rcb",  # 61 - May 17
    "dc:rr",     # 62 - May 17
    "csk:srh",   # 63 - May 18
    "rr:lsg",    # 64 - May 19
    "kkr:mi",    # 65 - May 20
    "gt:csk",    # 66 - May 21
    "srh:rcb",   # 67 - May 22
    "lsg:pbks",  # 68 - May 23
    "mi:rr",     # 69 - May 24
    "kkr:dc",    # 70 - May 24
]

results = run_ipl_simulation(
    basePoints_master = basePoints,
    matches_master    = matches,
    winner            = None,   
)

# %%
print(results.keys())
pd.set_option("display.float_format", "{:.4f}".format)
pd.DataFrame(results["summary"])


