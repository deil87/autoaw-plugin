# OpenAI Agents SDK

## Where things live

```python
from agents import Agent, Runner, ModelSettings
triage = Agent(
    name="Triage",
    instructions="...",                  # str, or a function(ctx, agent) -> str
    model="gpt-4o-mini",
    model_settings=ModelSettings(temperature=0.3),
    handoffs=[billing_agent, tech_agent],
    tools=[lookup_order],
)
result = await Runner.run(triage, input)
```

## Mapping to `.awf`

- **One `.awf` agent per `Agent(...)`.** `id` is a slug of `name`.
- `system_prompt` is `instructions`, verbatim. When `instructions` is a
  function, extract the text it returns. If that text depends on run context,
  pick the common case and note it in `metadata.description`.
- `model`: the `model=` argument. When it is unset, the SDK uses its default
  (`OPENAI_DEFAULT_MODEL`, or the SDK's built-in default); use an `env_var`
  anchor or ask the user.
- `temperature`: `model_settings.temperature`.
- `topology`:
  - Handoffs → `ai_orchestrated`. The agent passed to `Runner.run` is the entry
    point and goes first in `agents`. Add one edge from that agent to each
    handoff target.
  - Agents used as tools (`agent.as_tool(...)`) or chained in code →
    `fixed_pipeline`, with edges in call order.
- Function tools (`@function_tool`) are not agents. List them in
  `metadata.description`.
- Guardrails (`input_guardrails`, `output_guardrails`) that call an LLM are
  agents of their own. Include them only if the user wants them tuned.

## Anchors

| path | anchor |
|---|---|
| `…model` | `constructor_arg` on `model=` in `Agent(...)` |
| `…system_prompt` | `string_literal` on `instructions=`, or on the returned string when it is built by a function |
| `…few_shot` | `insertion_point` on `instructions`. Demos are appended as an "Examples" block, since the SDK has no separate few-shot slot. |
| `…temperature` | `constructor_arg` on `ModelSettings(temperature=…)` |
