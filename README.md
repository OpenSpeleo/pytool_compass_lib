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
`SurveyLeg.color` carries it through coordinate propagation and adjustment.
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
