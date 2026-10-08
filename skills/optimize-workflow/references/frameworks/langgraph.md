# LangGraph / LangChain

## Where things live

- The graph: `StateGraph(State)`, `add_node(name, fn)`, `add_edge(a, b)`,
  `add_conditional_edges(a, router, {...})`, `START` and `END`, plus prebuilt
  helpers like `create_react_agent(model, tools, prompt=...)`.
- Models: `ChatOpenAI(model=..., temperature=...)`, `ChatAnthropic(...)`,
  `init_chat_model("openai:gpt-4o-mini", temperature=...)`.
- Prompts: `ChatPromptTemplate.from_messages([("system", "..."), ...])`,
  `SystemMessage(content=...)`, the `prompt=` argument of `create_react_agent`,
  or LangSmith hub pulls (`hub.pull("org/name")`). A hub prompt is not in the
  repo; anchor it as `string_literal` on the `hub.pull` line and tell the user
  that the change goes into the hub prompt.

## Mapping to `.awf`

- **One `.awf` agent per node that calls an LLM.** Nodes that are plain Python
  (parsers, routers, retrievers, tool executors) are not agents. Describe them
  in `metadata.description`.
- `edges`: one per `add_edge` between two LLM nodes. A path that passes through
  a non-LLM node becomes one edge from the LLM node before it to the LLM node
  after it.
- `topology`:
  - Fixed edges, including conditional edges routed by Python functions →
    `fixed_pipeline`. Note the branching in `metadata.description`: AutoAW
    runs the agents in edge order, so branches are approximated.
  - A supervisor LLM choosing the next node (`create_supervisor`, a router node
    whose output names the next node) → `ai_orchestrated`, with the supervisor
    as an agent.
- `system_prompt`: the system message text, verbatim. Keep `{variables}`.
- `model` / `temperature`: from the chat model constructor that the node uses.
  When one model object is shared by several nodes, see "shared model" below.

## Anchors

| path | anchor |
|---|---|
| `…model` | `constructor_arg` on the `model=` argument of the chat model constructor |
| `…system_prompt` | `string_literal` on the system message text, or `file` if it is loaded from disk |
| `…few_shot` | `insertion_point` on the line that builds the message list for this node. Demos go in as a `FewShotChatMessagePromptTemplate`, or as alternating human/AI message pairs before the input. |
| `…temperature` | `constructor_arg` on `temperature=` |

**Shared model:** `llm = ChatOpenAI(...)` defined once and used by several nodes
means one anchor for several agents. This is fine while the change is the same
for all of them, and it usually is: AutoAW searches flat pipelines with one value
across agents. If the values differ, give the node its own model object.
