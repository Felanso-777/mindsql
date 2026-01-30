import typer
import ollama
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
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine.url import make_url
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.styles import Style

# --- Configuration ---
MODEL_NAME = "qwen2.5-coder:1.5b"
SCHEMA_FILE = "schema.txt"
DB_URL_FILE = "db_config.txt"
HISTORY_FILE = "mindsql_history.txt"
MAX_RETRIES = 3
SCHEMA_MAP = {}


# --- Setup ---
app = typer.Typer()
console = Console()

# --- Helpers ---

# --load_file to open the required files--
def load_file(filename):
    if not os.path.exists(filename):
        return None
    with open(filename, "r") as f:
        return f.read().strip()

def save_file(filename, content):
    with open(filename, "w") as f:
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
"""def validate_sql_schema(sql,SCHEMA_MAP):
    tables = extract_tables(sql)
    columns = extract_columns(sql)
    alias = {}
    for table in tables :
        #here we map alias to table 

            
     
    for column in columns :
        if column not in SCHEMA_MAP:
            return False
    
    return True"""

#--Load Schema --
def load_schema_map(engine):
    schema = {}
    inspector = inspect(engine)
    table_names =  inspector.get_table_names();
    for table in table_names:
        columns = inspector.get_columns(table)
        column_names = [col["name"] for col in columns]
        foreign_keys=[]
        for fk in inspector.get_foreign_keys(table):
            foreign_keys.append({"child_columns" : fk["constrained_columns"],
                                 "parent_table" : fk["referred_table"],
                                 "parent_columns" : fk["referred_columns"]})
        schema[table] = {"columns" : column_names,
                            "foreign_keys" : foreign_keys}
       
    return schema

def extract_sql(text):
    # 1. Look for markdown blocks
    match = re.search(r"```sql\s*(.*?)\s*```", text, re.DOTALL | re.IGNORECASE)
    if match: return match.group(1).strip()
    match = re.search(r"```\s*(.*?)\s*```", text, re.DOTALL)
    if match: return match.group(1).strip()
    
    # 2. Look for raw SQL statements (if no markdown)
    clean_text = text.strip()
    keywords = ["SELECT", "INSERT", "UPDATE", "DELETE", "CREATE", "DROP", "SET", "ALTER", "BEGIN", "WITH"]
    if any(clean_text.upper().startswith(k) for k in keywords):
        return clean_text
    return None

# --to display the staring lines --
def print_banner(db_url):
    console.clear()
    banner_text = Text("MindSQL v10.3 (Chain of Thought)", style="bold magenta", justify="center")
    
    info_text = f"\n[bold cyan]Connected to:[/bold cyan] {db_url}\n"
    info_text += "[dim]──────────────────────────────────────────────[/dim]\n"
    info_text += "• [bold cyan]mindsql <text>[/bold cyan]       : Strict SQL\n"
    info_text += "• [bold cyan]mindsql_ans <text>[/bold cyan]   : Chat & Explain\n"
    info_text += "• [bold yellow]mindsql_plot <text>[/bold yellow]  : Generate Charts 📊\n"
    info_text += "• [bold red]exit[/bold red]                  : Quit"

    console.print(Panel(
        info_text,
        title=banner_text,
        border_style="blue",
        box=box.ROUNDED,
        padding=(1, 2)
    ))
    
#--Initialising DB connection--

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
                        col_defs = []
                        for col in columns:
                            col_str = f"    {col['name']} {col['type']}"
                            col_defs.append(col_str)
                        f.write(",\n".join(col_defs))
                        f.write("\n);\n\n")
            
            save_file(DB_URL_FILE, connection_string)
            global SCHEMA_MAP
            SCHEMA_MAP = load_schema_map(engine)
            return engine, table_names
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
def mindsql_start(messages):
    response = ollama.chat(model=MODEL_NAME, messages=messages)

    print("\n[AI RESPONSE DEBUG]")
    print("Raw response length:", len(str(response)))

    ai_text = response.message.content
    print("AI output length:", len(ai_text))
    print("AI output preview:", ai_text[:200])

    sql_code = extract_sql(ai_text)
    return sql_code


    

# --- Commands ---

@app.command()
def connect(connection_string: str):
    pass 

@app.command()
def shell():
    print("Initialising......")
    db_url = load_file(DB_URL_FILE)
    engine = None
    if db_url: engine = create_engine(db_url)
    
    schema_context = load_file(SCHEMA_FILE)
    style = Style.from_dict({ 'prompt': 'ansicyan bold' })
    session = PromptSession(history=FileHistory(HISTORY_FILE), style=style)
    
  #to check whether the dictionary schema_map is allocatted or not (debugging)  
    schema_map = load_schema_map(engine)
    print(schema_map)

    if engine: print_banner(db_url)

    while True:
        try:
            user_input = session.prompt([('class:prompt', 'SQL> ')]).strip()
            print("User typed : ",user_input)
            if not user_input: continue
            
            if user_input.lower().startswith("sql>"): user_input = user_input[4:].strip()
            if user_input.lower() in ["exit", "quit"]: break
            print("Establishing connection with DB....")
            if user_input.lower().startswith("mindsql connect ") or user_input.lower().startswith("connect "):
                target = user_input.split("connect ", 1)[1].strip()
                if "://" not in target and db_url:
                    try:
                        target = str(make_url(db_url).set(database=target))
                    except: pass
                
                new_engine, tables = perform_connection(target)
                if new_engine:
                    engine = new_engine
                    db_url = target
                    schema_context = load_file(SCHEMA_FILE)
                    print_banner(target)
                    
                continue

            # --- PLOT MODE ---

            if user_input.lower().startswith("mindsql_plot"):
                print("Plotting the graph")
                #--reptition 1 begin---
                if not engine:
                    console.print("[red]❌ Not connected.[/red]")
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
                   f"Mode : Plot Mode\n Message length : {len(messages)}\n System instruction lenght : {len(messages[0]["content"])}\n"
                   f"User prompt length: {len(messages[1]["content"])}\n"
                   "Schema included:", "Context:" in messages[0]["content"]
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

            # --- CHAT MODE (Updated for Chain of Thought) ---
            elif user_input.lower().startswith("mindsql_ans"):
                print("Entering chat mode...")
                #--reptition 2 begin---
                if not engine:
                    console.print("[red]❌ Not connected.[/red]")
                    continue

                natural_prompt = user_input[11:].strip()
                
                # --- NEW CHAIN OF THOUGHT SYSTEM PROMPT ---
                system_instruction = (
                    "You are a Database Expert.\n"
                    "CRITICAL: Before writing SQL, you must VERIFY that every column exists in the Context.\n"
                    "STEP 1: Briefly list the tables/columns you plan to use and confirm they are in the schema.\n"
                    "STEP 2: Write the SQL script (using semicolons for multiple steps).\n"
                    "----------------\n"
                    "RULES:\n"
                    "1. DO NOT HALLUCINATE: If a direct link (like Enrollments.teacher_id) is missing, find a valid path (e.g., Teachers->Depts->Courses).\n"
                    "2. TO DELETE STUDENT: Delete Grades -> Enrollments -> Attendance -> Student.\n"
                    f"\nContext:\n{schema_context}"
                )

                messages = [
                    {'role': 'system', 'content': system_instruction},
                    {'role': 'user', 'content': natural_prompt}
                ]
                print(
                   "Understanding user query\n"
                   f"Mode : Chat Mode\n Message length : {len(messages)}\n System instruction lenght : {len(messages[0]["content"])}\n"
                   f"User prompt length: {len(messages[1]["content"])}\n"
                   "Schema included:", "Context:" in messages[0]["content"]
                )

                for attempt in range(MAX_RETRIES):
                    with console.status(f"[bold green]💬 Asking AI (Attempt {attempt+1})...[/bold green]", spinner="dots"):
                        response = ollama.chat(model=MODEL_NAME, messages=messages)
                        print("\n[AI RESPONSE DEBUG]")                       
                        print("Raw response length:", len(str(response)))
                        full_response = response['message']['content']
                        ai_text = response.message.content
                        print("AI output length:", len(ai_text))
                        print("AI output preview:", ai_text[:200])
                    
                    console.print(Panel(full_response, title="🤖 AI Answer", border_style="green", box=box.ROUNDED))
                    
                    sql_code = extract_sql(full_response)
                    
                    if sql_code:
                        if input("▶ Execute suggested SQL? (y/n): ").strip().lower() == 'y':
                            try:
                                execute_sql(engine, sql_code, raise_error=True)
                                break 
                            except Exception as e:
                                if attempt < MAX_RETRIES - 1:
                                    console.print(f"[yellow]⚠ Script Error: {e}. Retrying...[/yellow]")
                                    messages.append({'role': 'assistant', 'content': full_response})
                                    messages.append({'role': 'user', 'content': f"Execution failed: {str(e)}. RE-CHECK THE SCHEMA. Do not use invalid columns."})
                                else:
                                    console.print(f"[bold red]❌ Failed after {MAX_RETRIES} attempts.[/bold red]")
                        else: break
                    else: break
                   #--reptition 2 end---

            # --- STRICT MODE ---
            elif user_input.lower().startswith("mindsql"):
                print("Strict mode on ")
                #--reptition 3 begin---
                if not engine:
                    console.print("[red]❌ Not connected.[/red]")
                    continue
                
                natural_prompt = user_input[7:].strip()
                messages = [
                    {'role': 'system', 'content': (
                        "You are a strict SQL generator.\n"
                        "1. Output ONLY SQL code. Separate with semicolons (;).\n"
                        "2. VERIFY COLUMNS EXIST before writing.\n"
                        f"\nContext:\n{schema_context}"
                    )},
                    {'role': 'user', 'content': natural_prompt}
                ]
                print(
                   "Understanding user query\n"
                   f"Mode : Strict ai  Mode\n Message length : {len(messages)}\n System instruction lenght : {len(messages[0]["content"])}\n"
                   f"User prompt length: {len(messages[1]["content"])}\n"
                   "Schema included:", "Context:" in messages[0]["content"]
                )
                for attempt in range(MAX_RETRIES):
                    with console.status(f"[bold yellow]🧠 Thinking (Attempt {attempt+1})...[/bold yellow]", spinner="earth"):
                        response = ollama.chat(model=MODEL_NAME, messages=messages)
                        print("\n[AI RESPONSE DEBUG]")
                        print("Raw response length:", len(str(response)))
                        ai_text = response.message.content
                        print("AI output length:", len(ai_text))
                        print("AI output preview:", ai_text[:200])
                        
                        generated_sql = extract_sql(response['message']['content']) or response['message']['content']  

                        #--to check working of extract_table() & extract_columns()
                        tables, alias_map = extract_tables(generated_sql)
                        print(f"Tables:\n{tables}\nAliases:\n{alias_map}")
 
                        print(f"\nColumns found \n{extract_columns(generated_sql)}\n")   

                    console.print(Panel(Syntax(generated_sql, "sql", theme="monokai"), title="✨ Generated SQL", border_style="yellow", box=box.ROUNDED))
                    
                    
                    if input("🚀 Execute SQL? (y/n): ").strip().lower() != 'y': break 

                    try:
                        execute_sql(engine, generated_sql, raise_error=True)
                        break 
                    except Exception as e:
                        if attempt < MAX_RETRIES - 1:
                            console.print(f"[yellow]⚠ Error: {e}. Retrying...[/yellow]")
                            messages.append({'role': 'assistant', 'content': generated_sql})
                            messages.append({'role': 'user', 'content': f"Error: {str(e)}. Fix SQL."})
                        else:
                            console.print(Panel(f"[bold red]Failed after {MAX_RETRIES} attempts[/bold red]\n{e}", style="red"))
                        #--reptition 3 end---

            # --- STANDARD SQL ---
            else:
                print("Reverting to normal mode....")
                if not engine:
                    console.print("[red]❌ Not connected.[/red]")
                    continue
                execute_sql(engine, user_input)

        except KeyboardInterrupt: continue
        except Exception as e: console.print(Panel(f"Error: {e}", style="red"))

if __name__ == "__main__":
    app()


