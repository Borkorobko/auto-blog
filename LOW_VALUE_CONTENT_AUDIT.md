# AdSense low-value-content audit — pass 2

This pass follows the September 2026 AdSense rejection for **Low value content**.

## What was already in place

- scheduled article generation is paused;
- overlapping speed/training articles are consolidated;
- very thin articles are noindexed;
- the active library is rebuilt to exclude noindex pages.

## Rewrite queue

The pages below have strong buying intent in the title but currently answer it mostly with generic selection advice rather than concrete, differentiated recommendations. They are temporarily set to `noindex, follow` and removed from the article library and sitemap until rewritten.

| Page | Main issue | Required before reindexing |
| --- | --- | --- |
| `best-football-boots-under-100.html` | "Best" + price intent, but no concrete picks/comparison | clear picks or product tiers, comparison table, budget caveat, distinct trade-offs |
| `best-football-boots-for-beginners.html` | generic beginner buying advice | beginner-specific shortlist/types, comparison, fit/surface decision tree |
| `best-football-boots-for-defenders.html` | position intent not answered with differentiated picks | defender-specific use cases, trade-offs, comparison |
| `best-football-boots-for-midfielders.html` | position intent not answered with differentiated picks | midfielder-specific use cases, trade-offs, comparison |
| `best-football-boots-for-artificial-grass.html` | broad generic guide with weak AG-specific depth | AG-specific soleplate guidance, comparison, surface/care detail |
| `best-football-goalkeeper-gloves.html` | "Best" intent without concrete glove recommendations | cut/latex/use-case comparison, durability vs grip trade-offs, shortlist/types |

## Keep / stronger examples

These pages currently show a better structure and should be used as the rewrite benchmark rather than creating more articles:

- `best-football-boots-for-wet-conditions.html` — has a Quick Picks section and comparison table.
- `best-football-boots-for-speed.html` — has a comparison table and more specific model/context references.
- `speed-training-for-football.html` — consolidated pillar guide replacing multiple overlapping speed pages.

## Reindex rule

A page in the rewrite queue should not return to the sitemap/library until it:

1. answers the exact search intent near the top;
2. contains clearly differentiated practical recommendations, not just generic advice;
3. includes a useful comparison/table when the query is commercial;
4. avoids invented testing, prices, endorsements or availability;
5. has distinct value that is not already covered by another FTL page.

New-article generation stays paused during this cleanup.
