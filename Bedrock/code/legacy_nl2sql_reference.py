
import os
import re
import json
import boto3
import psycopg2
import pandas as pd
import sqlglot

from sqlglot import exp


# ==================================================
# 1. CONFIGURATION
# ==================================================

BEDROCK_REGION = "ap-southeast-2"
MODEL_ID = "apac.amazon.nova-micro-v1:0"

DATABASE_NAME = "postgres"
DATABASE_SCHEMA = "public"
DATABASE_USER = "nl2sql_user"

bedrock = boto3.client(
    "bedrock-runtime",
    region_name=BEDROCK_REGION
)


# ==================================================
# 2. DATABASE CONNECTION
# ==================================================

def get_connection():

    return psycopg2.connect(
        host=os.environ["DB_HOST"],
        port=os.environ.get("DB_PORT", "5432"),
        database=DATABASE_NAME,
        user=DATABASE_USER,
        password=os.environ["DB_PASSWORD"],
        sslmode="require",
        connect_timeout=10
    )


# ==================================================
# 3. RETRIEVE DATABASE SCHEMA
# ==================================================

def get_database_schema(conn):

    query = """
        SELECT
            table_name,
            column_name,
            data_type
        FROM information_schema.columns
        WHERE table_schema = %s
        ORDER BY table_name, ordinal_position;
    """

    with conn.cursor() as cursor:

        cursor.execute(query, (DATABASE_SCHEMA,))
        rows = cursor.fetchall()

    schema = {}

    for table, column, datatype in rows:

        if table not in schema:
            schema[table] = []

        schema[table].append(
            f"{column} ({datatype})"
        )

    if not schema:
        raise ValueError(
            f"No tables found in schema '{DATABASE_SCHEMA}'."
        )

    schema_text = ""

    for table, columns in schema.items():

        schema_text += (
            f"\nTable: {table}\n"
            f"Columns: {', '.join(columns)}\n"
        )

    return schema_text


# ==================================================
# 4. GENERATE SQL USING BEDROCK
# ==================================================

def generate_sql(question, schema):

    prompt = f"""
You are an expert PostgreSQL SQL developer.

Database: {DATABASE_NAME}
Schema: {DATABASE_SCHEMA}

Database schema:
{schema}

User question:
{question}

Instructions:

1. Generate PostgreSQL-compatible SQL.
2. Use only tables and columns from the supplied schema.
3. Use the public schema when referencing tables.
4. Generate exactly one SELECT query.
5. Never generate INSERT, UPDATE, DELETE,
   DROP, ALTER, CREATE or TRUNCATE statements.
6. Do not use SELECT INTO.
7. Do not generate markdown or explanations.
8. Use appropriate JOINs and aggregations.
9. Limit results to 100 rows unless fewer are requested.

Return only the SQL query.
"""

    response = bedrock.converse(
        modelId=MODEL_ID,
        messages=[
            {
                "role": "user",
                "content": [
                    {"text": prompt}
                ]
            }
        ],
        inferenceConfig={
            "maxTokens": 700,
            "temperature": 0.1
        }
    )

    sql = response["output"]["message"]["content"][0]["text"]

    sql = re.sub(
        r"^```(?:sql)?\s*|\s*```$",
        "",
        sql.strip(),
        flags=re.IGNORECASE
    )

    return sql.strip()


# ==================================================
# 5. VALIDATE GENERATED SQL
# ==================================================

def validate_sql(sql):

    statements = sqlglot.parse(
        sql,
        read="postgres"
    )

    statements = [
        statement
        for statement in statements
        if statement is not None
    ]

    if len(statements) != 1:
        raise ValueError(
            "Only one SQL statement is allowed."
        )

    tree = statements[0]

    if not isinstance(tree, exp.Select):
        raise ValueError(
            "Only SELECT queries are allowed."
        )

    forbidden = (
        exp.Insert,
        exp.Update,
        exp.Delete,
        exp.Create,
        exp.Drop,
        exp.Alter,
        exp.Merge,
        exp.Command
    )

    for kind in forbidden:

        if next(tree.find_all(kind), None) is not None:
            raise ValueError(
                "Modifying SQL operations are not allowed."
            )

    if tree.args.get("into") is not None:
        raise ValueError(
            "SELECT INTO is not allowed."
        )

    # Enforce a maximum of 100 returned rows.
    limit = tree.args.get("limit")

    if limit is None:
        tree = tree.limit(100)

    else:
        try:
            requested_limit = int(
                limit.expression.this
            )

            if requested_limit > 100:
                tree = tree.limit(100)

        except (AttributeError, TypeError, ValueError):
            raise ValueError(
                "Invalid SQL LIMIT expression."
            )

    return tree.sql(dialect="postgres")


# ==================================================
# 6. EXECUTE SQL
# ==================================================

def execute_sql(conn, sql):

    conn.rollback()

    try:

        conn.set_session(
            readonly=True,
            autocommit=False
        )

        with conn.cursor() as cursor:

            cursor.execute(
                "SET LOCAL statement_timeout = '15000ms'"
            )

            cursor.execute(sql)

            columns = [
                description[0]
                for description in cursor.description
            ]

            rows = cursor.fetchmany(100)

        conn.commit()

        return pd.DataFrame(
            rows,
            columns=columns
        )

    except Exception:

        conn.rollback()
        raise


# ==================================================
# 7. EXPLAIN RESULTS USING BEDROCK
# ==================================================

def explain_results(question, sql, dataframe):

    result_data = dataframe.to_dict(
        orient="records"
    )

    prompt = f"""
You are a professional data analyst.

Original question:
{question}

SQL executed:
{sql}

Query results:
{json.dumps(result_data, default=str)}

Explain the results in simple language.

Instructions:
1. Answer the original question directly.
2. Mention important numbers and patterns.
3. Do not invent information.
4. If no records are returned, clearly state that.
5. Keep the explanation concise.
"""

    response = bedrock.converse(
        modelId=MODEL_ID,
        messages=[
            {
                "role": "user",
                "content": [
                    {"text": prompt}
                ]
            }
        ],
        inferenceConfig={
            "maxTokens": 500,
            "temperature": 0.2
        }
    )

    return response["output"]["message"]["content"][0]["text"]


# ==================================================
# 8. MAIN APPLICATION
# ==================================================

def main():

    print("\n===================================")
    print("         NORTHWIND NL2SQL")
    print("===================================")

    conn = None

    try:

        print("\nConnecting to RDS PostgreSQL...")

        conn = get_connection()

        print("Database connection successful.")

        print("\nRetrieving database schema...")

        schema = get_database_schema(conn)

        print("Schema retrieved successfully.")

        print(schema)

        while True:

            question = input(
                "\nEnter your question (or type exit): "
            ).strip()

            if question.lower() == "exit":
                break

            if not question:
                continue

            try:

                print("\nGenerating SQL using Bedrock...")

                sql = generate_sql(
                    question,
                    schema
                )

                sql = validate_sql(sql)

                print("\nGenerated SQL:")
                print(sql)

                print("\nExecuting SQL against RDS...")

                results = execute_sql(
                    conn,
                    sql
                )

                print("\nQuery Results:")

                if results.empty:
                    print("No records found.")

                else:
                    print(
                        results.to_string(index=False)
                    )

                print("\nGenerating explanation...")

                explanation = explain_results(
                    question,
                    sql,
                    results
                )

                print("\n===================================")
                print("             ANSWER")
                print("===================================")

                print(explanation)

            except Exception as error:

                print(f"\nQuery Error: {error}")

    except Exception as error:

        print(f"\nApplication Error: {error}")

    finally:

        if conn is not None:
            conn.close()

        print("\nDatabase connection closed.")


if __name__ == "__main__":
    main()
