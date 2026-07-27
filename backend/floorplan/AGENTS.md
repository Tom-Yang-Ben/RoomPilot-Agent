# Floorplan Recognition

Owner: Cody. Spatial collaborator: Django. Read `docs/owners/CODY.md` and
`docs/owners/DJANGO.md`.

- Keep image evidence, confidence, and confirmed geometry separate.
- Normalize external output to centimeters.
- Color, grayscale, and scanned plans must pass through the explicit image
  profile route rather than one universal threshold.
- Cody adapters and model masks are inputs, not unquestioned ground truth.
- Do not add furniture placement or UI behavior here.

Minimum tests: vision, room evaluation, semantic status, and a matching fixture.

