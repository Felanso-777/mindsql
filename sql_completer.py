# sql_completer.py

import re
import os
from collections import Counter
from prompt_toolkit.completion import Completer, Completion

# 1. The Context Map: Defines what logically follows what
CONTEXT_MAP = {
    "select": ["FROM", "WHERE", "GROUP BY", "ORDER BY", "LIMIT", "COUNT", "MAX", "MIN", "AVG", "SUM", "DISTINCT", "CAST", "COALESCE"],
    "insert": ["INTO"],
    "into": ["VALUES"],
    "update": ["SET", "WHERE"],
    "set": ["WHERE"],
    "delete": ["FROM"],
    "from": ["JOIN", "LEFT JOIN", "RIGHT JOIN", "INNER JOIN", "FULL OUTER JOIN", "CROSS JOIN", "WHERE", "GROUP BY", "ORDER BY", "LIMIT", "AS"],
    "join": ["ON", "USING"],
    "where": ["AND", "OR", "IN", "LIKE", "ILIKE", "BETWEEN", "IS NULL", "IS NOT NULL", "EXISTS", "GROUP BY", "ORDER BY", "LIMIT"],
    "by": ["ORDER BY", "LIMIT", "DESC", "ASC"], 
    "order": ["BY"],
    "group": ["BY"],
    "having": ["AND", "OR", "COUNT", "MAX", "MIN", "AVG", "SUM"],
    "begin": ["TRANSACTION"],
    "commit": ["TRANSACTION"],
    "rollback": ["TO", "TRANSACTION"],
    "savepoint": [],
    "create": ["TABLE", "DATABASE", "INDEX", "VIEW", "TRIGGER", "PROCEDURE"],
    "drop": ["TABLE", "DATABASE", "INDEX", "VIEW", "IF EXISTS"],
    "alter": ["TABLE", "COLUMN"],
    "table": ["ADD", "DROP", "MODIFY", "ALTER COLUMN"],
    "add": ["COLUMN", "CONSTRAINT", "PRIMARY KEY", "FOREIGN KEY"],
    "grant": ["ALL PRIVILEGES", "SELECT", "INSERT", "UPDATE", "DELETE", "ON"],
    "revoke": ["ALL PRIVILEGES", "SELECT", "INSERT", "UPDATE", "DELETE", "ON"],
    "on": ["TO", "FROM"],
    "with": ["AS"],
    "union": ["ALL"],
}

ALL_KEYWORDS = [
    "SELECT", "INSERT", "UPDATE", "DELETE", "FROM", "WHERE", "VALUES", "SET",
    "CREATE", "DROP", "ALTER", "TRUNCATE", "TABLE", "DATABASE", "INDEX", "VIEW",
    "JOIN", "INNER JOIN", "LEFT JOIN", "RIGHT JOIN", "FULL OUTER JOIN", "ON", "USING", "UNION", "INTERSECT", "EXCEPT",
    "GROUP BY", "ORDER BY", "HAVING", "LIMIT", "OFFSET", "AS", "WITH", "AND", "OR", "NOT", "IN", "BETWEEN", "LIKE", "IS NULL", "EXISTS",
    "BEGIN", "COMMIT", "ROLLBACK", "SAVEPOINT",
    "COUNT", "SUM", "AVG", "MIN", "MAX", "COALESCE", "CAST", "CONCAT", "SUBSTRING", "ROUND", "NOW", "CURRENT_DATE",
    "PRIMARY KEY", "FOREIGN KEY", "UNIQUE", "NOT NULL", "DEFAULT", "INT", "VARCHAR", "TEXT", "BOOLEAN", "DATE", "TIMESTAMP"
]

class SQLCompleter(Completer):
    def __init__(self, history_file, get_schema_map_func):
        """
        Pass a getter function for schema_map because the global dictionary 
        gets reassigned when the database structure changes.
        """
        self.history_file = history_file
        self.get_schema_map = get_schema_map_func

    def get_user_frequencies(self):
        freq_map = Counter()
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, "r") as f:
                    content = f.read().lower()
                    tokens = re.findall(r'\b\w+\b', content)
                    freq_map.update(tokens)
            except Exception:
                pass 
        return freq_map

    def get_completions(self, document, complete_event):
        text_before_cursor = document.text_before_cursor.lower()
        word_before_cursor = document.get_word_before_cursor()
        
        typed_tokens = re.findall(r'\b\w+\b', text_before_cursor)
        suggestions = set()
        
        # Get the LIVE schema map from main_ac.py
        schema_map = self.get_schema_map()
        
        # --- A. CONTEXT-AWARE KEYWORDS ---
        if not typed_tokens:
            suggestions.update(ALL_KEYWORDS)
        else:
            last_token = typed_tokens[-1]
            if last_token == word_before_cursor.lower() and len(typed_tokens) > 1:
                last_token = typed_tokens[-2] 
                
            if last_token in CONTEXT_MAP:
                suggestions.update(CONTEXT_MAP[last_token])
            else:
                if "select" in typed_tokens and "from" not in typed_tokens:
                    suggestions.add("FROM")
                suggestions.update(ALL_KEYWORDS)

        # --- B. SCHEMA AWARENESS (Tables and Columns) ---
        active_tables = [token for token in typed_tokens if token in schema_map]
        
        if last_token in ["from", "join", "update", "into", "table"]:
            suggestions.update(schema_map.keys())
            
        if "select" in typed_tokens or "where" in typed_tokens or "set" in typed_tokens or "by" in typed_tokens:
            if not active_tables:
                for table_info in schema_map.values():
                    # Fixed to read "columns" list from the inner dict
                    suggestions.update(table_info.get("columns", []))
            else:
                for table in set(active_tables):
                    suggestions.update(schema_map[table].get("columns", []))

        # --- C. FILTER BY CURRENT TYPING ---
        valid_suggestions = [s for s in suggestions if s.lower().startswith(word_before_cursor.lower())]
        
        # --- D. SORT BY USER FREQUENCY ---
        freq_map = self.get_user_frequencies()
        valid_suggestions.sort(key=lambda x: freq_map.get(x.lower(), 0), reverse=True)

        # --- E. YIELD TO TERMINAL ---
        for suggestion in valid_suggestions:
            yield Completion(suggestion, start_position=-len(word_before_cursor))