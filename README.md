# AutoAW plugin for Claude Code

Optimise the agent workflow that already lives in your code (CrewAI, LangGraph,
LangChain, OpenAI Agents SDK, AutoGen, LlamaIndex, PydanticAI, smolagents, DSPy,
or plain SDK calls). The plugin:

1. reads your workflow and writes it to `.autoaw/workflow.awf`, recording the
   file and lines each prompt and model setting lives on;
2. builds an evaluation set with you, from your fixtures, logs or examples;
3. imports it into AutoAW over MCP, runs a cheap smoke test, then the optimisation;
4. brings the measured changes back and applies them at those exact lines.

Your source code never leaves your machine. The `.awf` file carries prompts,
settings, your evaluation rows and file hashes.

## Install

```
/plugin marketplace add deil87/autoaw-plugin
/plugin install autoaw@autoaw
```

Then create an API key at https://autoaw.app/connect (it is shown once) and
export it before starting Claude Code:

```
export AUTOAW_API_KEY=...
```

Ask Claude: *"optimise the agent workflow in this repo with AutoAW"*.

## OpenCode and other agents

The skill is a standard `SKILL.md`. Copy `skills/optimize-workflow/` into
`.opencode/skills/` (or `.claude/skills/`, `.agents/skills/`) and add the MCP
server to `opencode.json`:

```json
{
  "mcp": {
    "autoaw": {
      "type": "remote",
      "url": "https://5oahxb0xj7.execute-api.eu-central-1.amazonaws.com/mcp",
      "oauth": false,
      "headers": { "Authorization": "Bearer {env:AUTOAW_API_KEY}" }
    }
  }
}
```

## What gets reported

Every result names what it was measured on: the rows, the quality before and
after, how many rows that is, and what the change costs per run. A change that
did not beat your current workflow is reported as exactly that, with nothing to
apply.

This repository is generated from the AutoAW monorepo (`plugins/autoaw`); open
issues here, changes land there.
