# Requirement and Selection Agent

Owner: Yen. Read `docs/owners/YEN.md`.

- Convert questionnaire evidence into structured requirements and ranked
  choices.
- Preserve room identity, user-selected furniture, and deferred choices.
- Return explanations and repair intents, never invented coordinates.
- Use Kai catalog records and Ancai legality results as authoritative inputs.
- LLM output must be validated into the local schema before use.

Minimum tests: agent selection/place/knowledge plus room requirement contracts.

