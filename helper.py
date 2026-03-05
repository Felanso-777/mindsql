import os
import re
import sqlglot
from sqlglot import exp

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box

from sqlalchemy import inspect

console = Console()

# --- Helpers ---

# --load_file to open the required files--
def load_file(filename):
    if not os.path.exists(filename):
        return None
    with open(filename, "r") as f:
        return f.read().strip()
    
#to save user credentials
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
def validate_sql_schema(sql,SCHEMA_MAP):
    sql_upper  = sql.upper()
    tables,alias = extract_tables(sql)
    columns = extract_columns(sql)
    forbidden = ["CREATE","ALTER","DROP","DELETE"]
    valid_tables ={}
    #DDL cmd validation . prevents structural change.
    for keyword in forbidden : 
        if keyword in sql_upper : 
            return False 
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


#to add schema to schema.txt

def generate_schema_text(schema_map, schema_file):
    with open(schema_file, "w") as f:
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

#--Validator plot function --

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