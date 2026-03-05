import re


# -------------------------------------------------
# Extract tables and columns from CREATE statements
# -------------------------------------------------
def extract_schema(schema_text):
    tables = {}
    pattern = r"CREATE TABLE (\w+)\s*\((.*?)\);"
    matches = re.findall(pattern, schema_text, re.DOTALL | re.IGNORECASE)

    for table_name, columns_block in matches:
        columns = []
        lines = columns_block.split(",")

        for line in lines:
            parts = line.strip().split()
            if parts:
                col_name = parts[0]
                if col_name.upper() not in [
                    "PRIMARY", "FOREIGN", "UNIQUE", "KEY", "CONSTRAINT"
                ]:
                    columns.append(col_name)

        tables[table_name.lower()] = columns

    return tables


# -------------------------------------------------
# MAIN SUGGESTION ENGINE
# -------------------------------------------------
def generate_suggestions(user_input, schema_text):

    schema = extract_schema(schema_text)
    text = user_input.rstrip("?").strip()
    lower_text = text.lower()

    words = lower_text.split()
    suggestions = []

    SQL_KEYWORDS = [
        "SELECT", "INSERT", "UPDATE", "DELETE",
        "CREATE", "DROP", "ALTER",
        "FROM", "WHERE", "SET", "VALUES",
        "GROUP BY", "ORDER BY", "LIMIT",
        "JOIN", "LEFT JOIN", "RIGHT JOIN",
        "INNER JOIN", "ON"
    ]

    # -------------------------------------
    # If empty → show basic keywords
    # -------------------------------------
    if not lower_text:
        return SQL_KEYWORDS

    # -------------------------------------
    # SELECT
    # -------------------------------------
    if lower_text.startswith("select"):

        # SELECT ?
        if "from" not in lower_text:
            for table in schema:
                suggestions.extend(schema[table])
            suggestions.append("*")
            suggestions.append("FROM")
            return suggestions

        # SELECT * FROM ?
        if lower_text.endswith("from"):
            suggestions.extend(schema.keys())
            return suggestions

        # After FROM table
        match = re.search(r"from\s+(\w+)", lower_text)
        if match:
            table_name = match.group(1)

            if table_name in schema:

                # After table name
                if lower_text.endswith(table_name):
                    suggestions.extend([
                        "WHERE",
                        "GROUP BY",
                        "ORDER BY",
                        "LIMIT",
                        "JOIN"
                    ])
                    return suggestions

                # WHERE
                if "where" in lower_text:
                    suggestions.extend(schema[table_name])
                    return suggestions

                # JOIN
                if "join" in lower_text:
                    suggestions.extend(schema.keys())
                    suggestions.append("ON")
                    return suggestions

    # -------------------------------------
    # INSERT
    # -------------------------------------
    if lower_text.startswith("insert"):

        # INSERT ?
        if len(words) == 1:
            suggestions.append("INTO")
            return suggestions

        # INSERT INTO ?
        if lower_text.endswith("into"):
            suggestions.extend(schema.keys())
            return suggestions

        # INSERT INTO table
        match = re.search(r"insert into\s+(\w+)", lower_text)
        if match:
            table_name = match.group(1)

            if table_name in schema:
                if lower_text.endswith(table_name):
                    suggestions.append("(")
                    suggestions.append("VALUES")
                    return suggestions

                if "(" in lower_text and "values" not in lower_text:
                    suggestions.extend(schema[table_name])
                    suggestions.append(")")
                    return suggestions

                if "values" in lower_text:
                    suggestions.append("(")
                    return suggestions

    # -------------------------------------
    # UPDATE
    # -------------------------------------
    if lower_text.startswith("update"):

        # UPDATE ?
        if len(words) == 1:
            suggestions.extend(schema.keys())
            return suggestions

        match = re.search(r"update\s+(\w+)", lower_text)
        if match:
            table_name = match.group(1)

            if table_name in schema:

                if lower_text.endswith(table_name):
                    suggestions.append("SET")
                    return suggestions

                if "set" in lower_text and "where" not in lower_text:
                    suggestions.extend(schema[table_name])
                    suggestions.append("=")
                    suggestions.append("WHERE")
                    return suggestions

                if "where" in lower_text:
                    suggestions.extend(schema[table_name])
                    return suggestions

    # -------------------------------------
    # DELETE
    # -------------------------------------
    if lower_text.startswith("delete"):

        if len(words) == 1:
            suggestions.append("FROM")
            return suggestions

        if lower_text.endswith("from"):
            suggestions.extend(schema.keys())
            return suggestions

        match = re.search(r"delete from\s+(\w+)", lower_text)
        if match:
            table_name = match.group(1)

            if table_name in schema:
                suggestions.append("WHERE")
                return suggestions

    # -------------------------------------
    # CREATE
    # -------------------------------------
    if lower_text.startswith("create"):
        suggestions.append("TABLE")
        suggestions.append("DATABASE")
        return suggestions

    # -------------------------------------
    # DROP
    # -------------------------------------
    if lower_text.startswith("drop"):
        suggestions.append("TABLE")
        suggestions.append("DATABASE")
        suggestions.extend(schema.keys())
        return suggestions

    # -------------------------------------
    # ALTER
    # -------------------------------------
    if lower_text.startswith("alter"):
        suggestions.append("TABLE")
        suggestions.extend(schema.keys())
        return suggestions

    # -------------------------------------
    # Generic fallback
    # -------------------------------------
    suggestions.extend(SQL_KEYWORDS)
    suggestions.extend(schema.keys())

    return list(set(suggestions))
