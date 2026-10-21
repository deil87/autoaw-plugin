# `.awf` 1.1 — the workflow file

One JSON document, one workflow. 1.1 adds `source`, `tunable`, `anchors` and
`eval` to the 1.0 envelope AutoAW exports. A 1.0 file is still valid to read,
but it carries nothing tunable, so it cannot be optimised.

```json
{
  "awf_version": "1.1",
  "kind": "AgenticWorkflow",
  "metadata": {
    "name": "support-triage",
    "description": "Classify a ticket, then draft a reply. lookup_order() is a Python tool, simulated during the run."
  },
  "source": {
    "framework": "crewai",
    "framework_version": "0.86.0",
    "language": "python",
    "entrypoint": "src/triage/crew.py",
    "commit": "abc1234",
    "files": [{ "path": "src/triage/config/agents.yaml", "sha256": "…" }]
  },
  "workflow": {
    "id": "support-triage",
    "topology": "fixed_pipeline",
    "agents": [
      { "id": "classifier", "role": "Ticket classifier", "model": "gpt-4o-mini",
        "system_prompt": "…verbatim…", "temperature": 0.7 },
      { "id": "responder", "role": "Support responder", "model": "gpt-4o-mini",
        "system_prompt": "…verbatim…", "temperature": 0.7 }
    ],
    "edges": [{ "from": "classifier", "to": "responder", "type": "sequential" }],
    "topology_params": {}
  },
  "tunable": [
    "agents.classifier.model", "agents.classifier.system_prompt", "agents.classifier.few_shot",
    "agents.responder.model", "agents.responder.system_prompt"
  ],
  "anchors": {
    "agents.classifier.model": {
      "file": "src/triage/config/agents.yaml", "line_start": 4, "line_end": 4,
      "kind": "yaml_key", "locator": "classifier.llm", "original": "openai/gpt-4o-mini"
    },
    "agents.classifier.few_shot": {
      "file": "src/triage/config/tasks.yaml", "line_start": 3, "line_end": 3,
      "kind": "insertion_point", "locator": "classify_task.description"
    }
  },
  "eval": {
    "rows": [
      { "id": "t01", "input": "My invoice shows two charges", "expected": "billing", "stratum": "billing" }
    ],
    "evaluators": [{ "type": "reference", "params": { "metric": "exact_match" } }],
    "candidate_models": ["gpt-4o-mini", "openai/gpt-oss-120b@high"],
    "objective_weights": { "quality": 0.8, "cost": 0.15, "speed": 0.05 },
    "task_description": "Classify support tickets and draft replies."
  }
}
```

## `workflow`

| field | meaning |
|---|---|
| `id` | a slug for the workflow |
| `topology` | `fixed_pipeline` if the code runs steps in a set order or graph. `ai_orchestrated` if an LLM decides who runs next (a CrewAI hierarchical manager, OpenAI Agents handoffs, a LangGraph supervisor). |
| `agents[]` | one entry per **LLM call site**. `id` is a stable slug, `role` is one line, and `model`, `system_prompt` and `temperature` are copied verbatim. Leave `temperature` out if the code does not set it, rather than guessing. |
| `edges[]` | `{from, to, type: "sequential"}` for each hand-off of output from one agent to the next |
| `topology_params` | `{}` |

## `tunable` and `anchors`

A path is written `agents.<agent id>.<field>`. The field is one of `model`,
`temperature`, `system_prompt` or `few_shot`. One more path, `workflow.structure`,
records where the agents are wired together. Structure is always searched; the
path only gives a confirmed "remove this agent" result a location, so anchor it
with kind `graph_wiring`.

| `kind` | when |
|---|---|
| `yaml_key` | the value is a YAML key. Set `locator` to the dotted key, e.g. `classifier.backstory`. |
| `constructor_arg` | a keyword argument, e.g. `ChatOpenAI(model=...)`. Set `symbol` to the enclosing function or class. |
| `string_literal` | a string constant or literal holding a prompt |
| `env_var` | the value comes from an environment variable. Set `locator` to the variable name. The change then goes to wherever the variable is defined, such as `.env.example`, deploy config or docs. |
| `file` | the whole file is the prompt, e.g. `prompts/analyst.md` |
| `insertion_point` | `few_shot` only: the last line of the text the demos should follow, such as the end of a task description or the line that builds the message list |
| `graph_wiring` | `workflow.structure` only: the lines that connect the agents, such as a LangGraph builder's `add_node`/`add_edge` calls, a CrewAI crew's `tasks=[...]`, or the sequence of calls in plain SDK code. Set `symbol` to the enclosing function. |

Line numbers are 1-based and inclusive. For a multi-line value, cover every
line of it. For an `insertion_point`, point at the last line of the text the
demos follow. Use `locator` for a key path in a config file, and `symbol` for
a Python or TS function or class.

An anchor locates the **source** piece, and that can differ from the `.awf`
value: an assembled CrewAI prompt, or a prompt whose input placeholder was
rewritten. At apply time the skill checks that the piece is still at the
anchor (by `locator` or `symbol`) and edits it there. It does not search for
the `.awf` text.

Set `original` on a `model` anchor when the code spells the id differently
from the `.awf`, e.g. `openai/gpt-4o-mini` in the code and `gpt-4o-mini` in
the `.awf`. The result is then written back in the code's spelling.

A missing anchor is allowed (you get a warning), but the change then comes
back with no location attached.

## How a row runs

The row's `input` is the first agent's user message. Each later agent receives
the previous agent's output as its user message. The last agent's output is
scored. Template variables in prompts are not filled; see SKILL.md step 2.

## `eval`

`rows` is required, from 1 to 500 rows, each with a non-empty `input`. Add
`expected` and a `stratum` where you have them, and an `id` if the rows have a
natural one.

| evaluator `type` | when |
|---|---|
| `reference` | rows carry `expected`. `params.metric` is `exact_match` (labels, classes), `f1` (free text) or `numeric`. If no evaluator is named and rows carry `expected`, it defaults to `f1`. `exact_match` trims, lowercases and collapses whitespace, and nothing else: `"Billing."` does not match `billing`. Make the last agent's prompt demand the bare label. |
| `llm_judge` | no gold answers. `params.rubric` is required and written with the user. `params.model` is optional. |
| `deepeval_*`, `ragas_*` | RAG and faithfulness metrics |

Other evaluator types are refused for imported workflows.
