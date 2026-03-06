import typer
import re
import os
import sys
from time import sleep
from rich.console import Console
from rich.syntax import Syntax
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich import box
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine.url import make_url
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.styles import Style
from sql_autofill import generate_suggestions  # for new feature
import sql_autofill
print("Autofill file path:", sql_autofill.__file__)
from sql_completer import SQLCompleter  # for new feature







# --- Llama.cpp Integration ---
from llama_cpp import Llama

# --- Configuration ---
# UPDATE THIS PATH to your local .gguf file
MODEL_PATH = "models/qwen2.5-coder-3b-instruct-q4_k_m.gguf" 
SCHEMA_FILE = "schema.txt"
DB_URL_FILE = "db_config.txt"
HISTORY_FILE = "mindsql_history.txt"
MAX_RETRIES = 3

# --- 1. DIAGNOSTIC CHECK (ADD THIS HERE) ---
print("--- System Diagnostic ---")
print("Loading model from path: models/your_model.gguf")

try:
    # Set verbose=True to see the internal loading logs in your terminal
    llm = Llama(model_path="models/qwen2.5-coder-3b-instruct-q4_k_m.gguf", verbose=True, n_ctx=512)
    print("✅ Model loaded successfully!")
except Exception as e:
    print(f"❌ ERROR: Model failed to load. Reason: {e}")
    exit(1) # Stop the script if the model isn't working

# --- Setup ---
app = typer.Typer()
console = Console()

# Initialize Llama.cpp
# n_ctx: context window, n_threads: CPU cores to use
try:
    llm = Llama(
        model_path=MODEL_PATH,
        n_ctx=4096,
        n_threads=os.cpu_count(),
        verbose=False  # Set to True if you want to see loading logs
    )
except Exception as e:
    console.print(f"[bold red]Failed to load model from {MODEL_PATH}[/bold red]")
    console.print(e)
    sys.exit(1)

# --- Helpers ---
def load_file(filename):
    if not os.path.exists(filename): return None
    with open(filename, "r") as f: return f.read().strip()

def save_file(filename, content):
    with open(filename, "w") as f: f.write(content)

def extract_sql(text):
    match = re.search(r"```sql\s*(.*?)\s*```", text, re.DOTALL | re.IGNORECASE)
    if match: return match.group(1).strip()
    match = re.search(r"```\s*(.*?)\s*```", text, re.DOTALL)
    if match: return match.group(1).strip()
    
    clean_text = text.strip()
    keywords = ["SELECT", "INSERT", "UPDATE", "DELETE", "CREATE", "DROP", "SET", "ALTER", "BEGIN", "WITH"]
    if any(clean_text.upper().startswith(k) for k in keywords):
        return clean_text
    return None

def get_llama_completion(messages):
    """Bridge function to replace ollama.chat"""
    response = llm.create_chat_completion(
        messages=messages,
        temperature=0.1,  # Keep temperature low for structured data/SQL
        max_tokens=1024
    )
    return response['choices'][0]['message']['content']

def print_banner(db_url):
    console.clear()
    banner_text = Text("MindSQL v10.3 (Llama.cpp Edition)", style="bold magenta", justify="center")
    info_text = f"\n[bold cyan]Connected to:[/bold cyan] {db_url}\n"
    info_text += "[dim]──────────────────────────────────────────────[/dim]\n"
    info_text += "• [bold cyan]mindsql <text>[/bold cyan]       : Strict SQL\n"
    info_text += "• [bold cyan]mindsql_ans <text>[/bold cyan]   : Chat & Explain\n"
    info_text += "• [bold yellow]mindsql_plot <text>[/bold yellow]  : Generate Charts 📊\n"
    info_text += "• [bold red]exit[/bold red]                  : Quit"
    console.print(Panel(info_text, title=banner_text, border_style="blue", box=box.ROUNDED, padding=(1, 2)))

def perform_connection(connection_string):
    with console.status(f"[bold blue]🔌 Connecting to {connection_string}...[/bold blue]", spinner="dots"):
        try:
            engine = create_engine(connection_string)
            inspector = inspect(engine)
            table_names = inspector.get_table_names()
            
            if not table_names:
                console.print("[yellow]⚠ Connected, but DB is empty.[/yellow]")
            else:
                with open(SCHEMA_FILE, "w") as f:
                    for table_name in table_names:
                        columns = inspector.get_columns(table_name)
                        f.write(f"CREATE TABLE {table_name} (\n")
                        col_defs = [f"    {col['name']} {col['type']}" for col in columns]
                        f.write(",\n".join(col_defs))
                        f.write("\n);\n\n")
            
            save_file(DB_URL_FILE, connection_string)
            return engine, table_names
        except Exception as e:
            console.print(Panel(f"[bold red]Connection Failed[/bold red]\n{e}", style="red"))
            return None, []

def draw_ascii_bar_chart(data):
    if not data: return
    try:
        clean_data = [(str(row[0]), float(row[1])) for row in data if row[1] is not None]
    except: return
    if not clean_data: return
    
    max_label_len = max(len(d[0]) for d in clean_data)
    max_val = max(d[1] for d in clean_data)
    bar_width = 40 
    console.print(Panel("[bold]📊 Analysis Result[/bold]", style="blue", box=box.MINIMAL, expand=False))

    for label, value in clean_data:
        filled_len = int((value / max_val) * bar_width) if max_val > 0 else 0
        bar = "█" * filled_len
        color = "spring_green1" if value >= (max_val * 0.7) else "yellow" if value >= (max_val * 0.3) else "red"
        console.print(f"{label.rjust(max_label_len)} │ [{color}]{bar}[/{color}]  [bold white]{value}[/bold white]")

def execute_sql(engine, sql: str, raise_error=False, return_data=False):
    try:
        commands = [c.strip() for c in sql.split(';') if c.strip()]
        with engine.connect() as conn:
            trans = conn.begin()
            last_result_data = [] 
            try:
                for i, cmd in enumerate(commands):
                    if cmd.upper() in ['BEGIN', 'COMMIT', 'ROLLBACK']: continue
                    result = conn.execute(text(cmd))
                    if result.returns_rows:
                        rows = result.fetchall()
                        last_result_data = rows 
                        if not return_data:
                            table = Table(box=box.ROUNDED, header_style="bold magenta", border_style="blue", title=f"Result {i+1}")
                            for key in result.keys(): table.add_column(key, style="cyan")
                            for row in rows: table.add_row(*[str(item) for item in row])
                            console.print(table)
                trans.commit()
                return last_result_data if return_data else None
            except Exception as e:
                trans.rollback()
                raise e
    except Exception as e:
        if raise_error: raise e
        console.print(Panel(f"[bold red]SQL Execution Error[/bold red]\n{e}", style="red"))

@app.command()
def shell():
    db_url = load_file(DB_URL_FILE)
    #engine = create_engine(db_url) if db_url else None
    #schema_context = load_file(SCHEMA_FILE)
    engine = None
    schema_context = None

    if db_url:
    # FORCE schema regeneration on startup
        engine, _ = perform_connection(db_url)
        schema_context = load_file(SCHEMA_FILE)
    print("DEBUG: Schema loaded =", schema_context is not None)
    print("DEBUG: Schema length =", len(schema_context) if schema_context else 0)
    style = Style.from_dict({ 'prompt': 'ansicyan bold' })
    #session = PromptSession(history=FileHistory(HISTORY_FILE), style=style)
    completer = SQLCompleter(schema_context)  # for new feature
    session = PromptSession(
    history=FileHistory(HISTORY_FILE),
    style=style,
    completer=completer,        # for new feature
    complete_while_typing=True  # for new feature
)


    if engine: print_banner(db_url)

    while True:
        try:
            user_input = session.prompt([('class:prompt', 'SQL> ')]).strip()
            if not user_input: continue
            if user_input.lower() in ["exit", "quit"]: break

            if user_input.lower().startswith("connect "):
                target = user_input.split("connect ", 1)[1].strip()
                new_engine, _ = perform_connection(target)
                if new_engine:
                    engine, db_url = new_engine, target
                    schema_context = load_file(SCHEMA_FILE)
                    print_banner(target)
                continue

            # --- PLOT MODE ---
            if user_input.lower().startswith("mindsql_plot"):
                if not engine: continue
                prompt = user_input[12:].strip()
                messages = [
                    {'role': 'system', 'content': f"Output ONLY SQL producing 2 columns: Label (Text), Value (Number).\nContext:\n{schema_context}"},
                    {'role': 'user', 'content': prompt}
                ]
                with console.status("[bold yellow]📊 Generating Plot...[/bold yellow]"):
                    sql_code = extract_sql(get_llama_completion(messages))
                
                if sql_code:
                    console.print(Panel(Syntax(sql_code, "sql", theme="monokai"), title="Plot SQL"))
                    if session.prompt("🚀 Run Plot? (y/n): ").lower() == 'y':
                        data = execute_sql(engine, sql_code, return_data=True)
                        draw_ascii_bar_chart(data)

            # --- CHAT MODE ---
            elif user_input.lower().startswith("mindsql_ans"):
                if not engine: continue
                prompt = user_input[11:].strip()
                messages = [
                    {'role': 'system', 'content': f"Database Expert. Step 1: Verify schema. Step 2: Write SQL.\nContext:\n{schema_context}"},
                    {'role': 'user', 'content': prompt}
                ]
                for attempt in range(MAX_RETRIES):
                    with console.status(f"[bold green]💬 Thinking (Attempt {attempt+1})...[/bold green]"):
                        ans = get_llama_completion(messages)
                    console.print(Panel(ans, title="🤖 AI Answer", border_style="green"))
                    sql_code = extract_sql(ans)
                    if sql_code and session.prompt("🚀 Run SQL? (y/n): ").lower() == 'y':
                        try:
                            execute_sql(engine, sql_code, raise_error=True)
                            break
                        except Exception as e:
                            messages.append({'role': 'assistant', 'content': ans})
                            messages.append({'role': 'user', 'content': f"Error: {e}. Re-check schema."})
                    else: break

            # --- STRICT MODE ---
            elif user_input.lower().startswith("mindsql"):
                if not engine: continue
                prompt = user_input[7:].strip()
                messages = [
                    {'role': 'system', 'content': f"Strict SQL generator. Output ONLY SQL.\nContext:\n{schema_context}"},
                    {'role': 'user', 'content': prompt}
                ]
                for attempt in range(MAX_RETRIES):
                    with console.status(f"[bold yellow]🧠 Thinking...[/bold yellow]"):
                        sql_code = extract_sql(get_llama_completion(messages))
                    console.print(Panel(Syntax(sql_code, "sql", theme="monokai"), title="✨ SQL"))
                    if session.prompt("🚀 Run? (y/n): ").lower() == 'y':
                        try:
                            execute_sql(engine, sql_code, raise_error=True)
                            break
                        except Exception as e:
                            messages.append({'role': 'user', 'content': f"Error: {e}. Fix SQL."})
                    else: break
            else:
                if engine: execute_sql(engine, user_input)

        except KeyboardInterrupt: continue
        except Exception as e: console.print(f"[red]Error: {e}[/red]")

if __name__ == "__main__":
    app()