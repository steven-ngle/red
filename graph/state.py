from typing import TypedDict


class Exchange(TypedDict):
    # eine frage + report aus der laufenden chat session
    question: str
    report: str


class Finding(TypedDict):
    # fertiges ergebnis zu einer teilfrage
    subquestion: str
    evidence: list[str]
    rounds: int


class ResearchState(TypedDict):
    question: str
    user_id: str
    history: list[Exchange]

    memories: list[str]

    subquestions: list[str]

    # loop state: gilt immer für die aktuelle teilfrage
    current_index: int
    current_query: str
    round: int
    search_results: list[dict]
    tavily_answer: str
    evidence: list[str]
    decision: str # refine oder done

    findings: list[Finding]
    report: str
    new_memories: list[str]
