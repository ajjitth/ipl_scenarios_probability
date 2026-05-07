# %%
import datetime
import time
import pandas as pd

# %%
def chop_microseconds(delta):
    return delta - datetime.timedelta(microseconds=delta.microseconds)


def run_ipl_simulation(basePoints_master, matches_master,
                       top_n=4, print_every=500000):
    """
    For each team and each finishing slot threshold (top_n and top-2),
    compute the metrics:

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
                      scenarios produces the '+ Good NRR' probability.
    """

    basePoints = basePoints_master.copy()
    matches    = matches_master.copy()

    simulation_condition = "before {}".format(matches[0])
    print("Simulating from current standings (next game: {})\n".format(matches[0]))

    teams     = sorted(basePoints.keys())
    n         = len(matches)
    combos    = pow(2, n)
    formatStr = "0{}b".format(n)

    print("Pending matches    : {}".format(n))
    print("Possible scenarios : {:,}\n".format(combos))

    # Two counters per team for top_n, two more for top-2.
    # 'good_nrr' is float because each scenario can contribute a fraction.
    confirmed  = {t: 0   for t in teams}
    good_nrr   = {t: 0.0 for t in teams}
    confirmed2 = {t: 0   for t in teams}
    good_nrr2  = {t: 0.0 for t in teams}

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

            # GOOD-NRR: give me my fair share of remaining slots at my points 
            # level. Cap at 1 because a team can only occupy one qualifying slot.
            # The cap matters: if I'm alone at the top (ahead = 0, tied = 0), 
            # slots / competitors = 4, but my actual contribution should be 1.
            if ahead < top_n:
                slots       = top_n - ahead
                competitors = 1 + tied
                good_nrr[team] += min(1.0, slots / competitors)

            # ── TOP-2 metrics: same definitions, top_n replaced by 2 ──
            if ahead + tied <= 1:
                confirmed2[team] += 1
            if ahead < 2:
                good_nrr2[team] += min(1.0, (2 - ahead) / (1 + tied))

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

    summary.sort(key=lambda x: -x["top2_confirmed_pct"])

    print('=' * 86)
    print("  RESULTS: {}".format(simulation_condition))
    print('=' * 86)
    print("{:>5} | {:>8} | {:>8} | {:>8} | {:>8}".format(
        "Team", "T2 Conf", "T2 NRR", "T4 Conf", "T4 NRR"))
    print("-" * 86)
    for row in summary:
        print("{:>5} | {:>7.2f}% | {:>7.2f}% | {:>7.2f}% | {:>7.2f}%".format(
            row["team"],
            row["top2_confirmed_pct"], row["top2_good_nrr_pct"],
            row["top4_confirmed_pct"], row["top4_good_nrr_pct"]
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

results = run_ipl_simulation(basePoints, matches)

# %%
print(results.keys())
pd.set_option("display.float_format", "{:.4f}".format)
display_df = pd.DataFrame(results["summary"])[['team', 'top2_confirmed_pct', 'top2_good_nrr_pct', 'top4_confirmed_pct', 'top4_good_nrr_pct']].copy()
display_df = display_df.rename(columns={
    'team': 'Team',
    'top2_confirmed_pct': 'Top2 Pts Only',
    'top2_good_nrr_pct': 'Top2 Pts + Good NRR',
    'top4_confirmed_pct': 'Top4 Pts Only',
    'top4_good_nrr_pct': 'Top4 Pts + Good NRR',
})
display_df = display_df.reset_index(drop=True)
display_df


