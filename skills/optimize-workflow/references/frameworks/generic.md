# Other frameworks and plain SDK calls

Use `source.framework` with the closest value from `autogen`, `llamaindex`,
`pydantic_ai`, `smolagents`, `dspy` or `custom`. The method is the same for
all of them: **find every LLM call site, then follow the data between them.**

## Find the call sites

Search for:

- `chat.completions.create`, `responses.create`, `messages.create`,
  `generate_content`, `litellm.completion`
- framework constructors: `AssistantAgent(` (AutoGen), `Agent(` (PydanticAI,
  smolagents), `OpenAI(`/`Settings.llm` (LlamaIndex), `dspy.Predict`,
  `dspy.ChainOfThought` and `dspy.LM(` (DSPy)

Each call site that sends its own prompt is one `.awf` agent. If a loop calls
the same site many times, that is still one agent.

## Per framework

- **AutoGen**: `AssistantAgent(name, system_message=..., model_client=...)`.
  A `RoundRobinGroupChat` → `fixed_pipeline` in participant order. A
  `SelectorGroupChat` → `ai_orchestrated`.
- **PydanticAI**: `Agent(model, system_prompt=..., output_type=...)`. Note the
  structured output type in `metadata.description`: the expected answers must
  match its serialised form.
- **smolagents**: `CodeAgent` and `ToolCallingAgent` run a tool loop, so treat
  each as one agent. `managed_agents=[...]` → `ai_orchestrated`.
- **LlamaIndex**: query engines run one LLM call over retrieved context; the
  retriever is not an agent. `AgentWorkflow` with several agents →
  `ai_orchestrated`.
- **DSPy**: each `Predict`/`ChainOfThought` module is one agent, and its
  signature's docstring is the `system_prompt`. If the program is already
  compiled by DSPy, say so in `metadata.description`. Its demos are already
  tuned, so leave `few_shot` out of `tunable`.

## When it does not fit

If most of the workflow's behaviour lives in Python (routing rules, tool
results, retrieval) and the LLM is one step of it, still extract that step.
Tell the user that AutoAW optimises the step against the eval rows as inputs,
not the whole system. That fidelity limit is the honest one to state up front.
