# Football Prediction

A Muse skill for predicting football matches for China Sports Lottery play.

- `SKILL.md` holds the working method: gather evidence, run the model, convert to lottery markets, record and review every pick.
- `scripts/model.py` is a Poisson score-matrix model with a Dixon-Coles low-score correction, plus de-vig and parlay calculators.
- `scripts/ledger.py` records predictions before kickoff, settles them from final scores, and reports hit rates by market.
- `references/data-sources.md` records which data sources cover which leagues, verified on 2026-11-09.
- `data/predictions.jsonl` is the live prediction ledger.

Predictions are probability estimates for entertainment, not guarantees.
