# Traverse Adjustment

## Overview

When a Compass project has **two or more fixed anchor stations** (link stations
with known UTM coordinates), the BFS coordinate propagation creates a
**mixed-origin seam**: stations on one side of the meeting point get their
coordinates from Anchor A, stations on the other side from Anchor B. At the
meeting point, there is a massive positional discontinuity because measurement
errors accumulate differently from each anchor.

The **traverse adjustment** eliminates this seam by re-propagating the entire
network from a single anchor, then distributing the misclosure smoothly across
every station using a distance-weighted (Bowditch-like) correction.

## The Problem

```
Anchor A ---- s1 ---- s2 ---- s3 ---- s4 ---- Anchor B
              ↑ from A's BFS ↑  ↑ from B's BFS ↑
                        SEAM HERE
```

BFS starts from all anchors simultaneously. Each station is claimed by whichever
front reaches it first:

- `s1`, `s2` get coordinates propagated from A (small error near A, growing
  toward the middle).
- `s3`, `s4` get coordinates propagated from B (small error near B, growing
  toward the middle).
- The shot between `s2` and `s3` bridges two coordinate systems and shows a
  large, visible jump.

Side branches inherit the same problem: a spur off `s3` was positioned from B's
propagation and has B's accumulated error baked in.

## The Algorithm

Implemented in `compass_lib.solver.proportional.ProportionalSolver`.

For each connected pair of anchor stations (A, B):

### Step 1 — Re-propagate from A

Run a full BFS from anchor A through the network's undirected adjacency graph,
computing every station's position by summing measurement deltas from A's known
position. This produces **seam-free, consistent** positions — but with all
accumulated error landing at B:

```
measured_B = A_pos + sum(deltas along path to B)
```

### Step 2 — Compute misclosure

```
misclosure = measured_B - fixed_B
```

If `misclosure.length < 1e-9`, this pair needs no correction.

### Step 3 — Compute graph distances

Two BFS passes compute the cumulative shot-length distance from each anchor to
every station:

- `d_A[s]` = shortest graph-distance from A to station s
- `d_B[s]` = shortest graph-distance from B to station s

### Step 4 — Distance-weighted correction

For each non-anchor station `s`:

```
fraction = d_A[s] / (d_A[s] + d_B[s])
corrected[s] = re_propagated[s] - fraction * misclosure
```

This gives:

| Station position | fraction | Correction | |---|---|---| | At anchor A | 0 |
None (anchor is fixed) | | Near A | small | Almost no correction | | Midway |
0.5 | Half the misclosure | | Near B | large | Nearly full correction | | At
anchor B | 1 | Full correction (anchor is fixed, skipped) |

Side branches interpolate naturally: a station `E` on a spur off `B` has
`d_A = d_A(B) + dist(B,E)` and `d_B = dist(B,E)`, so its fraction reflects its
position in the overall network.

### Multiple anchor pairs

When more than two anchors exist, the solver iterates over all pairs
`combinations(sorted(anchors), 2)`. If a station receives corrections from
multiple pairs, the corrected positions are **averaged**.

## Architecture

```
compass_lib/solver/
├── __init__.py          # Public exports
├── base.py              # SurveyAdjuster (abstract base class)
├── models.py            # Vector3D, NetworkShot, Traverse, SurveyNetwork
├── noop.py              # NoopSolver (identity — no adjustment)
└── proportional.py      # ProportionalSolver (traverse adjustment)
```

### Key types

- **`SurveyAdjuster`** (`base.py`): Abstract base class. Subclasses implement
  `adjust(network) -> dict[str, Vector3D]`. Anchor stations must never be moved.

- **`SurveyNetwork`** (`models.py`): The solver's only input. Contains station
  positions (from BFS), shots with measurement-based deltas, and the set of
  anchor names. Built via `SurveyNetwork.from_computed_survey()`.

- **`NetworkShot`** (`models.py`): A single directed shot with a
  measurement-based delta vector and distance. The delta comes from the raw
  distance/azimuth/inclination measurements (with declination and convergence
  applied), **not** from coordinate differences.

- **`ProportionalSolver`** (`proportional.py`): The main solver. Contains
  `_bfs_propagate()` and `_bfs_distances()` helper functions for the
  re-propagation and distance computation.

### Integration with GeoJSON pipeline

```
geojson.py: compute_survey_coordinates()
  1. build_station_graph()      # adjacency from shots
  2. find_anchor_stations()     # fixed stations from MAK link stations
  3. propagate_coordinates()    # BFS from all anchors (may have seam)
  4. solver.adjust(network)     # ← traverse adjustment happens here
  5. Update station coordinates in-place
```

The solver is passed into `compute_survey_coordinates()`,
`project_to_geojson()`, and `convert_mak_to_geojson()` via the `solver=` keyword
argument. The CLI command `compass geojson` always uses `ProportionalSolver()`.

### Origin tracking (debug)

Each `Station` has an `origin` field that records which anchor's BFS front
reached it first. This is emitted as an `"origin"` property in GeoJSON features,
and a simplestyle `stroke` / `marker-color` is assigned per origin using the
`ORIGIN_COLORS` palette. This allows visual debugging of the BFS propagation
fronts.

## Design decisions

1. **Why re-propagate instead of correcting BFS positions?** BFS from multiple
   anchors creates mixed-origin positions. Applying a delta correction to
   mixed-origin positions doesn't fix the seam — it just shifts it.
   Re-propagation from a single anchor produces consistent positions that can
   then be corrected smoothly.

1. **Why distance-weighted instead of path-only Bowditch?** Traditional Bowditch
   distributes error along the traverse spine only. Side branches (spurs) would
   be left uncorrected. The distance-weighted approach `d_A / (d_A + d_B)`
   naturally handles every station in the network, including spurs, without
   needing to identify which stations are "on" the traverse.

1. **Why measurement deltas instead of coordinate differences?** Coordinate
   differences between consecutive BFS stations already incorporate propagation
   error from the anchor. Around a closed path they telescope to zero, masking
   the actual misclosure. Measurement deltas preserve the raw field measurements
   and reveal the true error.

1. **Why no loop closure?** Loop closure (distributing cycle misclosure) was
   removed to keep the solver focused on the anchor-to-anchor traverse problem,
   which is the primary source of visible error in multi-anchor projects. Loop
   closure may be re-introduced in the future as a separate pass.

## Testing

Unit tests are in `tests/test_solver.py`:

- `TestVector3D` — arithmetic on the 3D vector type
- `TestNoopSolver` — identity solver returns positions unchanged
- `TestProportionalSolver` — traverse adjustment:
  - Single anchor: no change
  - Perfect traverse (zero misclosure): no change
  - Anchors never move
  - Interior stations are adjusted
  - Correction is distance-weighted (closer to A = less correction)
  - Side-branch stations are adjusted
  - All stations present in output
- `TestSurveyNetwork` — adjacency list is undirected and cached

Integration tests in `tests/test_convert_roundtrip.py` compare GeoJSON output
against encrypted baseline files for ~40 real Compass projects.
