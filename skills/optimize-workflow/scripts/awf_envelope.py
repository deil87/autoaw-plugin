"""Validate an ``.awf`` envelope, 1.0 or 1.1, without importing the Gene model.

1.1 is additive over 1.0, so every file AutoAW has ever exported is a valid
import. The 1.1 blocks are what make a delta *applicable*:

``source``   which framework the workflow was extracted from, and from where.
             Hashes only — the envelope never carries the client's source.
``tunable``  the paths the client lets us change. Absent means NONE, never
             "everything": a client opts each field in.
``anchors``  for each tunable path, where in their code the value lives.
``eval``     the rows and the scoring. Without these there is nothing to
             optimise, and a run would report a confident number about nothing.

Paths read ``agents.<agent_id>.<field>``. The agent id may itself contain dots
(``crew.analyst``), so the field is cut off the END.
"""
from __future__ import annotations

import posixpath
import re
from typing import Any

AWF_KIND = "AgenticWorkflow"
SUPPORTED_VERSIONS = ("1.0", "1.1")

# What a v1 delta can carry back into a client's code. Each one maps to engine
# axes in ``experiment.AXES_FOR_FIELD``. ``system_prompt`` is tunable as TEXT
# appended by the predictor/instruction axes; the prompt is not rewritten.
TUNABLE_FIELDS = ("model", "temperature", "system_prompt", "few_shot")

# Frameworks the skill has extraction guidance for. Anything else must say
# ``custom`` — an unknown string would reach the apply step with no guide.
FRAMEWORKS = (
    "crewai", "langgraph", "langchain", "openai_agents", "autogen",
    "llamaindex", "pydantic_ai", "smolagents", "dspy", "custom",
)

ANCHOR_KINDS = (
    "string_literal",    # a Python/TS string literal holding the value
    "yaml_key",          # a key in a YAML config (CrewAI agents.yaml)
    "constructor_arg",   # a keyword argument: Agent(model=...)
    "env_var",           # the value is read from an environment variable
    "file",              # the whole file is the value (prompts/analyst.md)
    "insertion_point",   # few_shot: where demonstrations would be inserted
)

# Evaluators a client file may name. ``function`` is refused because its
# ``fn_path`` is imported by the engine — a file naming ``os.system`` would be
# code execution on our side. ``code_exec`` runs model output; not for client
# rows until it has a per-tenant sandbox. ``human`` / ``workbench`` /
# ``swebench`` need infrastructure an imported workflow does not bring.
CLIENT_EVALUATORS = ("reference", "llm_judge")
CLIENT_EVALUATOR_PREFIXES = ("deepeval_", "ragas_")

MAX_ROWS = 500
MAX_TUNABLE = 64


# LiteLLM / CrewAI spell provider-qualified ids (``openai/gpt-4o-mini``). AutoAW
# routes by bare id, so that spelling is not an OpenAI model to the engine: it
# falls through to the default provider and 404s. ``openai/gpt-oss-*`` is the
# exception — that IS AutoAW's id for gpt-oss on Nebius.
_PREFIXED_MODEL = re.compile(r"^(openai|anthropic)/(?!gpt-oss)(.+)$")
_TEMPLATE_VAR = re.compile(r"(?<!\{)\{([A-Za-z_][A-Za-z0-9_]*)\}(?!\})")


def normalize_model_id(model: str) -> str:
    """``openai/gpt-4o-mini`` -> ``gpt-4o-mini``; AutoAW ids pass unchanged."""
    m = _PREFIXED_MODEL.match(model or "")
    return m.group(2) if m else model


class AwfError(ValueError):
    """A document that cannot be imported. ``errors`` lists every reason."""

    def __init__(self, errors: list[str]):
        super().__init__("; ".join(errors))
        self.errors = errors


def split_path(path: str) -> tuple[str, str] | None:
    """``agents.crew.analyst.model`` -> ``("crew.analyst", "model")``."""
    if not isinstance(path, str) or not path.startswith("agents."):
        return None
    agent_id, _, field = path[len("agents."):].rpartition(".")
    if not agent_id or not field:
        return None
    return agent_id, field


def _safe_relpath(p: Any) -> bool:
    if not isinstance(p, str) or not p or p.startswith(("/", "\\")) or ":" in p[:3]:
        return False
    norm = posixpath.normpath(p.replace("\\", "/"))
    return not (norm == ".." or norm.startswith("../"))


def validate(doc: Any) -> tuple[list[str], list[str]]:
    """Return ``(errors, warnings)``. An empty ``errors`` means importable."""
    errors: list[str] = []
    warnings: list[str] = []
    if not isinstance(doc, dict):
        return ["document is not a JSON object"], warnings

    version = doc.get("awf_version")
    if version not in SUPPORTED_VERSIONS:
        errors.append(f"awf_version {version!r} not supported (want one of {list(SUPPORTED_VERSIONS)})")
    if doc.get("kind") != AWF_KIND:
        errors.append(f"kind must be {AWF_KIND!r}")

    wf = doc.get("workflow")
    if not isinstance(wf, dict):
        errors.append("missing 'workflow' object")
        return errors, warnings

    agents = wf.get("agents")
    agent_ids: set[str] = set()
    if not isinstance(agents, list) or not agents:
        errors.append("workflow.agents must be a non-empty list")
    else:
        for i, a in enumerate(agents):
            if not isinstance(a, dict):
                errors.append(f"workflow.agents[{i}] is not an object")
                continue
            for k in ("id", "role", "model", "system_prompt"):
                if not isinstance(a.get(k), str) or (k != "system_prompt" and not a.get(k)):
                    errors.append(f"workflow.agents[{i}].{k} must be a string")
            aid = a.get("id")
            if isinstance(aid, str):
                if aid in agent_ids:
                    errors.append(f"duplicate agent id {aid!r}")
                agent_ids.add(aid)
    if wf.get("topology") not in ("fixed_pipeline", "ai_orchestrated"):
        errors.append("workflow.topology must be 'fixed_pipeline' or 'ai_orchestrated'")
    edges = wf.get("edges", [])
    if not isinstance(edges, list):
        errors.append("workflow.edges must be a list")
        edges = []
    for i, e in enumerate(edges):
        ends = (e.get("from"), e.get("to")) if isinstance(e, dict) else (None, None)
        for end in ends:
            if end not in agent_ids:
                errors.append(f"workflow.edges[{i}] names {end!r}, which is not an agent id")
    for a in agents if isinstance(agents, list) else []:
        if not isinstance(a, dict):
            continue
        model = a.get("model")
        if isinstance(model, str) and normalize_model_id(model) != model:
            warnings.append(
                f"agent {a.get('id')!r}: model {model!r} is a provider-qualified id; AutoAW "
                f"runs it as {normalize_model_id(model)!r} (record the original in the anchor)")
        found = _TEMPLATE_VAR.findall(a.get("system_prompt") or "")
        if found:
            warnings.append(
                f"agent {a.get('id')!r}: system_prompt contains {sorted(set(found))} — AutoAW does "
                "not fill template variables; the eval row's input arrives as the first agent's "
                "user message and each later agent receives the previous agent's output")

    if version != "1.1":
        # A 1.0 file is a seed only: nothing is tunable, so nothing comes back.
        for k in ("source", "tunable", "anchors", "eval"):
            if k in doc:
                errors.append(f"'{k}' is a 1.1 field; set awf_version to '1.1'")
        return errors, warnings

    _validate_source(doc.get("source"), errors)
    tunable = _validate_tunable(doc.get("tunable"), agent_ids, errors)
    _validate_anchors(doc.get("anchors"), tunable, errors, warnings)
    _validate_eval(doc.get("eval"), errors, warnings)
    if not tunable:
        warnings.append("nothing is tunable — the run can measure this workflow but return no changes")
    return errors, warnings


def require_valid(doc: Any) -> list[str]:
    """Raise :class:`AwfError` on an invalid document; return its warnings."""
    errors, warnings = validate(doc)
    if errors:
        raise AwfError(errors)
    return warnings


def _validate_source(src: Any, errors: list[str]) -> None:
    if not isinstance(src, dict):
        errors.append("source must be an object with at least 'framework'")
        return
    fw = src.get("framework")
    if fw not in FRAMEWORKS:
        errors.append(f"source.framework {fw!r} unknown (one of {list(FRAMEWORKS)}; use 'custom' otherwise)")
    files = src.get("files", [])
    if not isinstance(files, list):
        errors.append("source.files must be a list")
        return
    for i, f in enumerate(files):
        if not isinstance(f, dict) or not _safe_relpath(f.get("path")):
            errors.append(f"source.files[{i}].path must be a relative path inside the repo")
        elif set(f) - {"path", "sha256"}:
            # Hashes only. A 'content' key would ship their source to us.
            errors.append(f"source.files[{i}] may carry only path and sha256")


def _validate_tunable(tun: Any, agent_ids: set[str], errors: list[str]) -> list[str]:
    if tun is None:
        return []
    if not isinstance(tun, list):
        errors.append("tunable must be a list of paths")
        return []
    if len(tun) > MAX_TUNABLE:
        errors.append(f"tunable lists {len(tun)} paths; the limit is {MAX_TUNABLE}")
    out: list[str] = []
    for path in tun:
        parts = split_path(path)
        if parts is None:
            errors.append(f"tunable path {path!r} must read agents.<agent_id>.<field>")
            continue
        aid, field = parts
        if aid not in agent_ids:
            errors.append(f"tunable path {path!r} names agent {aid!r}, which is not in workflow.agents")
        elif field not in TUNABLE_FIELDS:
            errors.append(f"tunable path {path!r}: field {field!r} is not tunable (one of {list(TUNABLE_FIELDS)})")
        else:
            out.append(path)
    return out


def _validate_anchors(anchors: Any, tunable: list[str], errors: list[str], warnings: list[str]) -> None:
    if anchors is None:
        anchors = {}
    if not isinstance(anchors, dict):
        errors.append("anchors must be an object keyed by path")
        return
    for path, a in anchors.items():
        if path not in tunable:
            errors.append(f"anchor {path!r} is for a path not in tunable")
            continue
        if not isinstance(a, dict):
            errors.append(f"anchor {path!r} is not an object")
            continue
        if not _safe_relpath(a.get("file")):
            errors.append(f"anchor {path!r}: file must be a relative path inside the repo")
        ls = a.get("line_start")
        if not isinstance(ls, int) or ls < 1:
            errors.append(f"anchor {path!r}: line_start must be an integer >= 1")
        le = a.get("line_end", ls)
        if isinstance(ls, int) and (not isinstance(le, int) or le < ls):
            errors.append(f"anchor {path!r}: line_end must be an integer >= line_start")
        if a.get("kind") not in ANCHOR_KINDS:
            errors.append(f"anchor {path!r}: kind {a.get('kind')!r} not one of {list(ANCHOR_KINDS)}")
    for path in tunable:
        if path not in anchors:
            # Still measurable; the change comes back without a location and the
            # skill has to find it again, which is where edits land wrong.
            warnings.append(f"tunable path {path!r} has no anchor")


def _validate_eval(ev: Any, errors: list[str], warnings: list[str]) -> None:
    if not isinstance(ev, dict):
        errors.append("eval must be an object: rows (or dataset_id) and evaluators")
        return
    rows = ev.get("rows")
    if rows is None and not ev.get("dataset_id"):
        errors.append("eval needs rows or a dataset_id — there is nothing to score without them")
    if rows is not None:
        if not isinstance(rows, list) or not rows:
            errors.append("eval.rows must be a non-empty list")
            rows = []
        elif len(rows) > MAX_ROWS:
            errors.append(f"eval.rows has {len(rows)} rows; the limit is {MAX_ROWS}")
        for i, r in enumerate(rows[:MAX_ROWS]):
            if not isinstance(r, dict) or not isinstance(r.get("input"), str) or not r["input"].strip():
                errors.append(f"eval.rows[{i}].input must be a non-empty string")
                break
        if rows and len(rows) < 10:
            warnings.append(f"only {len(rows)} eval rows — differences between configs will mostly be noise")
    evaluators = ev.get("evaluators") or []
    if not isinstance(evaluators, list) or any(not isinstance(e, dict) or not e.get("type") for e in evaluators):
        errors.append("eval.evaluators must be a list of {type, params}")
        evaluators = []
    for e in evaluators:
        t = e["type"]
        if t not in CLIENT_EVALUATORS and not t.startswith(CLIENT_EVALUATOR_PREFIXES):
            errors.append(f"evaluator {t!r} is not available to imported workflows "
                          f"(use {list(CLIENT_EVALUATORS)} or a deepeval_*/ragas_* metric)")
    has_expected = isinstance(rows, list) and any(isinstance(r, dict) and r.get("expected") for r in rows)
    if not evaluators and not has_expected:
        errors.append("eval has no evaluators and no row carries 'expected' — nothing would score")
    models = ev.get("candidate_models", [])
    if not isinstance(models, list) or any(not isinstance(m, str) for m in models):
        errors.append("eval.candidate_models must be a list of model ids")
