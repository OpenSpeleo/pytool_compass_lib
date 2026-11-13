# Compass Python Lib

## Conversion commands:

```bash
# Install in dev mod
pip install -e ".[dev,test]"

# Install latest stable version
pip install compass_lib

# run some commands
compass convert --input_file=./tests/artifacts/fulford.dat  --output_file=fulford.json --format=json --overwrite
compass convert --input_file=./tests/artifacts/random.dat  --output_file=random.json --format=json --overwrite
```

## GeoJSON section colors

GeoJSON survey legs include `properties.color`, an opaque CSS `#rrggbb` color.
Every shot in a DAT survey block receives the same generated section color.
Sections sharing a station have different colors, including across MAK-linked
DAT files. Names alone do not identify sections or station connections: the
existing MAK station-scoping rules remain authoritative. Geometric crossings
without a shared station do not create a color constraint.

The palette lives in `compass_lib/constants.py` as `SURVEY_COLORS`: vivid red,
orange, yellow, lime, green, mint, cyan, blue, purple, and hot pink. Both
palette colors and generated overflow colors have HSV saturation of at least 80%
and value of at least 90%, excluding black, white, gray, and muted shades.

Assignment uses ordinary random choices in at most 16 iterative passes, without
hashing, a fixed seed, or algorithm versioning. It stops on completion or no
improvement. Remaining sections receive distinct vibrant colors using a finite
fallback budget sized to the input, so reaching the pass limit does not leave
touching sections with the same viewer fallback color. Colors can change when
GeoJSON is regenerated and remain fixed in each stored artifact.

See [GeoJSON section coloring](docs/geojson-section-colors.md) for pass
semantics, fallback bounds, the color-space limit, export behavior, and test
coverage.

`CompassSurvey.color` is derived metadata assigned during coordinate
computation; it is excluded from source JSON and DAT/MAK serialization.
`SurveyLeg.color` carries it through coordinate propagation and loop closure.
Passage polygons and clipped passage fragments inherit their leg's color.
Station/anchor and misclosure styling retain their existing semantics.

The `color` property is independent of `color_by_origin` and CLI `--no-colors`,
which still control origin-based simplestyle `stroke`/`marker-color` styling.
Clients can use `color` for shot rendering and fall back to the survey color for
legacy data without it. Existing saved GeoJSON must be regenerated to gain these
properties; no source files are rewritten. Palette changes also require
regenerating stored GeoJSON; existing artifacts retain the colors recorded when
they were exported.

Portable regression coverage lives in `tests/test_section_colors.py`, including
duplicate names, linked/scoped stations, crowded junctions, solver paths, round
trips, CLI/API exports, vibrant colors, and safe budget exhaustion. Private
fixtures remain additional coverage and are never required for these guarantees.

## Loop closure

`compass_lib.loop_closure.LoopClosure` provides Gaussian WLS with explicit
`mode`, positive `sigma_m`, and per-survey `(declination, convergence)` values
keyed by `(file_name, survey_index)`. The pure
`compass_lib.loop_closure.prepare_loop_closure` API accepts the same inputs plus
caller-supplied ENU controls and a complete horizontal preserved-Z map.
`cave_closure` is a required dependency installed with the package.

`compass_lib.preset.InverseLengthWeightedL1SpatialSolver` reproduces the former
Compass-lib `SparseSolver` using the native HiGHS backend in `cave_closure`.
Pass it as `loop_closure=InverseLengthWeightedL1SpatialSolver` to the GeoJSON or
coordinate APIs. It is an immutable `LoopClosure` instance, with every setting
specified explicitly. It closes the propagated XYZ graph using inverse-length
weighted absolute errors and preserves the legacy GeoJSON baselines. Unlike the
Gaussian configuration below, it keeps the first observation for each undirected
station pair. See [loop closure](docs/Loop%20Closure.md) for its origin and
settings.

Raw parsed observations provide measurements; propagated positions never replace
them. Every repeated and reversed shot remains distinct. C protects normalized
active-dimensional displacement with an exact offset. X excludes processing; P
and L remain factors. One distance with redundant angles produces one factor,
using frontsight components with reversed-backsight fallback. `sigma_m` declares
independent isotropic Cartesian placement noise, not inferred instrument
accuracy. W-format does not supply absolute depth readings.

DAT calibration follows the vendor's compass, inclinometer, tape ordering in
[the native format specification](https://fountainware.com/compass/HTML_Help/Compass_Editor/surveyfileformat.htm).
Parser and formatter now use that order, retain backsight-only calibration, and
reverse-backsight inclination keeps its native signed reverse direction.
Calibration changes affect derived observations without overwriting raw
readings. Historical JSON generated by the old parser can contain mislabeled
correction values: reparse original DAT input or migrate only with known source
provenance. The adapter does not silently reinterpret named JSON fields.

GeoJSON APIs accept `loop_closure=LoopClosure(...)`. The CLI uses `--algorithm`
with the four enum member names; `--mode` selects dimensions and `--sigma-m`
declares placement uncertainty. `--raw` exports unadjusted geometry. The default
CLI and web loop closure is Gaussian reduced PCG. Frame corrections can be
supplied explicitly or reused from the per-survey geographic calculation.

Import `LoopClosureMode` and `LoopClosureAlgorithm` directly from
`cave_closure`. Preparation accepts
`algorithm=LoopClosureAlgorithm.LSE_REDUCED_PCG` (the default),
`LSE_UNREDUCED_PCG`, `LSE_SPARSE_QR`, or `LSE_SPARSE_CHOLESKY`. The algorithm
selects the least-squares solver independently of
`mode=LoopClosureMode.HORIZONTAL` or `mode=LoopClosureMode.SPATIAL`.
