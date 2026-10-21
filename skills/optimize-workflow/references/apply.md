# Applying an AutoAW result

`get_result` returns `changes[]`. Each change has a `path`, `from`, `to`,
`portability` and `anchor`, plus extra fields depending on the field it changes.
Apply exactly these changes. Never apply anything listed under `withheld`.

## Before each edit

Open `anchor.file` at `line_start`–`line_end` and confirm that the value is
still there. For a model, check `from_literal` (or `from`). For a prompt,
check the anchored piece, e.g. the CrewAI task description, not the whole
assembled prompt. The change's `from` is the `.awf` text, which may have been
assembled or had its placeholder rewritten, so it won't appear verbatim in the
file. An appended text goes at the end of the anchored piece. If the code has moved,
search the file for the `from` value. If it is found exactly once, edit it there
and tell the user the line moved. If it is found zero times or several times,
skip the change and report it.

## By field

**`model`** (direct). Replace the model id at the anchor. When `from_literal`
is set, that is the spelling in the code to look for. Write the new id the way
the user's provider spells it, which is not always the AutoAW id with a
prefix: `openai/gpt-oss-120b` is gpt-oss hosted on Nebius, so under LiteLLM it
may be `nebius/openai/gpt-oss-120b`. When unsure, ask. AutoAW ids need
mapping to whatever the user's code passes:

| AutoAW id | meaning | usual client spelling |
|---|---|---|
| `gpt-4o`, `gpt-4o-mini`, `gpt-5*` | OpenAI | the same, or `openai/gpt-4o-mini` (LiteLLM and CrewAI) |
| `openai/gpt-oss-120b@high` | gpt-oss-120b served by Nebius, at high reasoning effort | provider-specific. Ask the user which host they use. `@high` maps to `reasoning_effort="high"` where the client supports it, or is dropped otherwise. |
| `claude-*` | Anthropic | the same id, or `anthropic/<id>` under LiteLLM |

If the user cannot deploy the new model, do not apply this change. Note that
the measured win depended on it.

**Reasoning effort (`@high`).** The win was measured at that effort, so carry
it over where the client can set it: `reasoning_effort="high"` on the model
object (OpenAI SDK, LiteLLM, `ChatOpenAI`, CrewAI `LLM(...)`). A plain model
string can't carry it; CrewAI's YAML `llm:` is one. Then either move that
agent's model into code, or drop the suffix and tell the user the applied
config differs from the measured one.

**`temperature`** (direct). Set the number at the anchor, adding the argument if
the code relied on the default.

**`system_prompt`** (direct). When `append` is set, add that text to the end of
the anchored prompt, separated by a blank line. In YAML block scalars, keep the indentation, and remember what the text parses
to. In a literal `|` scalar, one empty line is a blank line. In a folded `>`
scalar, it takes **two** empty lines to make one blank line, because a single
empty line folds to a newline. When `append` is null, the full `to` text replaces the
prompt. Keep any template variables (`{topic}`, `{{ input }}`) exactly as they
are.

**`few_shot`**: every few-shot change carries `reference_code`, with
`select_examples()` and `render_examples()`. **Copy it verbatim**. It is the
exact rule that was measured, and a "similar" tokeniser or tie-break is a
different configuration.
- Examples file: write the labelled examples to a runtime data file next to
  the code (e.g. `config/examples.json`), mapped to the keys the code expects,
  `{"id", "input", "expected"}`. Don't point runtime code at `tests/`.
- Placement: the rendered block goes **before** the input, with a blank line
  between them. Where the input sits inside the anchored text (a CrewAI
  description holding `{ticket}`), insert the block just above that line.
  Otherwise put it at the start of the user message.
- `direct` with `demos`: the selection is fixed; `select_examples` with
  `selection="random"` over those demos gives the same result.
- `recipe`: call `select_examples` per run with the current input.
- A `note` on the change (an agent that is not the last step) describes what
  was measured. Pass it on to the user.
- `to: "none"`: remove the demonstrations at the insertion point.

**`workflow.structure`** (manual). `op` is `remove_agent`, `agent` names the
step, and `rewire` says what its neighbour now reads: `{from, to}`, where `INPUT`
is the workflow input and `OUTPUT` its result. Read `instruction`, show the user
the edit at the `graph_wiring` anchor, and wait for a yes. Then remove the
step's call, node or task, and connect `from` to `to` in the framework's idiom:
one `add_edge` in LangGraph, one fewer task in a CrewAI list, one fewer call in
the sequence. Keep any non-agent step that sat between them. Leave the removed
agent's prompt and model in place unless the user asks for them to be deleted.
Without an anchor, find the wiring by the agent's name and say that you did.

## After

Run the tests. If there are none, or the framework is not installed here,
say so plainly. Don't describe the change as verified. A selector you added is
new code: offer a test for it. Show the diff, grouped by change. Say which experiment the
changes came from and the evidence line, e.g. "quality 0.61 → 0.74 on 40 rows,
single run". Do not commit unless asked.
