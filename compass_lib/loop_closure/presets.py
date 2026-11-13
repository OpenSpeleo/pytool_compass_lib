"""Premade immutable configurations of the generic LoopClosure type."""

from cave_closure import LoopClosureMode

from compass_lib.loop_closure import LoopClosure
from compass_lib.loop_closure import LoopClosureMethod

# Origin/software: Compass-lib's former SparseSolver, which used SciPy's HiGHS
# linear-programming backend to minimize inverse-length weighted absolute errors.
# Use for full XYZ closure of the propagated survey graph with fixed anchors,
# first-observation undirected deduplication, a 0.1 m length floor, and no closure
# below two anchors. All weighting, centering, deduplication, and optimization
# now run in cave-closure/src_rust/l1.rs through one bulk call.
# Used by the legacy GeoJSON baseline comparisons in test_convert_roundtrip.py;
# the existing baseline artifacts remain unchanged.
InverseLengthWeightedL1SpatialSolver = LoopClosure(
    mode=LoopClosureMode.SPATIAL,
    sigma_m=None,
    algorithm=None,
    frame_corrections=None,
    method=LoopClosureMethod.INVERSE_LENGTH_WEIGHTED_L1,
    name="InverseLengthWeightedL1SpatialSolver",
    length_floor_m=0.1,
    minimum_anchor_count=2,
    deduplicate_edges=True,
    max_iterations=None,
)
