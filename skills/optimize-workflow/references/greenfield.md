# Greenfield: AutoAW builds the workflow

Use this path when there is no workflow in the repo, or the user asks AutoAW
to design one. You supply the task and the examples; AutoAW composes and
tunes the workflow. **You do not write prompts, agents or a graph.**

## 1. The task description

One or two plain sentences saying what the work **is**, in the user's domain
language. For example: "Triage an anti-money-laundering transaction-monitoring
alert and decide whether to escalate it to investigation or close it."

Describe the work, not the machinery. Words like "pipeline", "agents" or
"workflow" pull the catalog toward units about composition. The wording
decides which units scope retrieves, so agree it with the user.

## 2. Examples and how they are scored

The same rules as [eval-set.md](eval-set.md). The rows are
`{"input", "expected"?, "stratum"?, "id"?}`, and you need one of:

- `labels`: the closed answer set, for a classification task. Every
  `expected` must be one of the labels, and the workflow answers with exactly
  one.
- `rubric`: what a good free-text answer contains, when there is no single
  correct output. It is scored by an LLM judge. Agree the rubric with the user.

With neither, rows that carry `expected` are scored by token F1.

**Input shape matters.** AutoAW's domain catalog has real code steps (AML
scenario rules, sanctions screening, credit scoring), but they read
**structured records**. Free-text inputs get the generic workflow
(extract → assess → answer) automatically. If the user's inputs are JSON
records, keep them as JSON strings in `input`; then the catalog can be used.

## 3. Create, smoke, run

Show the user what will be uploaded (the task, the number of rows, the labels
or rubric, and the models), and **wait for a yes**. Then:

1. `create_experiment` with `smoke: true` (the default), then
   `start_optimization`, then poll `get_status`.
2. Gate on the smoke run, exactly as in SKILL.md step 6: everything at 0.0
   means the labels or the input format are wrong; everything at 1.0 means the
   rows are too easy.
3. Agree a budget, then call `create_experiment` with `smoke: false` and start
   it. The default is 24 trials and $5. `catalog` defaults to `auto`; pass
   `generic` or `domain` only if the user wants to force one.

## 4. Read the result

`get_result` returns `kind: "greenfield"`, with these parts:

- `scope.pool`: the workflow AutoAW composed, in order.
- `scope.fallback`: set when the generic workflow was used instead of the
  catalog, with the reason. Tell the user which one they got and why.
- `evidence.default` vs `evidence.winner`: the composed workflow at its
  default settings, against the best tuned settings, on `n_rows` rows from a
  single run. There is no "before" to beat; say so.
- `workflow`: each step with its kind, and for model steps the model, prompt,
  answer set and prompt settings.
- `portable`: true when every step is a model call.

## 5. Use it

- **Always available:** `deploy_workflow` serves the winning workflow on
  AutoAW. The user sends rows to `POST /deployments/{id}/runs` with their API
  key and polls `GET /deployments/{id}/runs/{run_id}`. Code steps run inside
  AutoAW, so this is the only option when `portable` is false.
- **When `portable` is true:** offer to rebuild it in the user's framework
  from `workflow`. Use one LLM call per model step, in order. Pass the
  original input to the first step and each step's output to the next, which
  is how AutoAW ran it. Use each step's `effective_system_prompt`, which is
  the prompt with any appended text already included, and its `model`, and
  `output_values` when set (answer with exactly one). When a step has
  `few_shot`, copy its `reference_code` verbatim, as in
  [apply.md](apply.md). Write nothing of your own into these prompts.
- Afterwards the project has a workflow in code, so later runs use the
  normal optimisation path in SKILL.md, steps 1–9.
