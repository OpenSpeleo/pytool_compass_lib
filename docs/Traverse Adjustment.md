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

### Step 1 — Unclamped propagation & misclosure

Run a full BFS from anchor A through the network's undirected adjacency graph,
computing every station's position by summing measurement deltas from A's known
position. This produces **seam-free, consistent** positions — but with all
accumulated error landing at B:

```
measured_B = A_pos + sum(deltas along path to B)
misclosure = measured_B - fixed_B
```

If `misclosure.length < 1e-9`, this pair needs no correction.

### Step 2 — Compute graph distances

Two BFS passes compute the cumulative shot-length distance from each anchor to
every station:

- `d_A[s]` = shortest graph-distance from A to station s
- `d_B[s]` = shortest graph-distance from B to station s

### Step 3 — Clamped re-propagation

A second BFS from A re-propagates the network, but this time each shot receives
a proportional share of the misclosure correction **clamped in polar
coordinates**:

For each edge (current → neighbor) in BFS order:

1. Compute graph-distance fractions `f_current`, `f_neighbor`.
1. Ideal correction for this shot:
   `correction = (f_neighbor - f_current) * misclosure`.
1. Corrected delta: `new_delta = survey_delta - correction`.
1. Decompose both the survey delta and the corrected delta into polar:
   `(length, compass_heading, inclination)`.
1. **Clamp** each component:
   - Length: `new_length` within `[0.95 * survey_length, 1.05 * survey_length]`
   - Heading: change ≤ 15 % of the survey compass reading (floor 2 °)
   - Inclination: change ≤ 15 % of |survey inclination| (floor 2 °)
1. Reconstruct the clamped cartesian delta and propagate:
   `pos[neighbor] = pos[current] + clamped_delta`.

This guarantees every shot's effective compass heading and tape length stay
within tolerance of the **original survey reading**, while distributing as much
error as those limits allow.

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

- **`ProportionalSolver`** (`proportional.py`): The main solver. Uses
  `_bfs_propagate()` and `_bfs_distances()` for the unclamped propagation and
  distance computation, then `_clamped_propagate()` for the per-shot polar-
  clamped re-propagation. Polar helpers `_to_polar()` / `_from_polar()` convert
  between cartesian deltas and survey-style (length, bearing, inclination).

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

## Per-shot polar clamping (current implementation)

The solver now enforces that every individual shot stays close to its **original
survey reading**. After computing the ideal proportional correction for each
shot, the corrected delta is decomposed into polar coordinates (tape length,
compass heading, inclination) and each component is clamped independently:

- **Length**: clamped to ±5 % of the survey tape distance (configurable via
  `max_length_change`).
- **Compass heading**: clamped to ±15 % of the survey compass reading, with a
  floor of 2 ° for near-north headings (configurable via `max_angle_change`).
- **Inclination**: clamped to ±15 % of the survey inclination, with a 2 ° floor
  for near-horizontal shots.

The clamped delta is reconstructed back to cartesian and used to propagate the
next station's position. This is done **per shot during BFS propagation**, so
each shot is independently limited — a wild correction on one shot does not
affect others.

### Constructor parameters

```python
ProportionalSolver(
    max_length_change=0.05,   # 5 % of survey tape distance
    max_angle_change=0.15,    # 15 % of survey compass / inclination
)
```

Both parameters are **fractions**, not degrees. A value of `10.0` (1000 %)
effectively disables clamping.

## Evolution of the clamping strategy

The per-shot polar clamping went through several design iterations before
arriving at the current implementation.

### Attempt 1 — Global linear scale-back

The first approach computed a single global scale factor `s` in `[0, 1]` and
applied `s * misclosure` to all stations. For each shot, the correction to its
delta was `(f_to - f_from) * s * misclosure`; the factor `s` was chosen as the
minimum of `max_ratio / actual_ratio` across all shots.

**Problem**: the ratio `max/actual` is a *linear approximation* that assumes the
length and angle change are proportional to `s`. This is only exact when the
correction is perfectly aligned with the shot direction. For off-axis
corrections (misclosure perpendicular to a shot), the relationship is nonlinear.
The linear estimate was too generous: the solver would pick a scale factor that
*should* give 5 % length change, but the actual change was 8–12 %, leaving shots
wild.

### Attempt 2 — Global binary-search scale-back

To fix the nonlinearity, the linear approximation was replaced with a binary
search (50 iterations) over `s`. For each shot, the function checked whether
scale `s` kept the corrected delta within the 3-D angular and length limits of
`shot.delta`, converging to the exact boundary.

**Problem**: global scaling is inherently the wrong tool. Scaling the entire
misclosure by a single factor means *all* shots receive a proportionally smaller
correction. If one shot near an anchor needs heavy clamping, the entire network
gets under-corrected. The user reported that "the shot at the anchor is insane"
while "you don't correct enough the other shots."

### Attempt 3 — Global scale-back against survey deltas (no GeoJSON values)

A refinement ensured the constraint was always checked against the *original
survey measurement* (`shot.delta`, derived from tape/compass/inclination), never
against the GeoJSON-computed effective delta (which can be wild at BFS seams).
The "gets worse" heuristic (only clamp shots whose correction moves them
*further* from the survey reading) was removed so the constraint was
unconditional.

**Problem**: still global scaling — one bad shot starves all others of
correction.

### Attempt 4 — Per-shot polar clamping (current)

The fundamental change: instead of finding a single scale factor, **each shot is
clamped individually** during BFS propagation. The corrected delta for each edge
is decomposed into polar coordinates (tape length, compass heading,
inclination), each component is clamped to ±5 %/±15 % of the original survey
reading, and the clamped delta is reconstructed. This means:

- Shots that need little correction get their full share of error distribution.
- Shots where the proportional correction would distort the survey measurement
  beyond tolerance are individually limited.
- No single shot can go wild regardless of how large the misclosure is.
- The trade-off: if many shots are clamped, the total distributed correction may
  be less than the full misclosure, leaving a small residual at the far anchor.
  In practice this residual is small for well-surveyed networks.

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

1. **Why per-shot polar clamping instead of global scaling?** Global scaling
   (attempts 1–3) treats all shots identically. When one shot has a correction
   that would distort its survey reading, scaling back the entire misclosure
   starves every other shot of correction. Per-shot clamping lets each shot
   absorb as much correction as its survey tolerances allow, independently.

1. **Why clamp in polar (heading/inclination/length) instead of cartesian?**
   Cave surveyors think in terms of compass readings and tape distances. A ±15 %
   tolerance on the compass heading is directly interpretable: a shot surveyed
   at 200° will never be adjusted beyond roughly 170°–230°. Clamping a 3-D angle
   between cartesian vectors has no such intuitive meaning and conflates heading
   and inclination changes.

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
  - Per-shot clamping limits length change to ±5 %
  - Clamped corrections are smaller than unclamped
  - Clamped and unclamped corrections point the same way
  - Small misclosure triggers no clamping
  - Large off-axis misclosure is correctly handled
  - Tighter custom limits produce smaller corrections
- `TestSurveyNetwork` — adjacency list is undirected and cached

Integration tests in `tests/test_convert_roundtrip.py` compare GeoJSON output
against encrypted baseline files for ~40 real Compass projects.
