from sqlalchemy import create_engine

from rich.console import Console
from rich.panel import Panel

from helper import (
    load_schema_map,
    generate_schema_text,
    save_file
)

console = Console()

#--Initialising DB connection--

SCHEMA_FILE = "schema.txt"
DB_URL_FILE = "db_config.txt"



SCHEMA_MAP = {}

def perform_connection(connection_string):
    with console.status(f"[bold blue]🔌 Connecting to {connection_string}...[/bold blue]", spinner="dots"):
        try:
            engine = create_engine(connection_string)

            global SCHEMA_MAP
            SCHEMA_MAP = load_schema_map(engine)

            if not SCHEMA_MAP:
                console.print("[yellow]⚠ Connected, but DB is empty.[/yellow]")
            else:
                generate_schema_text(SCHEMA_MAP, SCHEMA_FILE)

            save_file(DB_URL_FILE, connection_string)

            return engine, SCHEMA_MAP

        except Exception as e:
            #to be moved to apt place after alpha
            console.print(Panel(f"[bold red]Connection Failed[/bold red]\n{e}", style="red"))
            return None, []
        

