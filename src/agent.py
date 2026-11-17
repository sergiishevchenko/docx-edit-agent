"""LangGraph agent for document editing: Analyze → Plan → Execute → Validate."""

import os
from typing import TypedDict, Literal

from dotenv import load_dotenv
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import StateGraph, END, START
from pydantic import BaseModel, Field
from docx import Document

from src.document import analyze, replace_text, insert_paragraph, remove_paragraph, compare

load_dotenv()

PLAN_PROMPT = """\
You are a document editing planner. Analyze the document structure and the user's \
instruction, then create a minimal, precise edit plan.

Available operations:
1. replace — Replace text. target: exact text to find, value: replacement text.
2. insert — Insert new paragraph. target: "after:N" (N = paragraph index, \
use -1 to insert at the beginning), value: text to insert, style: paragraph style \
(default "Normal").
3. remove — Remove entire paragraph. target: text that uniquely identifies the paragraph.

Rules:
- Copy target text EXACTLY from the document — character-perfect matching is required.
- Make only the changes the instruction asks for. Do not alter anything else.
- Use enough context in target to match uniquely if a phrase appears more than once.
- To delete text inside a paragraph without removing it, use replace with empty value.
- Keep reasoning brief."""


class EditOperation(BaseModel):
    action: Literal["replace", "insert", "remove"] = Field(
        description="Type of edit"
    )
    target: str = Field(
        description=(
            "replace: exact text to find. "
            "insert: 'after:N' (paragraph index). "
            "remove: text identifying the paragraph."
        )
    )
    value: str = Field(
        default="",
        description="replace: new text. insert: text to add. Not used for remove.",
    )
    style: str = Field(default="Normal", description="Paragraph style (insert only)")


class EditPlan(BaseModel):
    reasoning: str = Field(description="Brief explanation of planned changes")
    operations: list[EditOperation]


class AgentState(TypedDict):
    document_path: str
    output_path: str
    instruction: str
    structure: str
    plan: list
    execution_log: list
    validation: dict
    retry_count: int


def _get_llm():
    return ChatGoogleGenerativeAI(
        model=os.getenv("LLM_MODEL", "gemini-3.8-flash"),
        temperature=0,
    )


def analyze_node(state: AgentState) -> dict:
    return {"structure": analyze(state["document_path"])}


def plan_node(state: AgentState) -> dict:
    llm = _get_llm().with_structured_output(EditPlan)

    content = (
        f"Document structure:\n{state['structure']}\n\n"
        f"Instruction: {state['instruction']}"
    )

    if state.get("execution_log") and not state.get("validation", {}).get("passed"):
        content += (
            f"\n\nPrevious attempt failed."
            f"\nExecution log: {state['execution_log']}"
            f"\nValidation: {state['validation']}"
            f"\nCreate a corrected plan."
        )

    response = llm.invoke([
        SystemMessage(content=PLAN_PROMPT),
        HumanMessage(content=content),
    ])

    return {"plan": [op.model_dump() for op in response.operations]}


def execute_node(state: AgentState) -> dict:
    doc = Document(state["document_path"])
    log = []

    for op in state["plan"]:
        action = op["action"]
        target = op["target"]
        value = op.get("value", "")

        if action == "replace":
            ok = replace_text(doc, target, value)
            log.append(f"replace '{target}' -> '{value}': {'OK' if ok else 'FAIL'}")

        elif action == "insert":
            idx = int(target.split(":")[1]) if ":" in target else -1
            ok = insert_paragraph(doc, idx, value, op.get("style", "Normal"))
            log.append(f"insert after P{idx}: {'OK' if ok else 'FAIL'}")

        elif action == "remove":
            ok = remove_paragraph(doc, target)
            log.append(f"remove '{target}': {'OK' if ok else 'FAIL'}")

    doc.save(state["output_path"])
    return {"execution_log": log}


def validate_node(state: AgentState) -> dict:
    log = state["execution_log"]
    all_ok = all("OK" in e for e in log)
    any_fail = any("FAIL" in e for e in log)

    diff = compare(state["document_path"], state["output_path"])

    has_changes = bool(diff["differences"])
    passed = all_ok and has_changes and not diff["formatting_issues"]

    reason = ""
    if any_fail:
        reason = "Some operations failed"
    elif not has_changes:
        reason = "No changes detected in document"
    elif diff["formatting_issues"]:
        reason = f"Formatting issues: {diff['formatting_issues']}"

    return {
        "validation": {"passed": passed, "reason": reason, **diff},
        "retry_count": state.get("retry_count", 0) + 1,
    }


def _should_retry(state: AgentState) -> Literal["plan", "end"]:
    if state["validation"].get("passed") or state.get("retry_count", 0) >= 3:
        return "end"
    return "plan"


def build_graph():
    g = StateGraph(AgentState)

    g.add_node("analyze", analyze_node)
    g.add_node("plan", plan_node)
    g.add_node("execute", execute_node)
    g.add_node("validate", validate_node)

    g.add_edge(START, "analyze")
    g.add_edge("analyze", "plan")
    g.add_edge("plan", "execute")
    g.add_edge("execute", "validate")
    g.add_conditional_edges("validate", _should_retry, {"plan": "plan", "end": END})

    return g.compile()
