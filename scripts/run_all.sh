#!/usr/bin/env bash
# Runs the whole platform end to end. Usage: bash scripts/run_all.sh
set -euo pipefail
cd "$(dirname "$0")/.."
set -a; source .env; set +a

echo "== 0. tests";                     python -m pytest -q
echo "== 1. generate raw data";         python data/generate_data.py
echo "== 2. M1+M2 ingest and rules";    python -m ingestion.ingest && python -m ingestion.rules
echo "== 3. M4 load PostgreSQL";        python -m ingestion.load_pg
echo "== 4. M3 business queries";       PGPASSWORD="$PG_PASSWORD" psql -h "$PG_HOST" -p "$PG_PORT" -U "$PG_USER" -d "$PG_DB" -v ON_ERROR_STOP=1 -f sql/queries.sql > sql/queries_output.txt && echo "   -> sql/queries_output.txt"
echo "== 5. M5 load MongoDB";           python -m mongo.mongo_load && python -m mongo.pipelines
echo "== 6. M6 notebook + raw export";  jupyter nbconvert --to notebook --execute --inplace notebooks/analysis.ipynb
echo "== 7. M7 dbt";                    (cd warehouse && dbt seed && dbt snapshot && dbt build && dbt docs generate)
echo "== done. Optional SCD2 demo: python scripts/apply_customer_moves.py && (cd warehouse && dbt snapshot && dbt build)"
