from sqlalchemy import create_engine, inspect
import sys

def scan_database(connection_string):
    """
    Connects to the DB, reads table structures, and writes schema.txt
    """
    print(f"🔌 Connecting to: {connection_string}...")

    try:
        # 1. Connect to the Database
        engine = create_engine(connection_string)
        inspector = inspect(engine)

        # 2. Open schema.txt for writing
        with open("schema.txt", "w") as f:

            # 3. Loop through all tables found in the DB
            table_names = inspector.get_table_names()

            if not table_names:
                print("⚠ No tables found in this database!")
                return

            print(f"✓ Found {len(table_names)} tables. analyzing...")

            for table_name in table_names:
                # Get columns for this table
                columns = inspector.get_columns(table_name)

                # Write the CREATE TABLE statement to the file
                f.write(f"CREATE TABLE {table_name} (\n")

                col_defs = []
                for col in columns:
                    # Extract name and type (e.g., 'id INTEGER')
                    col_str = f"    {col['name']} {col['type']}"
                    col_defs.append(col_str)

                f.write(",\n".join(col_defs))
                f.write("\n);\n\n")

        print(f"✅ Success! Database structure saved to 'schema.txt'.")

    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    # Allow running this file directly for testing
    if len(sys.argv) > 1:
        scan_database(sys.argv[1])
    else:
        print("Usage: python3 db_connector.py <connection_string>")