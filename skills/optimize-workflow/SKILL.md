---
name: optimize-workflow
description: Optimise an agent workflow that already exists in this codebase (CrewAI, LangGraph, LangChain, OpenAI Agents SDK, AutoGen, LlamaIndex, PydanticAI, smolagents, DSPy, or plain SDK calls) with AutoAW. Extracts the workflow into an .awf file with anchors to the exact lines each prompt/model lives on, builds an eval set, imports it over the AutoAW MCP server, runs a smoke test then the optimisation, and applies the measured changes back to the code. Use when the user wants to improve, tune, benchmark or cut the cost of their existing agents/crew/graph with AutoAW, or asks to apply an AutoAW result.
---

# Optimise an existing workflow with AutoAW

You turn the agent workflow in this repo into an `.awf` file, send it to AutoAW,
and later apply what AutoAW measured back into the code. AutoAW never sees the
source. It sees prompts, settings, eval rows and file hashes, and it returns
changes pinned to the file and lines you recorded.

The steps are below. Do them in order and don't skip the gates. Each gate is
there because skipping it has produced a confident number that measured nothing.

## 0. Preconditions

- The `autoaw` MCP tools must be available (`validate_awf`, `import_workflow`,
  `start_optimization`, `get_status`, `get_result`). If they are missing, send
  the user to https://autoaw.app/connect. That page has the endpoint, a token
  to export as `AUTOAW_TOKEN`, and the `claude mcp add` command. The token
  expires hourly. A 401 means the user should refresh it there.
- Keep all working state in `.autoaw/` at the repo root: `workflow.awf` and
  `state.json`. Suggest adding `.autoaw/` to `.gitignore`, because the eval rows
  may be sensitive.
- If `.autoaw/state.json` already has an `experiment_id`, the user may be
  resuming. Ask before starting a new import.

## 1. Detect the framework

Read the dependency manifests (`pyproject.toml`, `requirements*.txt`,
`package.json`) and the imports. Then read the matching guide **before
extracting**:

| framework | signal | guide |
|---|---|---|
| `crewai` | `crewai`, `@CrewBase`, `agents.yaml` | [references/frameworks/crewai.md](references/frameworks/crewai.md) |
| `langgraph` / `langchain` | `StateGraph`, `ChatOpenAI`, `ChatPromptTemplate` | [references/frameworks/langgraph.md](references/frameworks/langgraph.md) |
| `openai_agents` | `from agents import Agent, Runner` | [references/frameworks/openai_agents.md](references/frameworks/openai_agents.md) |
| anything else | `autogen`, `llama_index`, `pydantic_ai`, `smolagents`, `dspy`, raw SDK calls | [references/frameworks/generic.md](references/frameworks/generic.md) |

If the repo holds several workflows, ask which one to optimise. One `.awf` holds
one workflow.

## 2. Extract the workflow, with anchors

Follow the framework guide to fill `workflow` (agents, edges, topology). The
format is in [references/awf-1.1.md](references/awf-1.1.md). Rules:

- **Copy every value verbatim** from the code: prompts, model ids,
  temperatures. Do not paraphrase a prompt. The run measures the text you
  send, and a changed prompt makes the control a different workflow. For
  YAML, "verbatim" means the parsed value, not the raw lines: a folded `>`
  scalar becomes one line, with the trailing newline dropped.
- **Input wiring.** AutoAW sends each eval row's `input` to the **first** agent
  as its user message. Each later agent gets the previous agent's output as its
  user message, and the **last agent's output is what gets scored**. AutoAW
  does not fill template variables. Where a prompt has an input placeholder
  like `{ticket}` or `{{ input }}`, replace it with a short reference such as
  "(the ticket is in the user message)", and say so in
  `metadata.description`. Also fix prose that says where an input sits. For
  example, "the ticket summarized above" becomes "the ticket summary in the
  user message". Leave non-input variables as they are, but warn the
  user that they reach the model unfilled.
- **Model ids use AutoAW's spelling**: `gpt-4o-mini`, not
  `openai/gpt-4o-mini`. A provider-qualified id is otherwise sent to the
  wrong host and every row scores 0. Put the literal from the code in the
  anchor's `original` field, so the result can be written back in the user's
  spelling. The server also normalises and warns, but don't rely on that.
- **Record an anchor for every value that may change**: its file (repo-relative),
  `line_start`/`line_end`, `kind`, plus `symbol` or `locator`. Get line numbers
  from the file itself, never from memory:
  `python <skill-dir>/scripts/awf.py find <file> "<text>"` prints them.
- When a prompt is assembled from several pieces (CrewAI role + goal + backstory
  + task), put the assembled text in `system_prompt`. Anchor it at the piece
  where an appended instruction belongs; the guide says which.
- Run the helper scripts **from the repo root**, giving the full path to this
  skill's `scripts/awf.py`. Anchors and hashes are repo-relative.
- Things that are not LLM calls — custom tools, routers written in Python,
  retrievers — are not agents. Name them in `metadata.description` so the user
  knows the run simulates around them. If a workflow is mostly Python with
  one LLM call, say so: AutoAW can only tune that one call.

## 3. Agree what may change

Propose `tunable` paths and confirm them with the user. Present them as a list,
for example "classifier: model, prompt, few-shot examples". The fields are:

- `model`: AutoAW tries the models listed in `eval.candidate_models`. Ask
  which ones the user can actually deploy.
- `system_prompt`: AutoAW may **append** a reasoning or instruction text. It
  never rewrites the prompt.
- `few_shot`: AutoAW may add 2 or 4 demonstrations drawn from the eval rows.
- `temperature`: only if the user's provider honours it. GPT-5-class and other
  "temperature fixed" models ignore it.

Leave a field out when the user would not accept it changing. A field left out
is never changed. On flat pipelines the search sets one value for **all** agents
at once, so a field opened on one agent and not another comes back as
"partial". Open a field on every agent or on none.

## 4. Build the eval set

This is the part that decides whether the run means anything. Read
[references/eval-set.md](references/eval-set.md) first. In short:

- Remember what gets scored: the **last** agent's output, against `expected`.
- Look for real examples first: test fixtures, eval scripts, logged runs,
  sample inputs in the README or notebooks. Real inputs beat synthetic ones.
- Every row needs `input`. A row needs `expected` unless an `llm_judge`
  evaluator with a rubric scores it.
- **Never invent `expected` answers yourself.** If labels don't exist, propose
  some and have the user confirm them, or use `llm_judge` with a rubric the user
  approves.
- Aim for 30+ rows; 10 is the floor. Below that, every difference is noise.
- Carry a `stratum` label (category or difficulty) when the inputs have kinds.
  AutoAW samples across strata, and an unlabelled sorted file gets sampled from
  its first kind only.
- Ask the user before including anything that looks like personal data. These
  rows are uploaded.

## 5. Write and check the file locally

From the repo root:

1. `python <skill-dir>/scripts/awf.py hash <files>`. Hash every file an anchor
   points into, plus any file you copied a prompt or model value from. Don't
   hash the eval-row files: the rows travel in the `.awf` itself. Put the output into
   `source.files`.
2. Write `.autoaw/workflow.awf` (JSON).
3. `python <skill-dir>/scripts/awf.py validate .autoaw/workflow.awf`. This
   runs the server's checks, then checks every anchor against the files on
   disk: the file exists, the lines exist, and the hash still matches.

Fix every error. Read the warnings out to the user. "Only N eval rows",
"has no anchor" and "template variable" are all worth fixing before the
upload.

Set `eval.task_description` to one plain sentence about what the workflow
does, e.g. "Route a customer support ticket to one of four queues." It is
used as the experiment's task description; don't put instructions in it.

## 6. Confirm the upload, then smoke-test

Show the user what will leave the machine: agent names, the number of prompts,
the number of eval rows, the tunable fields and the candidate models. **Wait for
a yes.** Then:

1. `validate_awf` with the document. It should match the local check.
2. `import_workflow` with `smoke: true` (the default): 3 rows, 2 trials, $0.50
   cap. Then `start_optimization`.
3. Poll `get_status` about once a minute until `done`.
4. **Gate:** read `control_quality` and `best_quality`.
   - Control is 0.0 on every row: the scoring is broken (wrong evaluator, wrong
     label format, an output contract mismatch). Fix it before spending more.
   - Both trials scored exactly 1.0: the eval set is too easy to show a
     difference. Add harder rows.
   - An error status: report it verbatim.

## 7. The real run

Agree a budget with the user: the default is 24 trials and $5. A larger grid
cannot use more trials than it has cells. Then call `import_workflow` with
`smoke: false`, followed by `start_optimization`. Save `experiment_id` to
`.autoaw/state.json`. Runs take minutes to an hour. Tell the user they can leave
and resume later with "apply my AutoAW result".

## 8. Read the result honestly

`get_result` returns a `verdict`, `evidence`, `changes`, `withheld` and an
`apply_prompt`. Report the verdict in the evidence's own terms:

- `improved`: give the delta as "quality X → Y, about R of N rows"
  (`rows_delta`), plus the cost side (`cost_ratio`: the winner's cost per run
  as a multiple of today's). Add that it is a single-run difference with no
  noise floor measured, so a delta of a row or two is unproven. Never round it
  into a claim it does not support. The winner bundles every change it
  made, and the run does not say which one carried it. If a `recipe` change
  (new selection code) rides along with a model change, ask the user whether
  to apply the cheap edits first.
- `partial`: the winner also changed fields the user did not open. Applying
  only the opened changes produces a configuration nobody measured. Offer to
  re-run with those fields opened instead.
- `control_not_beaten` / `only_withheld`: nothing to apply. Say so plainly.
  That is a real result: their workflow is already at the top of this grid.

If `provisional` is set, the run is still going. Do not apply yet.

## 9. Apply

Follow [references/apply.md](references/apply.md). For each change:

1. Open the anchored file and lines. **Check that the `from` value is still
   there.** If the code has moved on since import, stop and report that change.
   Do not guess a new location.
2. Make exactly that edit in the framework's idiom: YAML key, constructor
   argument, or string literal.
3. Map AutoAW model ids to the user's provider id. The `@high` suffix means
   reasoning effort; it is not part of the id.

Then run the project's tests and show the diff. Do not commit unless the user
asks. Record in `.autoaw/state.json` which experiment the edits came from.
