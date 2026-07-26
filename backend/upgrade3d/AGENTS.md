# Confirmed Layout to 3D Geometry

Owner: Cody. Collaborators: Ancai and Bella. Read `docs/owners/CODY.md`.

- Parse only confirmed DXF/layout data into 3D-ready geometry.
- Preserve scale, wall/opening identity, and centimeter normalization.
- Do not infer design choices or furniture placement.
- Coordinate changes require engine and scene regression tests.

Minimum tests: DXF unit tests, scene layout tests, and 3D visual contracts.

