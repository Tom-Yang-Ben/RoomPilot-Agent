# Spatial Data Boundary

Owner: Django. Read `docs/owners/DJANGO.md`.

This folder is the canonical home for reusable spatial relationships and layout
evaluation schemas. It currently contains no runtime implementation; add code
only after the producer/consumer contract is documented.

- Inputs are confirmed or confidence-tagged floorplan geometry.
- Outputs may include dimensions, area, adjacency, opening relationships, and
  evaluation evidence.
- Graph RAG can retrieve these relationships but cannot decide geometry.
- Coordinate output is centimeters; area output is square meters.

Changes require Cody producer tests and Bella/Ancai consumer tests.

