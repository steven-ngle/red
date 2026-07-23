from langgraph.graph import END, START, StateGraph
from graph import nodes
from graph.state import ResearchState


def route_after_planner(state):
    return "search" if state["subquestions"] else "report"


def route_after_reflect(state):
    return "search" if state["decision"] == "refine" else "finalize"


def route_after_finalize(state):
    return "search" if state["current_index"] < len(state["subquestions"]) else "report"


def build_graph():
    g = StateGraph(ResearchState)

    g.add_node("memory_read", nodes.memory_read)
    g.add_node("planner", nodes.planner)
    g.add_node("search", nodes.search_node)
    g.add_node("summarize", nodes.summarize_node)
    g.add_node("reflect", nodes.reflect_node)
    g.add_node("finalize", nodes.finalize_subquestion)
    g.add_node("report", nodes.report_node)
    g.add_node("memory_write", nodes.memory_write)

    g.add_edge(START, "memory_read")
    g.add_edge("memory_read", "planner")
    g.add_conditional_edges("planner", route_after_planner, {"search": "search", "report": "report"})
    g.add_edge("search", "summarize")
    g.add_edge("summarize", "reflect")
    g.add_conditional_edges("reflect", route_after_reflect, {"search": "search", "finalize": "finalize"})
    g.add_conditional_edges("finalize", route_after_finalize, {"search": "search", "report": "report"})
    g.add_edge("report", "memory_write")
    g.add_edge("memory_write", END)

    return g.compile()
