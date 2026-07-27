# LinkedIn Games Leaderboard

Scrapes the daily LinkedIn games connections leaderboards for Alex and
Elizabeth, scores the day out of 8 (6 timed games + Pinpoint rank + total
time), renders the leaderboard chart and publishes it at a stable URL used
by https://alexwaite.org/linkedin-leaderboard/.

## How it runs
- Scheduled: every 30 minutes 07:00-19:30 UTC. Each run exits immediately
  once the day's result is final (both players have completed all 7 games).
- Manual: Actions tab -> "LinkedIn Leaderboard" -> Run workflow (the button
  push). Tick "force publish" to publish an incomplete day.

## Secrets (Settings -> Secrets and variables -> Actions)
- LI_AT: LinkedIn li_at cookie
- JSESSIONID: LinkedIn JSESSIONID cookie value (without quotes)

When the LinkedIn cookies expire, replace the two secrets - nothing else
needs to change.

## Scoring rules
- tango, zip, queens, mini-sudoku, crossclimb, patches: fastest time wins
  the point; identical times = half a point each.
- pinpoint: best (lowest) rank wins; tie = half each.
- 8th point: lowest total time across the 6 timed games; tie = half each.
- If only one player played a game, they take that point.

## Outputs
- data/history.json - daily scores (chart source of truth)
- chart/latest.png - stable URL for the website
- chart/LeaderboardYYYYMMDD-HHMMSS.png - dated archive
