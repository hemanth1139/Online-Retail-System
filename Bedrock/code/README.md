# Northwind NL2SQL with Amazon Bedrock Tool Use

A terminal-based Natural Language to SQL application using Amazon Bedrock Converse API Tool Use, Amazon Nova Micro, PostgreSQL on Amazon RDS, and SQLGlot.

## Architecture

1. User enters a natural-language question in the terminal.
2. Amazon Nova Micro receives system instructions and tool definitions.
3. Bedrock requests `get_database_schema` to inspect live PostgreSQL metadata.
4. Bedrock requests `execute_sql_query` with a generated SELECT statement.
5. Python validates the query with SQLGlot and executes it in a read-only transaction.
6. The tool result is returned to Bedrock through a `toolResult` block.
7. Bedrock produces the final natural-language answer.

## Project layout

- `nl2sql.py`: terminal entry point
- `core/bedrock_client.py`: Converse API and Tool Use loop
- `core/tool_executor.py`: dispatches Bedrock tool requests
- `core/database.py`: PostgreSQL connection, live schema inspection and read-only execution
- `core/sql_validator.py`: SQLGlot validation and query limits
- `tools/tool_definitions.py`: Bedrock tool JSON schemas
- `tools/schema_tool.py`: schema retrieval tool
- `tools/sql_tool.py`: SQL execution tool
- `config/database_schema.json`: schema snapshot supplied for Northwind
- `config/schema_relationships.json`: foreign-key snapshot
- `config/few_shot_examples.json`: example question/SQL pairs
- `prompts/`: model instructions

## Setup

### 1. Create and activate a virtual environment

Linux / WSL:
```bash
python3 -m venv .venv
source .venv/bin/activate
```

Windows PowerShell:
```powershell
py -m venv .venv
.venv\\Scripts\\Activate.ps1
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment

Copy `.env.example` to `.env`, then set the RDS endpoint and database password.

Linux / WSL:
```bash
cp .env.example .env
```

Windows PowerShell:
```powershell
Copy-Item .env.example .env
```

Do not commit `.env`.

### 4. Configure AWS authentication

Use one supported authentication method:

**Bedrock API key:** set `AWS_BEARER_TOKEN_BEDROCK` in the process environment or in `.env` if your installed boto3/botocore version supports Bedrock bearer-token authentication. Keep the key private.

**AWS credentials / IAM role:** configure the AWS credential chain, for example with `aws configure`, an AWS profile, or an attached IAM role. The identity needs permission to invoke the selected Bedrock model.

The application uses `boto3.client("bedrock-runtime", region_name=AWS_REGION)`. If bearer-token authentication is not recognized, update boto3/botocore and verify the current Bedrock API-key support for your SDK version.

### 5. Run

```bash
python nl2sql.py
```

Try:
- Show the top 5 customers by number of orders.
- Which products have stock at or below their reorder level?
- Show total sales by product.
- How many orders were shipped to Germany?

## Safety design

- SQLGlot parses SQL using the PostgreSQL dialect.
- Only one SELECT statement is accepted.
- DML and common DDL/administrative statement types are rejected.
- SELECT INTO and row-locking clauses are rejected.
- Cross-schema table references are rejected.
- A hard maximum row limit is applied.
- Queries execute in a read-only transaction with a statement timeout.
- Database credentials are read from environment variables.

For stronger production security, also enforce read-only access using a dedicated PostgreSQL role with SELECT privileges only on approved tables. Application-side validation is not a substitute for database permissions.

## Notes and limitations

- The static schema JSON reflects the table/column/foreign-key information supplied during project setup. Runtime schema retrieval is authoritative and also discovers primary keys.
- Few-shot examples are starter examples and should be expanded using tested, representative questions from your own database.
- The model may decide whether and when to call tools. The system prompt instructs it to inspect schema before generating SQL.
- This is a project prototype, not a production multi-user service. Add authentication, audit logging, rate limits, monitoring and stricter table/function allowlists before deployment.
