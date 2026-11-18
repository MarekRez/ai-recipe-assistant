# Test Plan

## Scope

Validate extraction quality, schema adherence, Notion integration, and tool-driven agent behavior.

## Test Data

1. 10-15 representative recipe samples.
2. Mix of short, long, complete, and partially specified recipes.

## Test Areas

1. Extraction accuracy

- Check name, ingredients, quantities, units, instructions, and times.

2. Schema validity

- Metric: `valid_outputs / total_outputs`.

3. Hallucination control

- Verify no invented ingredients, quantities, or times.

4. Notion integration

- Verify create and retrieve operations.

5. Agent search behavior

- Validate queries like vegetarian under 30 min, chicken, pasta.

## Minimal Automation Strategy

1. Unit tests for schema and parser output normalization.
2. Service tests for Notion mapping payload.
3. Agent tests with mocked tool outputs.
