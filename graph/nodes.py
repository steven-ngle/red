import json
import re
import config
from graph.state import ResearchState
from tools import memory as mem
from tools.llm import chat_flash, chat_pro
from tools.search import web_search
from ui import bullet, info, markdown_panel, panel, phase, warn


# 1) erst schauen was man schon über den user weiss
def memory_read(state: ResearchState) -> dict:
    phase("1) Remembering Memories ...")
    memories = mem.get_relevant(state["question"], state["user_id"])
    if memories:
        info(f"{len(memories)} relevante Erinnerungen für {state['user_id']} geladen:")
        for m in memories:
            bullet(m, style="green")
    else:
        info("Keine früheren Erinnerungen gefunden. Erster Durchlauf für dieses Thema")
    return {"memories": memories}


# 2) Planner
PLANNER_PROMPT = """Du bist Recherche-Planer. Zerlege die Nutzerfrage in {min_q} bis {max_q} \
präzise, eigenständig recherchierbare Teilfragen.

Bisheriger Gesprächsverlauf dieser Session (löse Bezüge wie "dabei"/"das" damit auf):
{history_block}

Nutzerfrage: {question}

Bekannter Kontext über den Nutzer aus früheren Recherchen (ggf. berücksichtigen, \
bereits Bekanntes nicht erneut recherchieren):
{memory_block}

WICHTIG: Wenn der bekannte Kontext die Frage bereits vollständig beantwortet, \
ist KEINE neue Recherche nötig, antworte dann mit einem leeren Array: []

Antworte NUR mit einem JSON-Array von Strings, z. B.:
["Teilfrage 1", "Teilfrage 2"]"""


def _history_block(state, max_exchanges=3, max_report_chars=1500):
    history = state.get("history") or []
    if not history:
        return "(erste Frage der Session)"
    parts = []
    for ex in history[-max_exchanges:]:
        report = ex["report"]
        if len(report) > max_report_chars:
            report = report[:max_report_chars] + " ...[gekürzt]"
        parts.append(f"Frage: {ex['question']}\nReport: {report}")
    return "\n\n".join(parts)


def planner(state: ResearchState) -> dict:
    phase(f"2) Planning ...")
    memory_block = "\n".join(f"- {m}" for m in state["memories"]) or "(nichts bekannt)"
    content, reasoning, reasoning_tokens = chat_pro([
        {
            "role": "user",
            "content": PLANNER_PROMPT.format(
                min_q=2, max_q=config.MAX_SUBQUESTIONS,
                question=state["question"], memory_block=memory_block,
                history_block=_history_block(state),
            ),
        }
    ])
    if reasoning_tokens:
        info(f"({reasoning_tokens} Tokens für das Reasoning verbraucht)")

    parsed = _extract_string_array(content)
    if parsed is None:
        warn("Planner-Output nicht parsebar. Nutze die Originalfrage als einzige Teilfrage")
        parsed = [state["question"]]
    subquestions = parsed[: config.MAX_SUBQUESTIONS]

    if not subquestions:
        info("Antwort bereits im Langzeitgedächtnis. Websuche wird daher übersprungen")
    else:
        info("Geplante Teilfragen:")
        for i, sq in enumerate(subquestions, 1):
            bullet(f"[{i}] {sq}", style="cyan")

    return {
        "subquestions": subquestions,
        "current_index": 0,
        "current_query": subquestions[0] if subquestions else "",
        "round": 0,
        "evidence": [],
        "findings": [],
    }


def _extract_string_array(text):
    match = re.search(r"\[.*?\]", text, re.DOTALL)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
        return [s.strip() for s in data if isinstance(s, str) and s.strip()]
    except json.JSONDecodeError:
        return None


# 3a) tavily
def search_node(state: ResearchState) -> dict:
    rnd = state["round"] + 1
    idx = state["current_index"] + 1
    phase(f"3) Researching ... (subquestion {idx}/{len(state['subquestions'])}, round {rnd}/{config.MAX_ROUNDS})")
    info(f"Suche: \"{state['current_query']}\"")

    result = web_search(state["current_query"])
    if result["results"]:
        for r in result["results"]:
            bullet(f"{r['title']}  [dim]({r['url']})[/dim]")
    else:
        warn("Keine Treffer für diese Runde")

    return {
        "round": rnd,
        "search_results": result["results"],
        "tavily_answer": result["answer"],
    }


# 3b) Treffer zusammenfassen
SUMMARIZE_PROMPT = """Fasse die folgenden Suchtreffer im Hinblick auf diese Teilfrage zusammen:
"{subquestion}"

Extrahiere 2-5 Kernaussagen als Stichpunkte. Hänge an JEDE Aussage die Quelle an,
im Format: (Quelle: <Titel> - <URL>). Nutze nur Informationen aus den Treffern.

Tavily-Kurzantwort: {answer}

Treffer:
{results_block}"""


def summarize_node(state: ResearchState) -> dict:
    if not state["search_results"]:
        return {}

    results_block = "\n\n".join(
        f"[{r['title']}]({r['url']})\n{r['content']}" for r in state["search_results"]
    )
    subq = state["subquestions"][state["current_index"]]
    summary = chat_flash([
        {
            "role": "user",
            "content": SUMMARIZE_PROMPT.format(
                subquestion=subq,
                answer=state["tavily_answer"] or "(keine)",
                results_block=results_block,
            ),
        }
    ])
    panel(summary, title=f"Kernaussagen Runde {state['round']}", style="blue")
    return {"evidence": state["evidence"] + [summary]}


# 3c) reicht die evidenz oder nochmal suchen?
REFLECT_PROMPT = """Du prüfst, ob die gesammelte Evidenz eine Teilfrage ausreichend beantwortet.

Teilfrage: "{subquestion}"

Bisher gesammelte Evidenz:
{evidence_block}

Antworte als JSON-Objekt:
{{"sufficient": true/false, "reason": "kurze Begründung", "refined_query": "neue/angepasste Suchanfrage oder null"}}

Setze "sufficient" auf true, wenn die Kernaspekte belegt sind. Perfektion ist nicht nötig.
Wenn false: formuliere in "refined_query" eine GEZIELT andere Suchanfrage, die die Lücke schließt."""


def reflect_node(state: ResearchState) -> dict:
    subq = state["subquestions"][state["current_index"]]

    if state["round"] >= config.MAX_ROUNDS:
        info(f"Reflexion: Rundenlimit ({config.MAX_ROUNDS}) erreicht. Weiter zur nächsten Teilfrage")
        return {"decision": "done"}
    if not state["evidence"]:
        info("Reflexion: Keine Evidenz. Die Suchanfrage wird umformuliert")
        return {"decision": "refine", "current_query": f"{subq} Überblick Fakten"}

    evidence_block = "\n\n".join(state["evidence"])
    raw = chat_flash(
        [{"role": "user", "content": REFLECT_PROMPT.format(subquestion=subq, evidence_block=evidence_block)}],
        json_mode=True,
    )
    try:
        verdict = json.loads(raw)
    except json.JSONDecodeError:
        warn("Output nicht parsebar. Werte Evidenz als ausreichend")
        verdict = {"sufficient": True, "reason": "Parse-Fallback"}

    if verdict.get("sufficient"):
        info(f"Reflexion: Evidenz reicht. {verdict.get('reason', '')}")
        return {"decision": "done"}

    refined = verdict.get("refined_query") or f"{subq} Details"
    info(f"Reflexion: Evidenz reicht NICHT. {verdict.get('reason', '')}")
    info(f"Neue Suchanfrage: \"{refined}\"")
    return {"decision": "refine", "current_query": refined}


# 3d) teilfrage fertig, nächste dran
def finalize_subquestion(state: ResearchState) -> dict:
    idx = state["current_index"]
    finding = {
        "subquestion": state["subquestions"][idx],
        "evidence": state["evidence"],
        "rounds": state["round"],
    }
    findings = state["findings"] + [finding]

    next_idx = idx + 1
    update = {"findings": findings, "current_index": next_idx, "round": 0, "evidence": []}
    if next_idx < len(state["subquestions"]):
        update["current_query"] = state["subquestions"][next_idx]
    return update


# 4) finaler Report
REPORT_PROMPT = """Erstelle aus den Rechercheergebnissen einen strukturierten Markdown-Report \
zur ursprünglichen Frage. Anforderungen:
- Beginne mit einer kurzen Zusammenfassung (5-6 Sätze)
- Ein Abschnitt pro Teilfrage
- JEDE Faktenaussage mit Quellenangabe (Titel + URL) belegen
- Abschließender Abschnitt "Quellen" mit allen verwendeten Links
- Sprache: Deutsch

Bisheriger Gesprächsverlauf dieser Session (für Bezüge, nicht wiederholen):
{history_block}

Ursprüngliche Frage: {question}

Bekannter Nutzerkontext (nur einfließen lassen, wo relevant):
{memory_block}

Rechercheergebnisse:
{findings_block}

Sonderfall: Wenn keine Rechercheergebnisse vorliegen, beantworte die Frage \
vollständig aus dem bekannten Nutzerkontext und gib als Quelle \
"Langzeitgedächtnis (frühere Recherche)" an."""


def report_node(state: ResearchState) -> dict:
    phase(f"4) Generating Report ...")
    findings_block = "\n\n".join(
        f"## Teilfrage: {f['subquestion']}\n" + "\n".join(f["evidence"])
        for f in state["findings"]
    )
    memory_block = "\n".join(f"- {m}" for m in state["memories"]) or "(keiner)"
    info("Schreibe finalen Report")
    report, reasoning, reasoning_tokens = chat_pro([
        {
            "role": "user",
            "content": REPORT_PROMPT.format(
                question=state["question"], memory_block=memory_block,
                findings_block=findings_block, history_block=_history_block(state),
            ),
        }
    ])
    if reasoning_tokens:
        info(f"({reasoning_tokens} Tokens für das Reasoning verbraucht)")
    markdown_panel(report, title="Finaler Report")
    return {"report": report}


# 5) neue erkenntnisse ins memory schreiben
def memory_write(state: ResearchState) -> dict:
    phase("5) Writing Memories ...")
    info("Mem0 extrahiert nennenswerte Fakten")
    new_memories = mem.add_memory(state["question"], state["report"], state["user_id"])
    if new_memories:
        info(f"{len(new_memories)} Memory Einträge aktualisiert:")
        for m in new_memories:
            bullet(m, style="blue")
    else:
        info("Mem0 hat keine neuen Fakten extrahiert")
    return {"new_memories": new_memories}
