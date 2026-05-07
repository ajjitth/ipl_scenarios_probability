# %%
import datetime
import time
import pandas as pd

# %%
"""
Modified IPL simulation. Adds a third metric per team — 'good_nrr_pct' —
which uses the fractional-credit definition that matches the Reddit
'+ Good NRR' column. The original 'confirmed' and 'possible' metrics are
preserved so you can see all three side by side.
"""
def chop_microseconds(delta):
    return delta - datetime.timedelta(microseconds=delta.microseconds)


def run_ipl_simulation(basePoints_master, matches_master, winner=None,
                       top_n=4, print_every=500000):
    """
    For each team and each finishing slot threshold (top_n and top-2),
    compute three metrics:

      confirmed_pct : guaranteed to finish in the top, regardless of any
                      tiebreaker. Mathematically: (teams strictly ahead) +
                      (teams tied with me on points) <= top_n - 1, so even
                      if every tied team beats me on NRR there are still
                      slots left for me.

      good_nrr_pct  : fractional credit. In each scenario, at my points
                      level (4 - ahead) slots are still open, and
                      (1 + tied) teams (including me) compete for them.
                      I get my fair share, capped at 1 since I can only
                      occupy one slot myself. Averaging this over all
                      scenarios produces the column the Reddit author
                      labels '+ Good NRR'.

      possible_pct  : the original definition — counts the scenario fully
                      if it's logically possible for me to qualify
                      (i.e. fewer than top_n teams strictly ahead). This
                      double-counts when several teams are tied at the
                      cutoff and is usually too optimistic.
    """

    basePoints = basePoints_master.copy()
    matches    = matches_master.copy()

    # Optional 'winner' branch — unchanged from the original code.
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

    teams     = sorted(basePoints.keys())
    n         = len(matches)
    combos    = pow(2, n)
    formatStr = "0{}b".format(n)

    print("Pending matches    : {}".format(n))
    print("Possible scenarios : {:,}\n".format(combos))

    # Three counters per team for top_n, three more for top-2.
    # 'good_nrr' is float because each scenario can contribute a fraction.
    confirmed  = {t: 0   for t in teams}
    good_nrr   = {t: 0.0 for t in teams}
    possible   = {t: 0   for t in teams}
    confirmed2 = {t: 0   for t in teams}
    good_nrr2  = {t: 0.0 for t in teams}
    possible2  = {t: 0   for t in teams}

    start_time = time.time()

    for i in range(combos):

        if print_every and (i + 1) % print_every == 0:
            elapsed = chop_microseconds(datetime.timedelta(seconds=time.time() - start_time))
            eta     = chop_microseconds(datetime.timedelta(seconds=(time.time() - start_time) * (combos - i + 1) / (i + 1)))
            print("  {:,} / {:,} ({:.1f}%) | elapsed {} | eta {}".format(
                i+1, combos, (i+1)*100/combos, elapsed, eta))

        # Bit pattern of i decides who wins each remaining match.
        binaryStr = format(i, formatStr)
        simPoints = basePoints.copy()
        for matchCnt, seq in enumerate(binaryStr):
            team1, team2 = matches[matchCnt].split(":")
            simPoints[team1 if seq == "0" else team2] += 2

        # Score this scenario from each team's perspective.
        for team in teams:
            my_pts = simPoints[team]
            ahead  = sum(1 for t in teams if t != team and simPoints[t] > my_pts)
            tied   = sum(1 for t in teams if t != team and simPoints[t] == my_pts)

            # ── TOP-N metrics ──

            # CONFIRMED: even if every tied team beats me on NRR, I still
            # land in the top_n. That requires ahead + tied <= top_n - 1.
            if ahead + tied <= top_n - 1:
                confirmed[team] += 1

            # GOOD-NRR (fractional): give me my fair share of remaining
            # slots at my points level. Cap at 1 because a team can only
            # occupy one qualifying slot. The cap matters: if I'm alone
            # at the top (ahead = 0, tied = 0), slots / competitors = 4,
            # but my actual contribution should be 1.
            if ahead < top_n:
                slots       = top_n - ahead
                competitors = 1 + tied
                good_nrr[team] += min(1.0, slots / competitors)

            # POSSIBLE (lenient): the original definition. Counts the
            # scenario if it's at least logically possible for me to
            # qualify, no matter how many teams are tied at the cutoff.
            if ahead <= top_n - 1:
                possible[team] += 1

            # ── TOP-2 metrics: same three definitions, top_n replaced by 2 ──
            if ahead + tied <= 1:
                confirmed2[team] += 1
            if ahead < 2:
                good_nrr2[team] += min(1.0, (2 - ahead) / (1 + tied))
            if ahead <= 1:
                possible2[team] += 1

    elapsed_total = chop_microseconds(datetime.timedelta(seconds=time.time() - start_time))

    summary = []
    for team in teams:
        summary.append({
            "team"               : team.upper(),
            "top2_confirmed_pct" : round(confirmed2[team] * 100.0 / combos, 6),
            "top2_good_nrr_pct"  : round(good_nrr2[team]  * 100.0 / combos, 6),
            "top2_possible_pct"  : round(possible2[team]  * 100.0 / combos, 6),
            "top4_confirmed_pct" : round(confirmed[team]  * 100.0 / combos, 6),
            "top4_good_nrr_pct"  : round(good_nrr[team]   * 100.0 / combos, 6),
            "top4_possible_pct"  : round(possible[team]   * 100.0 / combos, 6),
        })

    summary.sort(key=lambda x: -x["top4_good_nrr_pct"])

    print('=' * 86)
    print("  RESULTS: {}".format(simulation_condition))
    print('=' * 86)
    print("{:>5} | {:>8} | {:>8} | {:>8} | {:>8} | {:>8} | {:>8}".format(
        "Team", "T2 Conf", "T2 NRR", "T2 Poss", "T4 Conf", "T4 NRR", "T4 Poss"))
    print("-" * 86)
    for row in summary:
        print("{:>5} | {:>7.2f}% | {:>7.2f}% | {:>7.2f}% | {:>7.2f}% | {:>7.2f}% | {:>7.2f}%".format(
            row["team"],
            row["top2_confirmed_pct"], row["top2_good_nrr_pct"], row["top2_possible_pct"],
            row["top4_confirmed_pct"], row["top4_good_nrr_pct"], row["top4_possible_pct"],
        ))
    print('=' * 86)
    print("Completed {:,} scenarios in {}\n".format(combos, elapsed_total))

    return {
        "summary"              : summary,
        "simulation_condition" : simulation_condition,
        "total_scenarios"      : combos,
        "elapsed"              : str(elapsed_total),
    }

# %%
basePoints = {
    "pbks": 13, 
    "rcb": 12, 
    "srh": 14, 
    "rr": 12, 
    "gt": 12,
    "csk": 10, 
    "dc": 8,  
    "kkr": 7,  
    "mi": 6,  
    "lsg": 6,
}

matches = [
    "dc:kkr", 
    "rr:gt", 
    "csk:lsg", 
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
    "kkr:dc"
]

results = run_ipl_simulation(basePoints, matches, winner=None)

# %%
print(results.keys())
pd.set_option("display.float_format", "{:.4f}".format)
display_df = pd.DataFrame(results["summary"])[['team', 'top2_confirmed_pct', 'top2_good_nrr_pct', 'top4_confirmed_pct', 'top4_good_nrr_pct']].copy()
display_df = display_df.sort_values(by='top2_confirmed_pct', ascending=False)
display_df = display_df.rename(columns={
    'team': 'Team',
    'top2_confirmed_pct': 'Top2 Pts Only',
    'top2_good_nrr_pct': 'Top2 Pts + Good NRR',
    'top4_confirmed_pct': 'Top4 Pts Only',
    'top4_good_nrr_pct': 'Top4 Pts + Good NRR',
})
display_df = display_df.reset_index(drop=True)
display_df


