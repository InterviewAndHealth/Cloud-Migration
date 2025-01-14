import os
import pathlib

import dotenv
import psycopg2
from psycopg2 import sql
from psycopg2.extras import execute_batch

path = pathlib.Path(__file__).parent.absolute() / ".env"
dotenv.load_dotenv(dotenv_path=path, override=True)

HOST_SOURCE = os.getenv("HOST_SOURCE")
PORT_SOURCE = os.getenv("PORT_SOURCE")
USER_SOURCE = os.getenv("USER_SOURCE")
PASSWORD_SOURCE = os.getenv("PASSWORD_SOURCE")

HOST_DEST = os.getenv("HOST_DEST")
PORT_DEST = os.getenv("PORT_DEST")
USER_DEST = os.getenv("USER_DEST")
PASSWORD_DEST = os.getenv("PASSWORD_DEST")

EXCLUDED_DATABASES = os.getenv("EXCLUDED_DATABASES", "")

if not all(
    [
        HOST_SOURCE,
        PORT_SOURCE,
        USER_SOURCE,
        PASSWORD_SOURCE,
        HOST_DEST,
        PORT_DEST,
        USER_DEST,
        PASSWORD_DEST,
    ]
):
    raise ValueError("Please provide all required environment variables.")

SOURCE_DB_CONFIG = {
    "host": HOST_SOURCE,
    "port": PORT_SOURCE,
    "user": USER_SOURCE,
    "password": PASSWORD_SOURCE,
    "dbname": "postgres",  # Default connection to fetch DB names
}

DEST_DB_CONFIG = {
    "host": HOST_DEST,
    "port": PORT_DEST,
    "user": USER_DEST,
    "password": PASSWORD_DEST,
    "dbname": "postgres",  # Default connection
}


EXCLUDED_DATABASES = EXCLUDED_DATABASES.strip().split(",")
EXCLUDED_DATABASES.append("postgres")


def disableForeignKeyConstraints(connection):
    """
    Disable foreign key constraints on the specified connection
    by setting session_replication_role to 'replica'.
    """
    print("INFO: Disabling foreign key constraints...")
    with connection.cursor() as cursor:
        cursor.execute("SET session_replication_role = 'replica';")
        connection.commit()
    print("INFO: Foreign key constraints disabled.")


def enableForeignKeyConstraints(connection):
    """
    Enable foreign key constraints by resetting session_replication_role to 'origin'.
    """
    with connection.cursor() as cursor:
        cursor.execute("SET session_replication_role = 'origin';")
        connection.commit()
    print("INFO: Foreign key constraints enabled.")


def getForeignKeyTableDependencies(connection):
    """
    Retrieve foreign key dependencies among tables in the current database.

    Returns:
        A list of tuples (child_table, parent_table).
    """
    query = """
        SELECT
            tc.table_name AS child_table,
            ccu.table_name AS parent_table
        FROM
            information_schema.table_constraints AS tc
        JOIN information_schema.constraint_column_usage AS ccu
            ON tc.constraint_name = ccu.constraint_name
        WHERE
            tc.constraint_type = 'FOREIGN KEY';
    """
    with connection.cursor() as cursor:
        cursor.execute(query)
        dependencies = cursor.fetchall()
    return dependencies


def determineTableTransferOrder(tables, dependencies):
    """
    Determine an order in which to transfer table data based on foreign key dependencies.

    Args:
        tables (list): A list of table names.
        dependencies (list): A list of foreign key relationships.

    Returns:
        A list of table names in the recommended transfer order.
    """
    from collections import defaultdict, deque

    graph = defaultdict(list)
    indegree = defaultdict(int)

    # Build dependency graph
    for child, parent in dependencies:
        graph[parent].append(child)
        indegree[child] += 1

    # Add tables without dependencies
    for table in tables:
        if table not in indegree:
            indegree[table] = 0

    # Perform topological sort
    queue = deque([table for table, degree in indegree.items() if degree == 0])
    order = []

    while queue:
        current = queue.popleft()
        order.append(current)
        for neighbor in graph[current]:
            indegree[neighbor] -= 1
            if indegree[neighbor] == 0:
                queue.append(neighbor)

    return order


def fetchNonTemplateDatabases(connection):
    """
    Fetch all non-template databases from the PostgreSQL instance.

    Returns:
        A list of database names.
    """
    with connection.cursor() as cursor:
        cursor.execute("SELECT datname FROM pg_database WHERE datistemplate = false;")
        databases = cursor.fetchall()
    return [db[0] for db in databases]


def fetchDatabaseTables(connection):
    """
    Fetch all tables in the current database.

    Returns:
        A list of table names.
    """
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public';
        """
        )
        tables = cursor.fetchall()
    return [table[0] for table in tables]


def transferTableData(source_conn, dest_conn, table_name):
    """
    Transfer data from the specified table in source_conn to an identical table in dest_conn,
    logging progress and the total rows transferred.
    """
    print(f"INFO: Starting data transfer for table '{table_name}'...")
    with source_conn.cursor() as source_cursor, dest_conn.cursor() as dest_cursor:
        # Fetch data from source
        source_cursor.execute(
            sql.SQL("SELECT * FROM {}").format(sql.Identifier(table_name))
        )
        rows = source_cursor.fetchall()

        # Get column names
        col_names = [desc[0] for desc in source_cursor.description]

        # Prepare the INSERT query
        insert_query = sql.SQL("INSERT INTO {} ({}) VALUES ({})").format(
            sql.Identifier(table_name),
            sql.SQL(", ").join(map(sql.Identifier, col_names)),
            sql.SQL(", ").join(sql.Placeholder() * len(col_names)),
        )

        # Insert data into Azure
        execute_batch(dest_cursor, insert_query, rows)
        dest_conn.commit()

        print(f"SUCCESS: Transferred {len(rows)} rows from table '{table_name}'.")


def transferDatabaseContent(source_db_name, dest_db_name):
    """
    Transfer data for all tables from the source database to the destination database.
    Added extra logs for clarity.
    """
    print(f"INFO: Connecting to source database: {source_db_name}")
    print(f"INFO: Connecting to destination database: {dest_db_name}")
    source_conn = psycopg2.connect(**{**SOURCE_DB_CONFIG, "dbname": source_db_name})
    dest_conn = psycopg2.connect(**{**DEST_DB_CONFIG, "dbname": dest_db_name})

    try:
        # Get tables in the source database
        tables = fetchDatabaseTables(source_conn)
        print(f"INFO: Found tables in database '{source_db_name}': {tables}")

        # Fetch dependencies and determine order
        dependencies = getForeignKeyTableDependencies(source_conn)
        transfer_order = determineTableTransferOrder(tables, dependencies)
        print(f"INFO: Transfer order for tables: {transfer_order}")

        # Disable constraints on Azure
        print(f"INFO: Disabling constraints in {dest_db_name}...")
        disableForeignKeyConstraints(dest_conn)

        # Transfer each table in order
        for table in transfer_order:
            transferTableData(source_conn, dest_conn, table)

        # Enable constraints on Azure
        print("INFO: Re-enabling constraints...")
        enableForeignKeyConstraints(dest_conn)

    finally:
        source_conn.close()
        dest_conn.close()


def main():
    """
    Main function to orchestrate the migration process.
    Logs progress for each database being transferred.
    """
    # Connect to source and destination databases
    source_conn = psycopg2.connect(**SOURCE_DB_CONFIG)
    dest_conn = psycopg2.connect(**DEST_DB_CONFIG)

    try:
        # Fetch all non-template databases from the source
        databases = fetchNonTemplateDatabases(source_conn)
        print(f"INFO: Found databases in source db: {databases}")

        # Transfer each database
        for db_name in databases:
            if db_name in EXCLUDED_DATABASES:
                continue
            print(f"INFO: Transferring database: {db_name}")
            transferDatabaseContent(db_name, db_name)

    finally:
        source_conn.close()
        dest_conn.close()


if __name__ == "__main__":
    main()
