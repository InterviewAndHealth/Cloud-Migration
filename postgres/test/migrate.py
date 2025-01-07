import psycopg2
from psycopg2 import sql
from psycopg2.extras import execute_batch

# Connection details for both databases
AWS_DB_CONFIG = {
    "host": "127.0.0.1",
    "port": 5432,
    "user": "aws-user",
    "password": "aws-password",
    "dbname": "postgres",  # Default connection to fetch DB names
}

AZURE_DB_CONFIG = {
    "host": "127.0.0.1",
    "port": 5433,
    "user": "azure-user",
    "password": "azure-password",
    "dbname": "postgres",  # Default connection
}

EXCLUDED_DATABASES = [
    "postgres",
    "aws-user",
    "azure-user",
]


def disable_constraints(connection):
    """Temporarily disable foreign key constraints."""
    with connection.cursor() as cursor:
        cursor.execute("SET session_replication_role = 'replica';")
        connection.commit()


def enable_constraints(connection):
    """Re-enable foreign key constraints."""
    with connection.cursor() as cursor:
        cursor.execute("SET session_replication_role = 'origin';")
        connection.commit()


def get_foreign_key_dependencies(connection):
    """Fetch foreign key dependencies for tables in the database."""
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


def get_table_transfer_order(tables, dependencies):
    """Determine the transfer order of tables based on foreign key dependencies."""
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


def get_databases(connection):
    """Fetch all databases from the PostgreSQL instance."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT datname FROM pg_database WHERE datistemplate = false;")
        databases = cursor.fetchall()
    return [db[0] for db in databases]


def get_tables(connection):
    """Fetch all tables in the current database."""
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


def transfer_table_data(aws_conn, azure_conn, table_name):
    """Transfer data from one table in AWS to Azure."""
    with aws_conn.cursor() as aws_cursor, azure_conn.cursor() as azure_cursor:
        # Fetch data from AWS
        aws_cursor.execute(
            sql.SQL("SELECT * FROM {}").format(sql.Identifier(table_name))
        )
        rows = aws_cursor.fetchall()

        # Get column names
        col_names = [desc[0] for desc in aws_cursor.description]

        # Prepare the INSERT query
        insert_query = sql.SQL("INSERT INTO {} ({}) VALUES ({})").format(
            sql.Identifier(table_name),
            sql.SQL(", ").join(map(sql.Identifier, col_names)),
            sql.SQL(", ").join(sql.Placeholder() * len(col_names)),
        )

        # Insert data into Azure
        execute_batch(azure_cursor, insert_query, rows)
        azure_conn.commit()

        print(f"Transferred {len(rows)} rows from table '{table_name}'.")


def transfer_database_data(aws_db_name, azure_db_name):
    """Transfer data for all tables in a database."""
    aws_conn = psycopg2.connect(**{**AWS_DB_CONFIG, "dbname": aws_db_name})
    azure_conn = psycopg2.connect(**{**AZURE_DB_CONFIG, "dbname": azure_db_name})

    try:
        # Get tables in the source database
        tables = get_tables(aws_conn)
        print(f"Found tables in database '{aws_db_name}': {tables}")

        # Fetch dependencies and determine order
        dependencies = get_foreign_key_dependencies(aws_conn)
        transfer_order = get_table_transfer_order(tables, dependencies)
        print(f"Transfer order for tables: {transfer_order}")

        # Disable constraints on Azure
        disable_constraints(azure_conn)

        # Transfer each table in order
        for table in transfer_order:
            transfer_table_data(aws_conn, azure_conn, table)

        # Enable constraints on Azure
        enable_constraints(azure_conn)

    finally:
        aws_conn.close()
        azure_conn.close()


def main():
    # Connect to AWS and Azure default databases
    aws_conn = psycopg2.connect(**AWS_DB_CONFIG)
    azure_conn = psycopg2.connect(**AZURE_DB_CONFIG)

    try:
        # Fetch all non-template databases from AWS
        databases = get_databases(aws_conn)
        print(f"Found databases in AWS: {databases}")

        # Transfer each database
        for db_name in databases:
            if db_name in EXCLUDED_DATABASES:
                continue
            print(f"Transferring database: {db_name}")
            transfer_database_data(db_name, db_name)

    finally:
        aws_conn.close()
        azure_conn.close()


if __name__ == "__main__":
    main()
