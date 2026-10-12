---
id: usage_rate
doc_type: glossary
metric: usage_rate
status: draft (2.8; completed from the registry in 4.1)
---

# Usage rate (USG%)

Usage rate estimates the share of a team's plays a player "uses" while on the floor. A play ends
with that player's field goal attempt, free throw trip or turnover.

**Formula:** USG% = 100 × ((FGA + 0.44 × FTA + TOV) × (Team MIN / 5)) / (MIN × (Team FGA + 0.44 × Team FTA + Team TOV))

- The (Team MIN / 5) and MIN terms scale the player's plays to his time on the floor.
- A player who used exactly one fifth of his team's plays while on the floor has a usage rate of 20%.

**Caveats:** usage measures volume, not efficiency. Primary ball handlers and first scoring
options usually run high usage rates, and many centers who finish plays rather than create them
run lower ones. Values here are NBA.com's published usage rate (1996-97 on).
