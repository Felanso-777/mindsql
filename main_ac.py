#SCHEMA_MAP = dict
#tables = set
#alias = dict
#columns = list of dict
#valid_tables = dict

import typer

from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.styles import Style

from sqlalchemy.engine.url import make_url
from sqlalchemy import text

from rich.console import Console
from rich.syntax import Syntax
from rich.panel import Panel
from rich import box

# AI
import ollama

# DB connector
from db_connector import perform_connection, SCHEMA_FILE, DB_URL_FILE 

SCHEMA_MAP = {}

# Helpers
from helper import (
    load_file,
    save_file,
    extract_tables,
    extract_columns,
    validate_sql_schema,
    extract_sql,
    print_banner,
    draw_ascii_bar_chart,
    validate_plot_sql,
)


# --- Configuration ---
MODEL_NAME = "qwen2.5-coder:1.5b"
#SCHEMA_FILE = "schema.txt"
#DB_URL_FILE = "db_config.txt"
HISTORY_FILE = "mindsql_history.txt"
MAX_RETRIES = 3



# --- Setup ---
app = typer.Typer()
console = Console()




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
    if db_url:
        # _ is Python convention for “unused variable”
        engine, SCHEMA_MAP= perform_connection(db_url)
        schema_context = load_file(SCHEMA_FILE)
    else : 
        schema_context = None
    style = Style.from_dict({ 'prompt': 'ansicyan bold' })
    session = PromptSession(history=FileHistory(HISTORY_FILE), style=style)
    


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
                
                new_engine, new_schema = perform_connection(target)
                SCHEMA_MAP = new_schema
                if new_engine:
                    engine = new_engine
                    db_url = target
                    schema_context = load_file(SCHEMA_FILE)
                    print_banner(target)
                    print("VALID TABLES:", SCHEMA_MAP.keys())
                    print("SCHEMA MAP :",SCHEMA_MAP )
                    
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
                        is_valid = validate_sql_schema(sql_code, SCHEMA_MAP)
                    if not is_valid:
                        console.print(Panel("[bold red]❌ Schema Validation Failed[/bold red]", style="red"))
                        continue
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

                    # AI returned explanation not SQL
                    if not sql_code:
                        continue

                    is_valid = validate_sql_schema(sql_code, SCHEMA_MAP)
                    if not is_valid:
                        console.print(Panel(
                            "[bold red]❌ Schema Validation Failed[/bold red]",
                            style="red"
                        ))
                        continue
                    else:
                        console.print(Panel(
                            "[bold green]✅ Schema Validation Passed[/bold green]",
                            style="green"
                        ))

                    
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
                        "3. Use EXACT table names from schema (case-sensitive).\n"

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
                    
                    
                    if input("🚀 Execute SQL? (y/n): ").strip().lower() != 'y':
                        break

                    # VALIDATE BEFORE EXECUTE
                    is_valid = validate_sql_schema(generated_sql, SCHEMA_MAP)
                    if not is_valid:
                        console.print(Panel(
                            "[bold red]❌ Schema Validation Failed[/bold red]",
                            style="red"
                        ))
                        continue
                    else:
                        console.print(Panel(
                            "[bold green]✅ Schema Validation Passed[/bold green]",
                            style="green"
                        ))


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

                is_valid = validate_sql_schema(user_input, SCHEMA_MAP)
                if not is_valid:
                    console.print(Panel(
                        "[bold red]❌ Schema Validation Failed[/bold red]",
                        style="red"
                    ))
                    continue
                else:
                    console.print(Panel(
                        "[bold green]✅ Schema Validation Passed[/bold green]",
                        style="green"
                    ))

                execute_sql(engine, user_input)

        except KeyboardInterrupt: continue
        except Exception as e: console.print(Panel(f"Error: {e}", style="red"))

if __name__ == "__main__":
    app()


