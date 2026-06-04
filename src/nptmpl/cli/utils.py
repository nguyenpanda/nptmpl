from typing import List, Tuple, Dict, Any, Optional
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from nptmpl.core.models import Template
from nptmpl.core.metadata import Version, TemplateMetadata

console = Console()

def display_table(results: List[Tuple[Template, Version, TemplateMetadata]], title: str) -> None:
    """Displays a list of templates in a styled table."""
    if not results:
        console.print("[yellow]No templates found.[/yellow]")
        return
        
    table = Table(title=title, show_header=True, header_style="bold magenta", expand=True)
    table.add_column("Identifier", style="bold cyan")
    table.add_column("Ver", style="green", justify="right")
    table.add_column("Languages", style="blue")
    table.add_column("Author", style="yellow")
    table.add_column("Description", style="white")

    for template, version, metadata in results:
        table.add_row(
            f"{template.group}/{template.name}", 
            str(version), 
            ", ".join(metadata.languages), 
            metadata.author, 
            metadata.description
        )
    console.print(table)

def display_detail(template: Template, version: Version, metadata: TemplateMetadata) -> None:
    """Displays exhaustive template information in a panel view."""
    header = Text.assemble(
        (f"{template.group}/{template.name}", "bold cyan"), 
        (" @ ", "white"), 
        (str(version), "bold green")
    )
    
    info_table = Table.grid(padding=(0, 2))
    info_table.add_column(style="bold blue", justify="right")
    info_table.add_column()

    fields = [
        ("Name", metadata.name), 
        ("Author", metadata.author), 
        ("Email", metadata.email), 
        ("Languages", ", ".join(metadata.languages)), 
        ("License", metadata.license), 
        ("Added Date", metadata.added_date), 
        ("Tags", ", ".join(metadata.tags)), 
        ("URL", metadata.url)
    ]
    for label, val in fields:
        if val:
            info_table.add_row(f"{label}:", str(val))

    console.print("\n")
    console.print(Panel(info_table, title=header, border_style="bold magenta", padding=(1, 2)))
    console.print(Panel(Text(metadata.description, style="white"), title="Description", border_style="dim"))
    
    if metadata.variables:
        var_table = Table(show_header=True, header_style="bold green", box=None)
        var_table.add_column("Variable")
        var_table.add_column("Description")
        for k, v in metadata.variables.items():
            var_table.add_row(k, v)
        console.print(Panel(var_table, title="Variables", border_style="green"))

def confirm(msg: str) -> bool:
    """Prompts the user for confirmation."""
    res = input(f"{msg} [y/N]: ")
    return res.lower() in ("y", "yes")
