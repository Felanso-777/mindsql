#SCHEMA_MAP = dict
#tables = set
#alias = dict
#columns = list of dict
#valid_tables = dict

import typer
from llama_cpp import Llama
from rich.progress import Progress, TextColumn, BarColumn, DownloadColumn, TransferSpeedColumn, TimeRemainingColumn
import json
import urllib.request
import re
import os
import sys
import sqlglot
from sqlglot import exp
from time import sleep
from rich.console import Console
from rich.syntax import Syntax
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich import box
from rich.progress import (Progress, TextColumn, BarColumn,
                           DownloadColumn, TransferSpeedColumn, TimeRemainingColumn)
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine.url import make_url
import warnings
from sqlalchemy.exc import SAWarning

# Ignore SQLAlchemy warnings about unrecognized data types (like geometry)
warnings.filterwarnings("ignore", category=SAWarning)
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.styles import Style
from pathlib import Path

# =============================================================================
# PATHS & CONSTANTS
# =============================================================================

USER_HOME = Path.home() / ".mindsql"
USER_HOME.mkdir(parents=True, exist_ok=True)

SETTINGS_FILE  = USER_HOME / "settings.json"
DEFAULT_MODEL_DIR = USER_HOME / "models"
DEFAULT_MODEL_DIR.mkdir(parents=True, exist_ok=True)

MODEL_DOWNLOAD_URL = "https://huggingface.co/AKHILDEVCV/MindSQL-Model-GGUF/resolve/main/qwen2.5-coder-3b-instruct.Q4_K_M.gguf?download=true"
SCHEMA_FILE    = str(USER_HOME / "schema.txt")
DB_URL_FILE    = str(USER_HOME / "db_config.txt")
HISTORY_FILE   = str(USER_HOME / "mindsql_history.txt")
MAX_RETRIES    = 3
SCHEMA_MAP     = {}  # Global schema cache populated on DB connection


# --- Setup ---
app = typer.Typer()
console = Console()


# =============================================================================
# MODEL SETUP — Download or locate the local GGUF model
# =============================================================================

def download_model_with_progress(url: str, dest_path: str):
    """Download the GGUF model file with a Rich progress bar."""
    with Progress(
        TextColumn("[bold blue]{task.fields[filename]}", justify="right"),
        BarColumn(bar_width=None),
        "[progress.percentage]{task.percentage:>3.1f}%",
        "•", DownloadColumn(), "•", TransferSpeedColumn(), "•", TimeRemainingColumn(),
        console=console
    ) as progress:
        task = progress.add_task("Downloading...", filename="qwen2.5-coder-3b-instruct.Q4_K_M.gguf", total=None)

        def reporthook(block_num, block_size, total_size):
            if progress.tasks[task].total is None and total_size > 0:
                progress.update(task, total=total_size)
            progress.update(task, advance=block_size)

        try:
            urllib.request.urlretrieve(url, dest_path, reporthook=reporthook)
        except Exception as e:
            console.print(f"\n[bold red] Download failed: {e}[/bold red]")
            sys.exit(1)

def get_or_set_settings() -> dict:
    settings = {}
    
    # 1. Safely load existing settings
    if SETTINGS_FILE.exists():
        try:
            with open(SETTINGS_FILE, "r") as f:
                settings = json.load(f)
        except Exception:
            pass # Ignore empty or corrupted files, start fresh

    # 2. Check and prompt for Model Path
    if "model_path" not in settings or not Path(settings["model_path"]).exists():
        console.print(Panel("[bold cyan]MindSQL Setup[/bold cyan]\nLet's configure your AI Model."))
        user_input = input("Save model to (Enter for default): ").strip()
        model_dir = Path(user_input) if user_input else DEFAULT_MODEL_DIR
        model_dir.mkdir(parents=True, exist_ok=True)
        final_model_path = model_dir / "qwen2.5-coder-3b-instruct.Q4_K_M.gguf"

        if not final_model_path.exists():
            console.print("[bold yellow]📥 Downloading model...[/bold yellow]")
            download_model_with_progress(MODEL_DOWNLOAD_URL, str(final_model_path))
            file_size = final_model_path.stat().st_size
            if file_size < 1_000_000:  # Less than 1 MB = definitely not a real model
                console.print(f"[bold red]❌ Download failed — file too small ({file_size} bytes). Check the URL.[/bold red]")
                final_model_path.unlink()  # Delete the bad file
                sys.exit(1)

            
        else:
            console.print(f"[bold green]✅ Model found locally at: {final_model_path}[/bold green]")
            
        settings["model_path"] = str(final_model_path)

    # 3. Check and prompt for AI Memory (Tokens)
    if "n_ctx" not in settings:
        console.print("\n[bold cyan]🧠 AI Memory (Tokens) Setup[/bold cyan]")
        console.print("  [green]1. Low[/green]    (2048)  - Best for older/low-end PCs")
        console.print("  [yellow]2. Medium[/yellow] (4096)  - Recommended for most PCs")
        console.print("  [red]3. High[/red]   (8192)  - Best for high-end PCs")
        console.print("  [magenta]4. Max[/magenta]    (32768) - Full capacity (Requires massive RAM)")
        console.print("  [cyan]5. Custom[/cyan] (Enter a specific number)")
        
        t_input = input("\nChoose an option (1-5) or press Enter for Medium: ").strip()
        
        token_map = {"1": 2048, "2": 4096, "3": 8192, "4": 32768}
        if t_input in token_map:
            settings["n_ctx"] = token_map[t_input]
        elif t_input == "5":
            c_input = input("Enter custom token amount (e.g., 1024): ").strip()
            settings["n_ctx"] = int(c_input) if c_input.isdigit() else 4096
        else:
            settings["n_ctx"] = 4096 # Default to medium if they press Enter or mess up

    # 4. Save and return safely
    with open(SETTINGS_FILE, "w") as f:
        json.dump(settings, f)
        
    return settings

# Locate model and load LLM at startup
USER_SETTINGS = get_or_set_settings()
with console.status(f"[bold green]🧠 Loading Local LLM ({USER_SETTINGS['n_ctx']} tokens)...[/bold green]"):
    try:
        llm = Llama(
            model_path=USER_SETTINGS["model_path"],
            n_ctx=USER_SETTINGS["n_ctx"],
            n_threads=4,
            verbose=False
        )
    except Exception as e:
        console.print(f"[bold red] Failed to load model: {e}[/bold red]")
        sys.exit(1)


            


# --- Helpers ---

# --load_file to open the required files--
def load_file(filename):
    if not os.path.exists(filename):
        return None
    with open(filename, "r", encoding="utf-8") as f: # Fix UnicodeEncodeError on Windows by enforcing utf-8 encoding
        return f.read().strip()
    
#to save user credentials
def save_file(filename, content):
    with open(filename, "w", encoding="utf-8") as f:
        f.write(content)

#--Extract table names from each query--
def extract_tables(sql):
    parsed = sqlglot.parse_one(sql)
    tables = set()
    alias_map = {}
    for table in parsed.find_all(exp.Table):  
        real_name = table.name     
        tables.add(real_name)     #mapping tables from query and adding to set table
        if table.alias:  # determining alias existence
            alias_map[table.alias.name] = real_name
    return tables, alias_map

#--Extract column names from each query--
def extract_columns(sql):
    parsed = sqlglot.parse_one(sql)
    columns = []
    for column in parsed.find_all(exp.Column):
        columns.append({
        "table" : column.table,
        "column" : column.name})
    return columns

#--Validate generated sql alongside the SCHEMA_MAP
def validate_sql_schema(sql,SCHEMA_MAP):
    sql_upper  = sql.upper()
    tables,alias = extract_tables(sql)
    columns = extract_columns(sql)
    valid_tables = {}
    
    # DDL cmd validation. Asks user permission for structural changes and deletions.
    forbidden = ["CREATE", "ALTER", "DROP", "DELETE", "RENAME", "TRUNCATE"]
    if any(keyword in sql_upper for keyword in forbidden):
        # 1. Print a warning using your existing Rich console
        console.print("\n[bold red]⚠️  WARNING:[/bold red] Destructive or structural command detected!")
        # 2. Ask for explicit user permission
        choice = input("Are you sure you want to allow this command? (y/n): ").strip().lower()
        if choice == 'y':
            return True  # User approved: allow execution and skip normal column checks
        else:
            return None # User denied: block execution 
    # table validation 
    for table in tables : 
        matched = None
        for schema_table in SCHEMA_MAP :
            if table.lower() == schema_table.lower() :
                matched = schema_table
                break
        if matched is None :
            return False
        valid_tables[table]=matched
    #column & alias validation 
    for column in columns :
        col_table = column["table"]
        col_name = column["column"]
        # to get the table name from column list of dict. 3 cases : 
        # case -1 : if alias used , multiple table exist in query
        if col_table in alias :
            real_table = alias[col_table]
        # case -2 : if alias not used , multiple table exist in query
        elif col_table in valid_tables :
            real_table = col_table
        # case -3 : if alias not used , only single exists in query
        elif col_table is None :
            if len(valid_tables) == 1 :
                real_table = list(valid_tables.keys())[0]
            else :
                return False
        else : 
            return False
        #checking if the obtain table exist in the SCHEMA_MAP
        if real_table not in valid_tables :
            return False
        schema_table_name = valid_tables[real_table]
        schema_columns = SCHEMA_MAP[schema_table_name]["columns"]
        column_found = False
        for schema_col in schema_columns :
            if col_name.lower() == schema_col.lower():
                column_found = True
                break
        if not column_found :
            return False
#if no false happens => safe         
    return True

#--Load Schema --
def load_schema_map(engine):
    schema = {}
    inspector = inspect(engine)
    table_names =  inspector.get_table_names();
    for table in table_names:
        columns = inspector.get_columns(table)
        column_names = [col["name"] for col in columns]
        pk_constraint = inspector.get_pk_constraint(table)
        primary_keys = pk_constraint.get("constrained_columns", [])
        foreign_keys=[]
        for fk in inspector.get_foreign_keys(table):
            foreign_keys.append({"child_columns" : fk["constrained_columns"],
                                 "parent_table" : fk["referred_table"],
                                 "parent_columns" : fk["referred_columns"]})
        schema[table] = {"columns" : column_names,"primary_keys": primary_keys,
                            "foreign_keys" : foreign_keys}
       
    return schema

def extract_sql(text):
    # 1. Look for markdown blocks
    match = re.search(r"```sql\s*(.*?)\s*```", text, re.DOTALL | re.IGNORECASE)
    if match:
        sql = match.group(1).strip()
    else:
        match = re.search(r"```\s*(.*?)\s*```", text, re.DOTALL)
        if match:
            sql = match.group(1).strip()
        else:
            clean_text = text.strip()
            keywords = ["SELECT", "INSERT", "UPDATE", "DELETE", "CREATE", "DROP", "SET", "ALTER", "BEGIN", "WITH"]
            if any(clean_text.upper().startswith(k) for k in keywords):
                sql = clean_text
            else:
                return None

    # added centralised method to identify sql queries from non- sql queries
    try:
        sqlglot.parse_one(sql)
        return sql
    except Exception:
        print("Failed. Try giving requests related to SQL")
        return None

# --to display the staring lines --
def print_banner(db_url):
    console.clear()
    banner_text = Text("MindSQL v10.3 (Chain of Thought)", style="bold magenta", justify="center")
    
    info_text = (
        f"\n[bold cyan]Connected to:[/bold cyan] {db_url}\n"
        "[dim]──────────────────────────────────────────────[/dim]\n"
        "• [bold cyan]mindsql <text>[/bold cyan]       : Strict SQL\n"
        "• [bold cyan]mindsql_ans <text>[/bold cyan]   : Chat & Explain\n"
        "• [bold yellow]mindsql_plot <text>[/bold yellow]  : Generate Charts 📊\n"
        "• [bold green]switch[/bold green]                 : Change Database\n"
        "• [bold green]connect[/bold green]                : Login Wizard\n"
        "• [bold magenta]set_tokens <num>[/bold magenta]       : Change AI Memory\n"
        "• [bold yellow]CREATE/DROP DATABASE[/bold yellow]   : Server Management\n"
        "• [bold red]exit[/bold red]                   : Quit"
    )

    console.print(Panel(
        info_text,
        title=banner_text,
        border_style="blue",
        box=box.ROUNDED,
        padding=(1, 2)
    ))


#to add schema to schema.txt

def generate_schema_text(schema_map, schema_file):
    with open(schema_file, "w", encoding="utf-8") as f: 
        f.write("DATABASE SCHEMA\n")
        f.write("================\n\n")

        for table, info in schema_map.items():
            f.write(f"TABLE: {table}\n")

            for col in info["columns"]:
                col_line = f"  - {col}"

                if col in info.get("primary_keys", []):
                    col_line += " (PRIMARY KEY)"

                for fk in info.get("foreign_keys", []):
                    if col in fk["child_columns"]:
                        parent_table = fk["parent_table"]
                        parent_column = fk["parent_columns"][0]
                        col_line += f" (FOREIGN KEY → {parent_table}.{parent_column})"

                f.write(col_line + "\n")

            f.write("\n")
    
#--Initialising DB connection--

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

            return engine, list(SCHEMA_MAP.keys())

        except Exception as e:
            console.print(Panel(f"[bold red]Connection Failed[/bold red]\n{e}", style="red"))
            return None, []

# --- CHARTING FUNCTION ---
def draw_ascii_bar_chart(data):
    """
    Expects data as a list of tuples: [("Label", Value), ...]
    """
    if not data:
        console.print("[yellow]No data to plot.[/yellow]")
        return

    try:
        clean_data = [(str(row[0]), float(row[1])) for row in data if row[1] is not None]
    except ValueError:
        console.print("[red]Error: Plot data must contain a Label and a Number.[/red]")
        return

    if not clean_data:
        console.print("[yellow]No valid numeric data found.[/yellow]")
        return

    max_label_len = max(len(d[0]) for d in clean_data)
    max_val = max(d[1] for d in clean_data)
    bar_width = 40 

    console.print()
    console.print(Panel("[bold]📊 Analysis Result[/bold]", style="blue", box=box.MINIMAL, expand=False))

    for label, value in clean_data:
        if max_val > 0:
            filled_len = int((value / max_val) * bar_width)
        else:
            filled_len = 0
            
        bar = "█" * filled_len
        color = "spring_green1" 
        if value < (max_val * 0.3): color = "red"
        elif value < (max_val * 0.7): color = "yellow"

        console.print(f"{label.rjust(max_label_len)} │ [{color}]{bar}[/{color}]  [bold white]{value}[/bold white]")
    
    console.print()

#--Validator function --

def validate_plot_sql(sql: str) -> bool:
    """
    Ensures SQL returns exactly 2 columns:
    LABEL (text) and VALUE (numeric)
    """
    sql_upper = sql.upper()

    # Must be SELECT
    if not sql_upper.startswith("SELECT"):
        return False

    # Count selected columns (naive but effective)
    select_part = sql_upper.split("FROM")[0]
    columns = select_part.replace("SELECT", "").split(",")

    if len(columns) != 2:
        return False

    # VALUE must be aggregated or numeric
    if not any(k in columns[1] for k in ["COUNT", "SUM", "AVG", "MIN", "MAX"]):
        return False

    return True


# --- EXECUTE FUNCTION ---

def execute_sql(engine, sql: str, raise_error=False, return_data=False):
    try:
        raw_commands = sql.split(';')
        commands = [c.strip() for c in raw_commands if c.strip()]
        
        with engine.connect() as conn:
            trans = conn.begin() 
            last_result_data = [] 
            
            try:
                for i, cmd in enumerate(commands):
                    if cmd.upper() in ['BEGIN', 'COMMIT', 'ROLLBACK', 'BEGIN TRANSACTION']:
                        continue
                        
                    result = conn.execute(text(cmd))
                    
                    if result.returns_rows:
                        rows = result.fetchall()
                        last_result_data = rows 
                        
                        if not return_data:
                            table = Table(box=box.ROUNDED, header_style="bold magenta", border_style="blue", title=f"Result {i+1}")
                            keys = result.keys()
                            for key in keys:
                                table.add_column(key, style="cyan")
                            for row in rows:
                                row_str = [str(item) for item in row]
                                table.add_row(*row_str)
                            console.print(table)
                
                trans.commit()
                if not return_data:
                    console.print(Panel(f"[bold green]✓ Successfully ran {len(commands)} commands.[/bold green]", box=box.ROUNDED, style="green"))
                
                if return_data:
                    return last_result_data

            except Exception as script_error:
                trans.rollback()
                raise script_error

    except Exception as e:
        if raise_error:
            raise e
        console.print(Panel(f"[bold red]SQL Execution Error[/bold red]\n{e}", style="red", box=box.ROUNDED))
        return None
def mindsql_start(messages: list) -> str | None:
    """Send messages to the local LLM and extract SQL from the response."""
    response = llm.create_chat_completion(messages=messages, temperature=0.1)

    print("\n[AI RESPONSE DEBUG]")
    print("Raw response length:", len(str(response)))

    ai_text = response['choices'][0]['message']['content']
    print("AI output length:", len(ai_text))
    print("AI output preview:", ai_text[:200])

    return extract_sql(ai_text)


    

# --- Commands ---

@app.command()
def shell():
    print("Initialising......")
    global SCHEMA_MAP
    # --- Session state ---
    db_url        = load_file(DB_URL_FILE)  # Last used DB URL (persisted)
    engine        = None   # Active DB engine (requires a selected database)
    server_engine = None   # Server-level engine (no DB) for SHOW DATABASES / switch
    schema_context = ""    # Schema text injected into LLM prompts

    # Stores login credentials in memory so switching DBs never needs re-login
    base_credentials = {"user": None, "password": None, "host": None, "dialect": "mysql+pymysql"}

    # --- Credential helpers ---
    def build_url(target_db: str) -> str:
        """Construct a full DB URL from cached credentials + target database name."""
        return (f"{base_credentials['dialect']}://"
                f"{base_credentials['user']}:{base_credentials['password']}@"
                f"{base_credentials['host']}/{target_db}")

    def cache_credentials(user: str, password: str, host: str, dialect: str = "mysql+pymysql"):
        """Save login credentials to the in-memory store."""
        base_credentials.update({"user": user, "password": password,
                                  "host": host, "dialect": dialect})

    def parse_credentials_from_url(url_str: str):
        """Restore cached credentials from a saved URL string (used on startup)."""
        try:
            parsed = make_url(url_str)
            cache_credentials(parsed.username, parsed.password,
                              parsed.host, parsed.drivername)
        except Exception:
            pass

# --- Restore previous session if a saved URL exists ---
    if db_url:
        # _ is Python convention for “unused variable”
        parse_credentials_from_url(db_url)
        engine, _ = perform_connection(db_url)
        schema_context = load_file(SCHEMA_FILE) or ""

        # --- Prompt session setup ---
    session = PromptSession(
        history=FileHistory(HISTORY_FILE),
        style=Style.from_dict({'prompt': 'ansicyan bold'}),
    )
    


    if engine:
        print_banner(db_url)
    else:
        console.print(Panel(
            "[bold cyan]Welcome to MindSQL![/bold cyan]\n\n"
            "Type [bold green]connect[/bold green] to login with your database credentials.",
            border_style="blue", box=box.ROUNDED, padding=(1, 2)
        ))
            # MAIN REPL LOOP
    while True:
        try:
            # Show current DB name in prompt, or 'no db' if none selected
            current_db = make_url(db_url).database if db_url else "no db"
            user_input = session.prompt([
                ('class:prompt', f'SQL ({current_db})> ')
            ]).strip()
            if not user_input:
                continue

            # Strip trailing semicolon for internal command matching
            clean_input = user_input.rstrip(';').strip()

            if user_input.lower() in ["exit", "quit"]:
                break

    # CMD: USE db_name — Switch database using stored credentials

            if clean_input.lower().startswith("use "):
                if not base_credentials["user"]:
                    console.print("[red] Please 'connect' first to establish credentials.[/red]")
                    continue

                target_db = clean_input.split(" ", 1)[1].strip()
                try:
                    new_url    = build_url(target_db)
                    new_engine, _ = perform_connection(new_url)
                    if new_engine:
                        engine         = new_engine
                        db_url         = new_url
                        schema_context = load_file(SCHEMA_FILE) or ""
                        print_banner(db_url)
                        console.print(f"[bold green]✅ Switched to database: {target_db}[/bold green]")
                except Exception as e:
                    console.print(f"[red] Could not switch to '{target_db}': {e}[/red]")
                continue

            # CMD: SET_TOKENS — Adjust LLM context window memory

            elif clean_input.lower().startswith("set_tokens "):
                parts = clean_input.split(" ")
                if len(parts) == 2 and parts[1].isdigit():
                    new_tokens = int(parts[1])
                    with open(SETTINGS_FILE, "r") as f:
                        settings = json.load(f)
                    settings["n_ctx"] = new_tokens
                    with open(SETTINGS_FILE, "w") as f:
                        json.dump(settings, f)
                    console.print(f"[bold green]✅ Token limit saved as {new_tokens}.[/bold green]")
                    console.print("[yellow]🔄 Please type 'exit' and restart MindSQL to apply the new memory settings.[/yellow]")
                else:
                    console.print("[red]Invalid usage. Example: set_tokens 4096[/red]")
                continue

            # CMD: SWITCH — Interactive database picker (no re-login needed)
            elif clean_input.lower() == "switch":
                nav_engine = engine or server_engine
                if not nav_engine:
                    console.print("[red] Not connected. Please 'connect' first.[/red]")
                    continue

                try:
                    with nav_engine.connect() as conn:
                        db_list = [row[0] for row in conn.execute(text("SHOW DATABASES;")).fetchall()]

                    console.print("\n[bold cyan]📂 Available Databases:[/bold cyan]")
                    for idx, name in enumerate(db_list, 1):
                        console.print(f"  [bold yellow]{idx}.[/bold yellow] {name}")

                    choice = session.prompt([('class:prompt', '\nEnter number or name: ')]).strip()
                    if not choice:
                        continue

                    target_db = None
                    if choice.isdigit() and 1 <= int(choice) <= len(db_list):
                        target_db = db_list[int(choice) - 1]
                    elif choice in db_list:
                        target_db = choice

                    if target_db:
                        new_url    = build_url(target_db)
                        new_engine, _ = perform_connection(new_url)
                        if new_engine:
                            engine         = new_engine
                            db_url         = new_url
                            schema_context = load_file(SCHEMA_FILE) or ""
                            print_banner(db_url)
                        else:
                            console.print(
                                f"[red] User '{base_credentials['user']}' "
                                f"has no access to '{target_db}'.[/red]"
                            )
                    else:
                        console.print("[yellow]⚠ Invalid selection.[/yellow]")

                except Exception as e:
                    console.print(f"[red] Could not fetch databases: {e}[/red]")
                continue

            # CMD: CONNECT — Full login wizard with server + DB selection
            elif clean_input.lower() in ["connect", "mindsql connect"]:
                console.print(Panel("[bold cyan]🔐 Server Login[/bold cyan]", box=box.ROUNDED))
                c_user = session.prompt([('class:prompt', 'Username (e.g., root): ')]).strip() or "root"
                c_pass = session.prompt([('class:prompt', 'Password: ')], is_password=True).strip()
                c_host = session.prompt([('class:prompt', 'Host (default: localhost): ')]).strip() or "localhost"

                server_url = f"mysql+pymysql://{c_user}:{c_pass}@{c_host}/"

                try:
                    # Verify credentials and fetch accessible databases
                    with console.status(f"[bold blue]Verifying credentials...[/bold blue]"):
                        temp_engine = create_engine(server_url)
                        with temp_engine.connect() as conn:
                            db_list = [row[0] for row in conn.execute(text("SHOW DATABASES;")).fetchall()]

                    console.print("\n[bold green]✅ Login Successful![/bold green]")
                    console.print("[bold cyan]Select a database:[/bold cyan]")
                    for idx, name in enumerate(db_list, 1):
                        console.print(f"  [bold yellow]{idx}.[/bold yellow] {name}")

                    choice = session.prompt([('class:prompt', '\nEnter number or name: ')]).strip()

                    target_db = None
                    if choice.isdigit() and 1 <= int(choice) <= len(db_list):
                        target_db = db_list[int(choice) - 1]
                    elif choice in db_list:
                        target_db = choice

                    # Always cache credentials after successful login
                    cache_credentials(c_user, c_pass, c_host)

                    if not target_db:
                        # No DB chosen — keep server engine alive for navigation
                        console.print(
                            "[yellow]⚠ No database selected. "
                            "Type 'switch', 'use <db_name>', or 'CREATE DATABASE <name>;'.[/yellow]"
                        )
                        engine         = None
                        db_url         = None
                        schema_context = ""
                        server_engine  = create_engine(server_url)  # navigation-only engine
                    else:
                        final_url  = f"mysql+pymysql://{c_user}:{c_pass}@{c_host}/{target_db}"
                        new_engine, _ = perform_connection(final_url)
                        if new_engine:
                            engine         = new_engine
                            db_url         = final_url
                            schema_context = load_file(SCHEMA_FILE) or ""
                            print_banner(final_url)

                except Exception as e:
                    console.print(f"[red] Login Failed: {e}[/red]")

                session.is_password = False
                continue

            # CMD: CONNECT db_name — Direct DB switch without wizard
            elif clean_input.lower().startswith("connect "):
                if not base_credentials["user"]:
                    console.print("[red] Please 'connect' first to set credentials.[/red]")
                    continue

                target_db_name = clean_input.split("connect ", 1)[1].strip()
                try:
                    new_url    = build_url(target_db_name)
                    new_engine, _ = perform_connection(new_url)
                    if new_engine:
                        engine         = new_engine
                        db_url         = new_url
                        schema_context = load_file(SCHEMA_FILE) or ""
                        print_banner(new_url)
                    else:
                        console.print(f"[red] Could not connect to '{target_db_name}'.[/red]")
                except Exception as e:
                    console.print(f"[red] Error: {e}[/red]")
                continue

            # --- PLOT MODE ---

            if user_input.lower().startswith("mindsql_plot"):
                print("Plotting the graph")
                #--reptition 1 begin---
                if not engine:
                    console.print("[red] Not connected.[/red]")
                    continue
                
                natural_prompt = user_input[12:].strip()
                
                # Plotting Prompt
                system_instruction = (
                    "You are a Data Visualization Assistant.\n"
                    "RULES:\n"
                    "1. Return SQL that produces EXACTLY 2 COLUMNS.\n"
                    "2. Column 1 = LABEL (Text).\n"
                    "3. Column 2 = VALUE (Number).\n"
                    "4. Output ONLY SQL.\n"
                    f"\nContext:\n{schema_context}"
                )
                
                messages = [
                    {'role': 'system', 'content': system_instruction},
                    {'role': 'user', 'content': natural_prompt}
                ]
                print(
                   "Understanding user query\n"
                   f"Mode : Plot Mode\n Message length : {len(messages)}\n System instruction lenght : {len(messages[0]['content'])}\n"
                   f"User prompt length: {len(messages[1]['content'])}\n"
                   "Schema included:", "Context:" in messages[0]['content']
                )
                with console.status(f"[bold yellow]📊 Generating Plot Data...[/bold yellow]", spinner="earth"):
                    sql_code = mindsql_start(messages)
                    if sql_code and validate_plot_sql(sql_code):
                        console.print(Panel(Syntax(sql_code, "sql", theme="monokai"), title="✨ Plotting SQL", border_style="yellow", box=box.ROUNDED))
                        if input("🚀 Run Plot? (y/n): ").strip().lower() == 'y':
                            print("Commencing sql execution....")
                            data = execute_sql(engine, sql_code, return_data=True)
                            if data: 
                                draw_ascii_bar_chart(data)
                        print("Execution completed")
                    else:
                        console.print("[red]❌ Invalid plot SQL. Must return LABEL + VALUE only.[/red]")

                #--reptition 1 end---

            # CMD --- CHAT MODE (Updated for Chain of Thought) ---
            elif user_input.lower().startswith("mindsql_ans"):
                if not engine:
                    console.print("[red] No database selected. Use 'switch', 'use <db_name>', or 'CREATE DATABASE <name>;'.[/red]")
                    continue

                natural_prompt = user_input[11:].strip()
                messages = [
                    {'role': 'system', 'content': (
                        "You are a Database Expert.\n"
                        "STEP 1: Briefly list the tables/columns you will use.\n"
                        "STEP 2: Write the SQL script.\n"
                        "CRITICAL: Only use columns that exist in the schema.\n"
                        f"\nContext:\n{schema_context}"
                    )},
                    {'role': 'user', 'content': natural_prompt}
                ]

                # No retry loop needed, just a single AI call
                with console.status("[bold green]💬 Asking AI...[/bold green]", spinner="dots"):
                    response      = llm.create_chat_completion(messages=messages, temperature=0.1)
                    full_response = response['choices'][0]['message']['content']

                # Print the AI's explanation and suggested SQL
                console.print(Panel(full_response, title="🤖 AI Answer",
                                    border_style="green", box=box.ROUNDED))

            # CMD: MINDSQL — Strict mode: LLM generates SQL only, validated
            elif user_input.lower().startswith("mindsql"):
                if not engine:
                    console.print("[red] No database selected. Use 'switch', 'use <db_name>', or 'CREATE DATABASE <name>;'.[/red]")
                    continue

                natural_prompt = user_input[7:].strip()
                messages = [
                    {'role': 'system', 'content': (
                        "You are a strict SQL generator.\n"
                        "1. Output ONLY valid SQL code — no explanation.\n"
                        "2. Verify all columns exist in the schema before using them.\n"
                        "3. Use exact table and column names from the schema.\n"
                        f"\nContext:\n{schema_context}"
                    )},
                    {'role': 'user', 'content': natural_prompt}
                ]

                for attempt in range(MAX_RETRIES):
                    with console.status(f"[bold yellow]Thinking (Attempt {attempt+1})...[/bold yellow]", spinner="earth"):
                        response = llm.create_chat_completion(messages=messages, temperature=0.1)
                        
                        # Do NOT fall back to raw content. If it's not SQL, let it be None.
                        generated_sql = extract_sql(response['choices'][0]['message']['content'])
                        
                        # Terminate gracefully if no SQL was found
                        if not generated_sql:
                            console.print(Panel(
                                "[bold yellow]⚠ Invalid request.[/bold yellow]\nI can only process database and SQL-related requests.", 
                                border_style="yellow", box=box.ROUNDED
                            ))
                            break # Exits the retry loop immediately

                        #--to check working of extract_table() & extract_columns()
                        tables, alias_map = extract_tables(generated_sql)
                        print(f"Tables:\n{tables}\nAliases:\n{alias_map}")

                    console.print(Panel(Syntax(generated_sql, "sql", theme="monokai"),
                                        title="Generated SQL", border_style="yellow", box=box.ROUNDED))

                    if input("Execute SQL? (y/n): ").strip().lower() != 'y':
                        break
                     # VALIDATE BEFORE EXECUTE
                    is_valid = validate_sql_schema(generated_sql, SCHEMA_MAP) 
                    
                    if is_valid is None:
                        break

                    if is_valid is False:
                        console.print(Panel(
                            "[bold red]Schema Validation Failed[/bold red]",
                            style="red"
                        ))
                        continue


                    try:
                        execute_sql(engine, generated_sql, raise_error=True)
                        # --- AI REFRESH LOGIC ---
                        if any(kw in generated_sql.upper() for kw in ["CREATE", "ALTER", "DROP", "RENAME", "TRUNCATE"]):
                            SCHEMA_MAP = load_schema_map(engine)
                            generate_schema_text(SCHEMA_MAP, SCHEMA_FILE)
                            schema_context = load_file(SCHEMA_FILE) or ""
                            console.print("[dim green]🔄 Schema cache updated by AI![/dim green]")
                        # ------------------------
                        break

                    except Exception as e:
                        if attempt < MAX_RETRIES - 1:
                            console.print(f"[yellow]⚠ Error: {e}. Retrying...[/yellow]")
                            messages.append({'role': 'assistant', 'content': generated_sql})
                            messages.append({'role': 'user', 'content': f"Error: {str(e)}. Fix SQL."})
                        else:
                            console.print(Panel(f"[bold red]Failed after {MAX_RETRIES} attempts[/bold red]\n{e}", style="red"))
                        #--reptition 3 end---

            # STANDARD SQL — Pass directly to the database engine
            # Server level commands are allowed even without a selected database
            else:
                upper_input = clean_input.upper()
                is_server_cmd = (
                    upper_input == "SHOW DATABASES" or 
                    upper_input.startswith("CREATE DATABASE") or 
                    upper_input.startswith("DROP DATABASE")
                )

                if is_server_cmd:
                    nav_engine = engine or server_engine
                    if nav_engine:
                        execute_sql(nav_engine, user_input)
                    else:
                        console.print("[red] Not connected. Please 'connect' first.[/red]")
                    continue

                if not engine:
                    console.print("[red] No database selected. Use 'switch', 'use <db_name>', or 'CREATE DATABASE <name>;'.[/red]")
                    continue

                execute_sql(engine, user_input)
                # --- REFRESH LOGIC ---
                # If the query changes the database structure, refresh the schema map and text file
                if any(keyword in clean_input.upper() for keyword in ["CREATE", "ALTER", "DROP", "RENAME", "TRUNCATE"]):
                    SCHEMA_MAP = load_schema_map(engine)
                    generate_schema_text(SCHEMA_MAP, SCHEMA_FILE)
                    
                    # Update the context for the LLM and the autocomplete engine
                    schema_context = load_file(SCHEMA_FILE) or ""
                    
                    console.print("[dim green]🔄 Schema cache updated![/dim green]")
                # --- NEW REFRESH LOGIC ENDS HERE ---


        except KeyboardInterrupt: continue
        except Exception as e: console.print(Panel(f"[bold red]Unexpected Error[/bold red]\n{e}", style="red"))

if __name__ == "__main__":
    app()


