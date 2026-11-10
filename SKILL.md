# Football Prediction

## Gather the evidence

- Confirm the fixture list for the requested date first, with kickoff times converted to the user's timezone, and drop matches that have already started.

- Check whether the machina-sports `sports-skills` package covers the competition before promising its data, following the coverage notes in `references/data-sources.md`.

- Pull recent form, home and away splits, head-to-head history, injuries and at least one published model probability for each shortlisted match, cross-checking two independent sources per match.

- Pull market 1X2 odds from at least two bookmaker or aggregator sources per match, following the odds-reference workflow in `references/data-sources.md`. Read public odds pages only — never register, log in or bet. Record the reference price in the ledger's `odds` field for every pick.

- Treat lower-league weekday slates as lower confidence by default, and say so in the recommendation.

## Run the model

- Anchor on the market first: run `model.py fit` on the de-vigged market consensus to get the market-implied lambda pair. That pair is the baseline — the market's odds distill professional models and money flow, so start from them instead of building in a vacuum.

- Adjust the lambdas only for verified information the price has not absorbed yet (rotation, injuries, motivation, weather), and state each adjustment and its reason in the recommendation. With no such information, keep the market-implied probabilities; do not manufacture an edge.

- Then run `~/workspace/custom-skills/football_prediction/scripts/model.py predict` with the final lambda pair (or the evidence-based estimate when no market exists for the competition).

- Fall back to the script's Elo route only when no expected-goals estimate exists, and flag Elo-based output as rough when you present it.

- De-vig any market prices you cite with `model.py devig`, and compare the fair probabilities against the model before keeping a pick.

- Build parlays with `model.py parlay` from the legs' fair probabilities, and present the combined probability and fair combined odds with every parlay.

## Convert to lottery play

- Map model output to China Sports Lottery markets directly: win-draw-loss from the 1X2 probabilities, total goals from the total-goals distribution, both-teams-to-score and over or under 2.5 from the goal markets, exact scores only from the top of the score list and always labeled as low probability.

- Prefer a goals market over a result market when the goal probabilities are clearly stronger than the 1X2 edge, and prefer a single over a parlay when the user asks for the safest option.

- State an honest hit-probability estimate for every recommended combination, and keep stakes framed as entertainment money with a fixed cap.

## Record and review

- Record every recommendation the user may act on with `~/workspace/custom-skills/football_prediction/scripts/ledger.py add` before kickoff, one entry per market pick, including `--odds` (reference price) and `--mprob` (de-vigged market probability for the same market) so settlement can judge the adjustment against the market.

- The report's `vs_market` block is the running verdict on the distillation: our Brier score vs the market's, and the hit record on picks that diverged from the market by 8+ points. If the edge stays negative over a meaningful sample, shrink adjustments toward the market anchor.

- Settle finished matches with `ledger.py settle` using the final score, then run `ledger.py report` and show the user the running hit rate by market.

- Review misses without excuses: name which input was wrong, such as the expected-goals estimate or a form read, and adjust the next slate's confidence instead of promising improvement.

## Available connectors

- [GitHub](/opt/hatch/connectors/github/CONNECTOR.md) for storing this skill's code in the user's repository.
