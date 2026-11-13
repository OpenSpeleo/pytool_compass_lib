# Loop closure

`compass_lib.loop_closure` adapts survey data to the Gaussian and inverse-length
weighted L1 solvers in `cave_closure`. With the Gaussian method, it normalizes
original DAT observations. Every repeated and reversed measurement remains a
separate observation. C flags preserve exact displacement; X flags exclude
processing. Display flags do not remove numerical evidence.

`LoopClosure` supplies a `LoopClosureMode`, positive `sigma_m`, and a
`LoopClosureAlgorithm`. It is passed as `loop_closure=` to
`compute_survey_coordinates`, `project_to_geojson`, and
`convert_mak_to_geojson`. The algorithm choices are `LSE_REDUCED_PCG`,
`LSE_UNREDUCED_PCG`, `LSE_SPARSE_QR`, and `LSE_SPARSE_CHOLESKY`. `None` requests
raw geometry.

The preparation uses complete source observations rather than a deduplicated
network reconstructed from drawn legs. Hard ENU anchors remain fixed. Horizontal
loop closure preserves each station's Z. Frame corrections use explicit
per-survey values when supplied, otherwise the geographic calculation's cached
declination and convergence. `sigma_m` declares independent Cartesian placement
uncertainty; it does not infer instrument precision or implement robust
weighting.

`compass geojson --algorithm LSE_SPARSE_QR --mode spatial --sigma-m 1` selects
an algorithm. `--raw` bypasses loop closure. All algorithms minimize the same
Gaussian objective. They do not clamp changes or identify blunders.

Regression tests exercise original measurement preservation, hard controls,
repeated observations, source flags, section colors, all four algorithms, and
CLI exports. Numerical reference tests belong to `cave_closure`.

## Inverse-length weighted L1 preset

`compass_lib.preset.InverseLengthWeightedL1SpatialSolver` is a premade frozen
`LoopClosure` instance, also exported from `compass_lib`. It reproduces the
algorithm formerly implemented by Compass-lib's `SparseSolver`, which called
SciPy's HiGHS linear-programming backend. The solver now lives entirely in
`cave-closure/src_rust/l1.rs`. It is used by the legacy GeoJSON baseline
comparisons in `tests/test_convert_roundtrip.py`; no baseline files are changed.

```python
from compass_lib import InverseLengthWeightedL1SpatialSolver
from compass_lib.geojson import compute_survey_coordinates

closed = compute_survey_coordinates(
    project,
    loop_closure=InverseLengthWeightedL1SpatialSolver,
)
```

The preset explicitly sets spatial mode, the inverse-length weighted L1 method,
a length floor of 0.1 metres, a minimum of two anchors, first-observation
undirected edge deduplication, and no iteration limit. Gaussian-only `sigma_m`
and `algorithm` are `None`. Frame corrections default to those already used by
the geographic calculation. Customize it with `dataclasses.replace`; shared
presets remain immutable.

This compatibility method consumes the propagated survey graph and its original
measurement deltas. Station identity uses the scoped mapping keys, recovered
from leg endpoint objects, so identically named stations in different file
scopes remain distinct. Orphan anchors are omitted from the request. The Python
adapter copies IDs, endpoints, positions, controls, and options, then calls
`solve_l1_loop_closure_json` once. Rust handles missing-delta fallback,
deduplication, anchor centering, weights, all three axis solves, and convergence
checks. Fewer than two anchors preserves the initial coordinates. Solver failure
raises rather than fabricating a corrected survey. The Gaussian source method
continues to retain repeated measurements and protected-displacement
constraints; those source policies do not describe the legacy graph preset.
