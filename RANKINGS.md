# Refreshing player rankings, ADP, and defenses

`pool.json` holds static reference data for every player: name, position, NFL team, a
within-position `rank`, and a cross-position `overallRank` (ADP-based). It is **not** live draft
state -- who's picked, kept, or protected lives entirely in `state.json` and gets layered onto a
fresh copy of this pool in memory on every page render (see `build_derived_state()` in
`generate.py`). That means **refreshing `pool.json` is safe at any time, including mid-draft** --
it cannot lose or corrupt a live pick.

Player injury status is a separate, already-automated system: the browser fetches it live from
Sleeper's public API on every page load (see `SLEEPER_CACHE_KEY` in `generate.py`). Nothing to do
there.

## The pipeline

1. **`raw_rankings.py`** -- hand-refreshed data pulled from fantasyfootballcalculator.com. Six
   blocks: `QB_RANKS`, `RB_RANKS`, `WR_RANKS`, `TE_RANKS`, `K_RANKS` (each `"Player - TEAM"` per
   line, rank order, sourced from `fantasyfootballcalculator.com/rankings/<qb|rb|wr|te|kicker>`),
   and `DEF_RANKS` (plain team names, sourced from `fantasyfootballcalculator.com/rankings/defense`
   -- fetch this one too, don't skip it: an earlier version of this file only had 7 of 32 teams
   ranked, named `DEF_RANKS_PARTIAL`, because whoever built it originally didn't fetch the full
   defense page). Also carries `TEAM_ABBR2` (team abbreviation -> full name) and
   `ALL_32_DEFENSES2`, which don't need to change season to season.

2. **`overall_adp.py`** -- `OVERALL_ADP`, a list of `(rank, name, team, pos)` tuples sourced from
   `fantasyfootballcalculator.com/adp/standard`. This is the *only* source for `overallRank`. The
   site's ADP list has a natural depth limit (217 rows as of the 2026-08-24 refresh) -- players
   past that point genuinely don't have a meaningful ADP yet, so `overallRank: null` for most of
   the pool is expected, not a bug. Note the source site labels kickers `"PK"`; normalize to
   `"K"` when transcribing so it matches everything else.

3. **`build_pool3.py`** -- rebuilds `pool.json` from `raw_rankings.py` alone (positional rank
   only, `overallRank` not yet set). Every player starts `status: "available"` -- this script
   must never hardcode any team's keep/protect state; see the docstring in the file for why.

4. **`match_overall_ranks.py`** -- run after `build_pool3.py`. Layers `overall_adp.py`'s ADP onto
   the pool by name (accent/suffix-normalized match), writing `overallRank`. Prints any ADP rows
   it couldn't match -- check these by hand. In the 2026-08-24 refresh this caught one real gap
   (Jayden Higgins, a rookie WR who was on the ADP page but missing from the WR rankings page
   fetch -- added back manually with `rank: null` since he had no positional rank available) and
   two legitimate drops (Ricky Pearsall -- knee injury, not expected to play; Theo Wease Jr. --
   released by his team) that were correctly *not* carried forward, since they're no longer
   actually draftable.

## How to actually refresh

```
python3 build_pool3.py
python3 match_overall_ranks.py
```

Both scripts resolve `pool.json` relative to their own location, so this works from wherever the
repo is checked out.

Before trusting the result: check `match_overall_ranks.py`'s "Unmatched ADP rows" output by hand
(each one is either a real gap worth fixing, like Jayden Higgins above, or a legitimately-dropped
player, like Pearsall/Wease above -- a quick web search settles which), then spot-check that every
name in `state.json`'s `keepers` block still has an exact match in the new `pool.json` (a name
spelling drift on the source site would silently break the Keep/Protect tracker for that player,
since `generate.py` does exact-string lookups). Then regenerate the live pages
(`python3 generate.py`) and grep the output for a keeper name or two to confirm `status`/
`pickInfo`/`protectedBy` still derive correctly from `state.json` against the new pool -- see the
2026-08-24 refresh in git history for exactly what that check looked like.

Ship it the same way as any other `pool.json`-only change: commit + push to `v2-live-app`, then
`tbml` on Web01.

## Don't forget the mock draft demo

`mock_state.seed.json` is a full, pre-simulated 12-round mock draft built from `pool.json` --
after a rankings/ADP refresh it's now drafting stale players unless you regenerate it too. Rerun
`python3 mock_draft.py` (also resolves paths relative to its own location) to rebuild it against
the current `pool.json`, then commit + push both `pool.json` and `mock_state.seed.json` together.
Deploying doesn't automatically pick this up on Web01, though -- `mock_state.json` (the live
working copy `/mock` actually serves) is separate from the seed and only gets overwritten when
someone hits "Reset mock draft" on `/mock/entry`. Tell Jon to do that after any deploy that
includes a refreshed `mock_state.seed.json`, same as reminding him to run `tbml` for anything
else.
