# GeoJSON section coloring

Each `CompassSurvey` block inside a DAT file receives one generated color. All
of that block's exported shots use it. Section names are not identifiers; repeated
names remain separate blocks. Two sections are adjacent when they share a station
in the existing solver graph, including MAK links and station scopes across DAT
files. Crossings without a shared station do not establish adjacency.

## Palette

`compass_lib/constants.py` owns `SURVEY_COLORS`: vivid red, orange, yellow, lime,
green, mint, cyan, blue, purple, and hot pink. Both this palette and additional
colors have at least 80% HSV saturation and 90% HSV value. Black, white, gray,
and muted shades are excluded. Ariane's recorded colors are independent of this
generated Compass palette.

## Bounded passes and safe exits

`assign_section_colors()` in `compass_lib/section_colors.py` uses ordinary
`random.choice`, with no seed, hashing, or algorithm version. It visits sections
in descending neighbor count. Each pass starts a fresh candidate assignment;
available colors exclude those already assigned to neighboring sections.

The allocator keeps the candidate only if it colors more sections than the best
previous pass. It stops when every section is colored, when a candidate makes no
improvement (including a worse candidate), or after `MAX_COLORING_PASSES`, which
defaults to 16. A worse candidate never replaces the best result. An empty project
is a no-op. The traversal is iterative and does not use Python recursion.

Any remaining sections receive distinct additional vibrant colors, excluding
every color already in use. If there are `R` unresolved sections and `U` distinct
used colors, inspecting at most `R + U` unique candidates is sufficient: at most
`U` can collide. This bound grows with the input instead of arbitrarily abandoning
adjacent sections after a fixed overflow limit. A zero pass budget still reaches
this fallback and colors all sections when the color space has enough capacity.

The additional-color iterator visits each 24-bit RGB value at most once and
filters out colors below the saturation/value limits. Its scan is finite. If the
entire usable RGB space is exhausted, no algorithm can give a larger clique
distinct colors; this exceptional case logs a warning and omits unresolved
colors instead of throwing or retaining stale colors. Consumers then use their
ordinary survey fallback, so the adjacency guarantee cannot cover that physical
color-space limit. Ordinary pass/no-improvement exits do not have this limitation.

## Export and persistence

Colors are derived metadata: `CompassSurvey.color` is excluded from DAT/MAK and
source JSON serialization. `SurveyLeg.color` carries the assignment through every
coordinate-propagation path. GeoJSON lines, passage polygons, and clipped passage
fragments receive `properties.color`. Processing and plotting exclusions remain
unchanged, as do coordinates, depths, feature identities, and source files.

The property is independent of `color_by_origin` and CLI `--no-colors`, which
control the existing origin-based simplestyle metadata. Nonadjacent sections may
share a color. A fresh export may choose different colors; a saved GeoJSON artifact
keeps its recorded colors until regenerated. Palette updates therefore require
artifact regeneration, not merely a browser reload or an unchanged source upload.

## Regression coverage

`tests/test_section_colors.py` checks chains longer than the recursion limit,
branches, cycles, disconnected sections, duplicate names, cross-DAT links and
scopes, crowded junctions, palette and overflow vibrancy, source serialization,
solver propagation, exclusions, clipped fragments, and CLI/API export.

Exit tests explicitly check first-pass completion, no improvement, preservation
of a better prior assignment, the hard pass limit while every pass improves,
zero-pass fallback, collisions with already-used colors, finite RGB enumeration,
and simulated complete color-space exhaustion without exceptions or stale colors.
Geographic baseline tests validate colors separately while still comparing all
original geometry and metadata. Private fixtures are additional coverage; the
allocator's portable cases need no private data.
