import argparse
import sys
import config
from ui import bullet, console, error, info, panel


def run_research(graph, question, user_id, history):
    panel(
        f"[bold]{question}[/bold]\n[dim]user_id: {user_id} · Session Verlauf: {len(history)} Austausch(e)[/dim]",
        title="red",
        style="magenta",
    )
    initial_state = {"question": question, "user_id": user_id, "history": history}
    try:
        final = graph.invoke(initial_state, config={"recursion_limit": 150})
    except RuntimeError as e:
        error(str(e))
        return None

    console.rule("[bold green]Fertig[/bold green]")
    info(f"Teilfragen recherchiert: {len(final.get('findings', []))}")
    for f in final.get("findings", []):
        bullet(f"{f['subquestion']}  [dim]({f['rounds']} Runde(n))[/dim]")
    info(f"Neue Memory Einträge: {len(final.get('new_memories', []))}")
    return final


def chat_loop(graph, user_id):
    console.print(
        "[bold magenta]red[/bold magenta] chat "
    )
    from tools import memory as mem

    history = []
    while True:
        try:
            question = console.input("\n[bold magenta]red ❯ [/bold magenta]").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\n[dim]Session beendet[/dim]")
            return
        if not question:
            continue
        if question.lower() in ("exit", "quit", "q"):
            console.print("[dim]Session beendet[/dim]")
            return
        if question == "/memories":
            memories = mem.get_all(user_id)
            panel(
                "\n".join(f"• {m}" for m in memories) or "(leer)",
                title=f"Mem0 Langzeitgedächtnis für {user_id}",
            )
            continue

        final = run_research(graph, question, user_id, history)
        if final and final.get("report"):
            history.append({"question": question, "report": final["report"]})


def main():
    parser = argparse.ArgumentParser(prog="red", description="red research agent")
    parser.add_argument("question", nargs="*", help="Recherche Frage (leer = Chat-Modus)")
    parser.add_argument("--user-id", default="Steven", help="Nutzer-ID für das Mem0 Gedächtnis")
    parser.add_argument("--show-memories", action="store_true", help="Nur gespeicherte Memories anzeigen")
    args = parser.parse_args()

    missing = config.check_env()
    if missing:
        error(f"Fehlende Umgebungsvariablen: {', '.join(missing)}")
        info(".env.example nach .env kopieren und Keys eintragen")
        sys.exit(1)

    if args.show_memories:
        from tools import memory as mem

        memories = mem.get_all(args.user_id)
        panel(
            "\n".join(f"• {m}" for m in memories) or "(leer)",
            title=f"Mem0 Gedächtnis für {args.user_id}",
        )
        return

    from graph.build_graph import build_graph

    graph = build_graph()
    question = " ".join(args.question).strip()

    try:
        if question:
            if run_research(graph, question, args.user_id, history=[]) is None:
                sys.exit(1)
        else:
            chat_loop(graph, args.user_id)
    except KeyboardInterrupt:
        console.print("\n[dim]Abgebrochen[/dim]")
        sys.exit(130)


if __name__ == "__main__":
    main()
