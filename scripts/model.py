#!/usr/bin/env python3
"""Football match prediction model: Poisson score matrix with a
Dixon-Coles low-score correction, plus odds helpers (de-vig, parlay).

Usage:
  model.py predict --home Sabadell --away "Real Sociedad B" --lam-home 1.45 --lam-away 0.95
  model.py predict --home A --away B --elo-home 1650 --elo-away 1520 [--league-avg 2.65]
  model.py devig --odds 1.70 3.40 3.20
  model.py parlay --legs 0.55 0.60 [--odds 3.90]
  model.py fit --odds 1.67 4.75 6.25 [--home A --away B]
  model.py fit --probs 0.60 0.22 0.18

The fit subcommand inverts market 1X2 prices (or fair probabilities) into
the lambda pair whose model 1X2 best matches them. Use it to anchor the
model on the market consensus first, then adjust the lambdas only for
verified information the price has not absorbed (rotation, injuries,
motivation), and state the adjustment and its reason.

Expected goals (lambda) come first when the caller has them from form,
xG or a published model. The Elo route is a rough fallback: goal
supremacy is approximated as (elo_diff + 60 home edge) / 280.
"""
import argparse
import json
import math
import sys

MAX_GOALS = 10


def poisson(k, lam):
    return math.exp(-lam) * lam ** k / math.factorial(k)


def dc_tau(i, j, lam_h, lam_a, rho):
    """Dixon-Coles correction for low scores."""
    if i == 0 and j == 0:
        return 1.0 - lam_h * lam_a * rho
    if i == 0 and j == 1:
        return 1.0 + lam_h * rho
    if i == 1 and j == 0:
        return 1.0 + lam_a * rho
    if i == 1 and j == 1:
        return 1.0 - rho
    return 1.0


def score_matrix(lam_h, lam_a, rho=-0.08):
    m = {}
    total = 0.0
    for i in range(MAX_GOALS + 1):
        for j in range(MAX_GOALS + 1):
            p = poisson(i, lam_h) * poisson(j, lam_a) * dc_tau(i, j, lam_h, lam_a, rho)
            m[(i, j)] = p
            total += p
    for k in m:
        m[k] /= total
    return m


def predict(args):
    if args.lam_home is not None and args.lam_away is not None:
        lam_h, lam_a = args.lam_home, args.lam_away
        lam_source = "expected_goals_input"
    elif args.elo_home is not None and args.elo_away is not None:
        diff = (args.elo_home - args.elo_away + 60.0) / 280.0
        lam_h = max(0.15, (args.league_avg + diff) / 2.0)
        lam_a = max(0.15, (args.league_avg - diff) / 2.0)
        lam_source = "elo_heuristic"
    else:
        print("error: give --lam-home/--lam-away or --elo-home/--elo-away", file=sys.stderr)
        return 2

    m = score_matrix(lam_h, lam_a, args.rho)
    p_home = sum(p for (i, j), p in m.items() if i > j)
    p_draw = sum(p for (i, j), p in m.items() if i == j)
    p_away = sum(p for (i, j), p in m.items() if i < j)
    p_btts = sum(p for (i, j), p in m.items() if i >= 1 and j >= 1)
    totals = {}
    for (i, j), p in m.items():
        totals[i + j] = totals.get(i + j, 0.0) + p
    over = {line: sum(p for t, p in totals.items() if t > line) for line in (1.5, 2.5, 3.5)}
    top_scores = sorted(m.items(), key=lambda kv: -kv[1])[:5]

    def pct(x):
        return round(x * 100, 1)

    def fair(p):
        return round(1.0 / p, 2) if p > 0 else None

    out = {
        "home": args.home,
        "away": args.away,
        "lambda_home": round(lam_h, 2),
        "lambda_away": round(lam_a, 2),
        "lambda_source": lam_source,
        "probabilities_pct": {
            "home_win": pct(p_home),
            "draw": pct(p_draw),
            "away_win": pct(p_away),
            "btts_yes": pct(p_btts),
            "over_1_5": pct(over[1.5]),
            "over_2_5": pct(over[2.5]),
            "over_3_5": pct(over[3.5]),
            "under_2_5": pct(1.0 - over[2.5]),
        },
        "fair_odds": {
            "home_win": fair(p_home),
            "draw": fair(p_draw),
            "away_win": fair(p_away),
            "btts_yes": fair(p_btts),
            "over_2_5": fair(over[2.5]),
            "under_2_5": fair(1.0 - over[2.5]),
        },
        "total_goals_pct": {str(t): pct(totals.get(t, 0.0)) for t in range(0, 7)},
        "total_goals_7plus_pct": pct(sum(p for t, p in totals.items() if t >= 7)),
        "top_scores": [{"score": f"{i}-{j}", "pct": pct(p)} for (i, j), p in top_scores],
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


def aggregate(m):
    """Raw probability pieces from a score matrix."""
    p_home = sum(p for (i, j), p in m.items() if i > j)
    p_draw = sum(p for (i, j), p in m.items() if i == j)
    p_away = sum(p for (i, j), p in m.items() if i < j)
    p_btts = sum(p for (i, j), p in m.items() if i >= 1 and j >= 1)
    totals = {}
    for (i, j), p in m.items():
        totals[i + j] = totals.get(i + j, 0.0) + p
    over = {line: sum(p for t, p in totals.items() if t > line) for line in (1.5, 2.5, 3.5)}
    top_scores = sorted(m.items(), key=lambda kv: -kv[1])[:5]
    return p_home, p_draw, p_away, p_btts, totals, over, top_scores


def fit(args):
    if args.odds:
        raw = [1.0 / o for o in args.odds]
        s = sum(raw)
        target = [p / s for p in raw]
    elif args.probs:
        s = sum(args.probs)
        target = [p / s for p in args.probs]
    else:
        print("error: give --odds (1X2) or --probs (fair H D A)", file=sys.stderr)
        return 2

    def err(lam_h, lam_a):
        m = score_matrix(lam_h, lam_a, args.rho)
        ph = sum(p for (i, j), p in m.items() if i > j)
        pd_ = sum(p for (i, j), p in m.items() if i == j)
        pa = sum(p for (i, j), p in m.items() if i < j)
        return (ph - target[0]) ** 2 + (pd_ - target[1]) ** 2 + (pa - target[2]) ** 2

    best, best_e = None, None
    lam = 0.15
    grid = []
    while lam <= 3.605:
        grid.append(round(lam, 2))
        lam += 0.05
    for lh in grid:
        for la in grid:
            e = err(lh, la)
            if best_e is None or e < best_e:
                best, best_e = (lh, la), e
    step = 0.01
    lo_h, lo_a = best
    for lh in [round(lo_h + d * step, 2) for d in range(-5, 6)]:
        for la in [round(lo_a + d * step, 2) for d in range(-5, 6)]:
            if lh <= 0 or la <= 0:
                continue
            e = err(lh, la)
            if e < best_e:
                best, best_e = (lh, la), e

    lam_h, lam_a = best
    m = score_matrix(lam_h, lam_a, args.rho)
    p_home, p_draw, p_away, p_btts, totals, over, top_scores = aggregate(m)

    def pct(x):
        return round(x * 100, 1)

    out = {
        "home": args.home,
        "away": args.away,
        "target_probabilities_pct": [pct(p) for p in target],
        "lambda_home": round(lam_h, 2),
        "lambda_away": round(lam_a, 2),
        "lambda_source": "market_fit",
        "fit_error": round(best_e, 6),
        "probabilities_pct": {
            "home_win": pct(p_home),
            "draw": pct(p_draw),
            "away_win": pct(p_away),
            "btts_yes": pct(p_btts),
            "over_2_5": pct(over[2.5]),
            "under_2_5": pct(1.0 - over[2.5]),
        },
        "total_goals_pct": {str(t): pct(totals.get(t, 0.0)) for t in range(0, 7)},
        "top_scores": [{"score": f"{i}-{j}", "pct": pct(p)} for (i, j), p in top_scores],
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


def devig(args):
    probs = [1.0 / o for o in args.odds]
    s = sum(probs)
    fair = [p / s for p in probs]
    out = {
        "book_odds": args.odds,
        "overround_pct": round((s - 1.0) * 100, 2),
        "fair_probabilities_pct": [round(p * 100, 1) for p in fair],
        "fair_odds": [round(1.0 / p, 2) for p in fair],
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


def parlay(args):
    combined = 1.0
    for p in args.legs:
        combined *= p
    out = {
        "legs_pct": [round(p * 100, 1) for p in args.legs],
        "combined_probability_pct": round(combined * 100, 1),
        "fair_combined_odds": round(1.0 / combined, 2) if combined > 0 else None,
    }
    if args.odds:
        ev = combined * args.odds - 1.0
        out["offered_odds"] = args.odds
        out["expected_value_pct"] = round(ev * 100, 1)
        out["verdict"] = "positive_ev" if ev > 0 else "negative_ev"
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


def main():
    ap = argparse.ArgumentParser(description="Football prediction model")
    sub = ap.add_subparsers(dest="cmd", required=True)

    pp = sub.add_parser("predict")
    pp.add_argument("--home", required=True)
    pp.add_argument("--away", required=True)
    pp.add_argument("--lam-home", type=float)
    pp.add_argument("--lam-away", type=float)
    pp.add_argument("--elo-home", type=float)
    pp.add_argument("--elo-away", type=float)
    pp.add_argument("--league-avg", type=float, default=2.65)
    pp.add_argument("--rho", type=float, default=-0.08)
    pp.set_defaults(fn=predict)

    pd = sub.add_parser("devig")
    pd.add_argument("--odds", type=float, nargs="+", required=True)
    pd.set_defaults(fn=devig)

    pf = sub.add_parser("fit")
    pf.add_argument("--home")
    pf.add_argument("--away")
    pf.add_argument("--odds", type=float, nargs=3, help="1X2 book odds H D A")
    pf.add_argument("--probs", type=float, nargs=3, help="fair probabilities H D A, decimals")
    pf.add_argument("--rho", type=float, default=-0.08)
    pf.set_defaults(fn=fit)

    pl = sub.add_parser("parlay")
    pl.add_argument("--legs", type=float, nargs="+", required=True,
                    help="fair probability of each leg, as decimals")
    pl.add_argument("--odds", type=float)
    pl.set_defaults(fn=parlay)

    args = ap.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
