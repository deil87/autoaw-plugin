# CrewAI

## Where things live

A standard `crewai create` project:

```
src/<pkg>/config/agents.yaml   role, goal, backstory, llm (per agent)
src/<pkg>/config/tasks.yaml    description, expected_output, agent (per task)
src/<pkg>/crew.py              @CrewBase class: @agent / @task / @crew methods, Process
```

Agents and tasks can also be built in Python: `Agent(role=..., llm=LLM(model=..., temperature=...))`
and `Task(description=..., agent=...)`. Use `constructor_arg` anchors for those.

## Mapping to `.awf`

- **One `.awf` agent per TASK, not per CrewAI agent.** In CrewAI each task is
  one LLM call (or one tool loop) run by an agent. Name the `.awf` agent after
  the task (`research_task`) and set `role` to the CrewAI agent's role.
- `system_prompt`: assemble the text CrewAI sends. CrewAI splits it into a
  system part (the agent) and a task part (the user turn); the `.awf` has one
  prompt per call, so join them:
  ```
  You are {role}. {backstory}
  Your personal goal is: {goal}

  Current Task: {task description}

  This is the expected criteria for your final answer: {expected_output}
  you MUST return the actual complete content as the final answer, not a summary.
  ```
  This wording comes from CrewAI's `translations/en.json`. If the installed
  version is available (`site-packages/crewai/translations/en.json`, keys
  `role_playing`, `task`, `expected_output`), copy the wording from there
  instead. If crewai isn't installed, use the text above and say so in
  `metadata.description`.
- The task's input placeholder (`{topic}`, `{ticket}`: whatever
  `crew.kickoff(inputs=...)` fills) becomes a reference to the user message;
  see SKILL.md step 2. In a sequential crew, CrewAI passes earlier task output
  as context, which matches AutoAW handing each agent the previous agent's
  output.
- `model`: the agent's `llm`. In YAML this is a string like
  `openai/gpt-4o-mini`. Write `gpt-4o-mini` in the `.awf` and put the YAML
  string in the anchor's `original`. In Python it is `LLM(model=...)`. When it is unset,
  CrewAI uses the `MODEL` env var, default `gpt-4o-mini`: use an `env_var`
  anchor on `MODEL`.
- `source.framework_version`: the pinned version, or the constraint as
  declared (`>=0.86.0`) when nothing is pinned.
- `temperature`: from `LLM(temperature=...)`. Leave it out when it is not set.
- `topology`:
  - `Process.sequential` → `fixed_pipeline`, with edges in the order of the
    tasks in the crew. A task's `context=[...]` adds an edge from each context
    task.
  - `Process.hierarchical` → `ai_orchestrated`. Add the manager (`manager_llm` /
    `manager_agent`) as an agent with id `manager`.
- Tools (`@tool`, `BaseTool` subclasses) are not agents. List them in
  `metadata.description`.

## Anchors

| path | anchor |
|---|---|
| `…model` | `yaml_key` on `<agent>.llm` in agents.yaml, or `constructor_arg` on `LLM(model=…)` |
| `…system_prompt` | `yaml_key` on `<task>.description` in tasks.yaml, covering every line of the scalar. Appended instructions belong in the task, so the agent's other tasks stay unchanged. At apply time, check the description, not the whole assembled prompt. |
| `…few_shot` | `insertion_point` on the **last line** of the task's `description`, with `locator: <task>.description`. Demos are added as an "Examples" block at its end. |
| `…temperature` | `constructor_arg` on `LLM(temperature=…)` |

**Applying few-shot in CrewAI:** pass the rendered block as a kickoff input,
e.g. `{examples}` placed just above the input placeholder in the task
description. Fill it in a `@before_kickoff` hook that calls `select_examples`.
A later task's own input (the earlier task's output) does not exist at kickoff.
Select on the original input there, and tell the user that this differs from
what was measured.

**Reasoning effort:** a YAML `llm:` string can't carry `@high`. Define the agent's
model in `crew.py` as `LLM(model=..., reasoning_effort="high")` and pass it as
`Agent(config=..., llm=...)`. Check that the installed CrewAI's `LLM` accepts
`reasoning_effort`; if it doesn't, drop the suffix and tell the user.

**Shared agents:** one CrewAI agent may run several tasks. A `model` change then
applies to every task that agent runs. If AutoAW returns different models for
two tasks of the same agent, create a second agent in agents.yaml rather than
silently picking one. Tell the user.
