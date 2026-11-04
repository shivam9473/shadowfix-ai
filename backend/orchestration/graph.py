"""LangGraph wiring for the five agents. Supports both Shopkart demo and custom user projects."""

from __future__ import annotations

from typing import TypedDict

from langgraph.graph import END, StateGraph

from agents.breaker import run_breaker
from agents.coder import run_coder
from agents.detective import run_detective
from agents.reviewer import THRESHOLD, run_reviewer
from agents.sre import run_sre
from knowledge.mem0_rules import TenantMemory
from knowledge.qdrant_prod import AstKnowledgeBase
from paths import DEMO_ROOT


class FixState(TypedDict, total=False):
    tenant_id: str
    target: str
    project_id: str
    project_name: str
    custom_stack: str
    mode: str
    test_payload: str
    attempts: int
    original: str
    breaker: dict
    sre: dict
    detective: dict
    coder: dict
    review: dict


def build_graph(kb: AstKnowledgeBase, memory: TenantMemory):
    checkout = (DEMO_ROOT / "api" / "checkout.py").read_text(encoding="utf-8")

    def breaker_node(state: FixState) -> dict:
        report = run_breaker(
            tenant_id=state["tenant_id"],
            target=state["target"],
            project_id=state.get("project_id", ""),
            custom_stack=state.get("custom_stack", ""),
            mode=state.get("mode", ""),
            test_payload=state.get("test_payload", ""),
        )
        memory.add_episode(
            state["tenant_id"],
            report["stack"][-500:],
            {"agent": "breaker", "error": report["error"]},
        )
        return {"breaker": report}

    def sre_node(state: FixState) -> dict:
        return {"sre": run_sre(state["tenant_id"], state["breaker"]["stack"])}

    def detective_node(state: FixState) -> dict:
        return {
            "detective": run_detective(
                kb=kb,
                tenant_id=state["tenant_id"],
                stack=state["breaker"]["stack"],
                project_id=state.get("project_id", ""),
            )
        }

    def coder_node(state: FixState) -> dict:
        culprit = state["detective"]["culprit_path"]
        orig = state.get("original") or (checkout if not state.get("project_id") else "")
        draft = run_coder(
            tenant_id=state["tenant_id"],
            culprit_path=culprit,
            original=orig,
            stack=state["breaker"]["stack"],
            project_id=state.get("project_id", ""),
        )
        return {"coder": draft, "attempts": state.get("attempts", 0) + 1}

    def reviewer_node(state: FixState) -> dict:
        review = run_reviewer(state["coder"])
        if review["passed"]:
            rule = (
                "100% coupons are a multiplier (1 - discount), never a divisor."
                if not state.get("project_id")
                else f"Automated fix verified for {state.get('project_name', 'project')}"
            )
            memory.add_procedure(
                state["tenant_id"],
                rule,
                {"eval_score": review["eval_score"]},
            )
        return {"review": review}

    def route(state: FixState) -> str:
        review = state.get("review") or {}
        if review.get("eval_score", 0) >= THRESHOLD or state.get("attempts", 0) >= 2:
            return "done"
        return "coder"

    graph = StateGraph(FixState)
    graph.add_node("breaker", breaker_node)
    graph.add_node("sre", sre_node)
    graph.add_node("detective", detective_node)
    graph.add_node("coder", coder_node)
    graph.add_node("reviewer", reviewer_node)
    graph.set_entry_point("breaker")
    graph.add_edge("breaker", "sre")
    graph.add_edge("sre", "detective")
    graph.add_edge("detective", "coder")
    graph.add_edge("coder", "reviewer")
    graph.add_conditional_edges("reviewer", route, {"done": END, "coder": "coder"})
    return graph.compile()
