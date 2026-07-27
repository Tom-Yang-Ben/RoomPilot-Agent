# Recognition Test Data

Owner: Cody. Reviewers: Django for room/spatial labels and Ben for QA.

- Keep fixtures small, intentional, and attributable to a test.
- Separate source image, ground truth, and generated result.
- Do not overwrite human-reviewed labels with model output.
- Large training datasets and generated caches stay outside Git.
- Every fixture change must name the test or evaluation it supports.

