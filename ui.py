from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

console = Console()


def phase(title):
    console.rule(f"[bold cyan]{title}[/bold cyan]")


def info(msg):
    console.print(f"[dim]{msg}[/dim]")


def bullet(msg, style="white"):
    console.print(f"  [bold green]•[/bold green] [{style}]{msg}[/{style}]")


def warn(msg):
    console.print(f"[bold yellow] {msg}[/bold yellow]")


def error(msg):
    console.print(f"[bold red] {msg}[/bold red]")


def panel(content, title, style="cyan"):
    console.print(Panel(content, title=title, border_style=style, expand=False))


def markdown_panel(md, title):
    console.print(Panel(Markdown(md), title=title, border_style="magenta"))
