#!/usr/bin/env python3
"""Prediction ledger: record predictions before kickoff, settle them
after the match, and report hit rates. One JSON object per line in
data/predictions.jsonl beside this skill.

Usage:
  ledger.py add --date 2026-11-09 --league 西乙 --home Sabadell --away "Real Sociedad B" \
      --market home_win --label 主胜 --prob 0.52 [--odds 1.70] [--confidence 中] \
      [--mprob 0.49]   (de-vigged market probability for the same market)
  ledger.py settle --home Sabadell --score 1-0
  ledger.py report

Auto-settled markets: home_win, draw, away_win, btts_yes, over_2_5,
under_2_5, total_goals_1_2 (final total 1 or 2), total_goals_3_4
(final total 3 or 4), and score_H-A for an exact score.
"""
import argparse
import json
import os
import sys
import uuid

DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "data", "predictions.jsonl")


def load():
    if not os.path.exists(DATA):
        return []
    with open(DATA, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def save(rows):
    os.makedirs(os.path.dirname(DATA), exist_ok=True)
    with open(DATA, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def add(args):
    rows = load()
    rec = {
        "id": uuid.uuid4().hex[:8],
        "date": args.date,
        "league": args.league,
        "home": args.home,
        "away": args.away,
        "market": args.market,
        "label": args.label or args.market,
        "prob": args.prob,
        "mprob": args.mprob,
        "odds": args.odds,
        "confidence": args.confidence,
        "status": "open",
        "final_score": None,
        "won": None,
    }
    rows.append(rec)
    save(rows)
    print(json.dumps(rec, ensure_ascii=False))
    return 0


def evaluate(market, hg, ag):
    total = hg + ag
    if market == "home_win":
        return hg > ag
    if market == "draw":
        return hg == ag
    if market == "away_win":
        return hg < ag
    if market == "btts_yes":
        return hg >= 1 and ag >= 1
    if market == "over_2_5":
        return total >= 3
    if market == "under_2_5":
        return total <= 2
    if market == "total_goals_1_2":
        return total in (1, 2)
    if market == "total_goals_3_4":
        return total in (3, 4)
    if market.startswith("score_"):
        want = market[len("score_"):].split("-")
        return hg == int(want[0]) and ag == int(want[1])
    return None


def settle(args):
    hg, ag = (int(x) for x in args.score.split("-"))
    rows = load()
    settled = 0
    for r in rows:
        if r["status"] == "open" and r["home"].lower() == args.home.lower():
            won = evaluate(r["market"], hg, ag)
            if won is None:
                continue
            r["status"] = "settled"
            r["final_score"] = args.score
            r["won"] = won
            settled += 1
    save(rows)
    print(f"settled {settled} prediction(s) for {args.home} at {args.score}")
    return 0


def report(args):
    rows = load()
    settled = [r for r in rows if r["status"] == "settled"]
    open_ = [r for r in rows if r["status"] == "open"]
    won = [r for r in settled if r["won"]]
    by_market = {}
    for r in settled:
        by_market.setdefault(r["market"], []).append(r)
    with_mkt = [r for r in settled if r.get("mprob") is not None and r.get("prob") is not None]
    if with_mkt:
        n = len(with_mkt)
        our_brier = sum((r["prob"] - (1.0 if r["won"] else 0.0)) ** 2 for r in with_mkt) / n
        mkt_brier = sum((r["mprob"] - (1.0 if r["won"] else 0.0)) ** 2 for r in with_mkt) / n
        div = [r for r in with_mkt if abs(r["prob"] - r["mprob"]) >= 0.08]
        vs_market = {
            "settled_with_market_prob": n,
            "our_brier": round(our_brier, 4),
            "market_brier": round(mkt_brier, 4),
            "brier_edge": round(mkt_brier - our_brier, 4),
            "diverged_picks": len(div),
            "diverged_won": sum(1 for r in div if r["won"]),
        }
    else:
        vs_market = None
    out = {
        "total_recorded": len(rows),
        "settled": len(settled),
        "won": len(won),
        "hit_rate_pct": round(len(won) / len(settled) * 100, 1) if settled else None,
        "open": [{"home": r["home"], "away": r["away"], "label": r["label"]} for r in open_],
        "by_market": {
            m: {"settled": len(v), "won": sum(1 for x in v if x["won"]),
                "hit_rate_pct": round(sum(1 for x in v if x["won"]) / len(v) * 100, 1)}
            for m, v in by_market.items()
        },
        "vs_market": vs_market,
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


def main():
    ap = argparse.ArgumentParser(description="Prediction ledger")
    sub = ap.add_subparsers(dest="cmd", required=True)

    pa = sub.add_parser("add")
    pa.add_argument("--date", required=True)
    pa.add_argument("--league", required=True)
    pa.add_argument("--home", required=True)
    pa.add_argument("--away", required=True)
    pa.add_argument("--market", required=True)
    pa.add_argument("--label")
    pa.add_argument("--prob", type=float)
    pa.add_argument("--mprob", type=float,
                    help="de-vigged market probability for the same market, decimal")
    pa.add_argument("--odds", type=float)
    pa.add_argument("--confidence")
    pa.set_defaults(fn=add)

    ps = sub.add_parser("settle")
    ps.add_argument("--home", required=True)
    ps.add_argument("--score", required=True, help="final score like 1-0")
    ps.set_defaults(fn=settle)

    pr = sub.add_parser("report")
    pr.set_defaults(fn=report)

    args = ap.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
