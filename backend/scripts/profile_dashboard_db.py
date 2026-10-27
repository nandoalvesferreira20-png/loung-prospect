"""Read-only latency probe: no business rows, JWTs, migrations or credentials in output."""
import argparse
import json
from time import perf_counter
from pathlib import Path
from dotenv import dotenv_values
import psycopg
from psycopg.conninfo import conninfo_to_dict
from backend.persistence.postgres import TABLES


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--env-file', required=True, type=Path)
    args = parser.parse_args()
    dsn = dotenv_values(args.env_file).get('LOUNG_POSTGRES_DSN', '')
    if conninfo_to_dict(dsn).get('user', '').split('.')[0] != 'loung_web':
        raise SystemExit('Refused: restricted loung_web login required')
    samples = []
    for _ in range(3):
        started = perf_counter()
        with psycopg.connect(dsn, connect_timeout=5, autocommit=True) as connection:
            sample = {'connect_ms': round((perf_counter() - started) * 1000, 1)}
            connection.execute('BEGIN READ ONLY')
            try:
                connection.execute('SET LOCAL ROLE loung_api')
                started = perf_counter()
                original = {}
                for table in sorted(TABLES):
                    original[table] = [row[0] for row in connection.execute("SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name=%s ORDER BY ordinal_position", (table,)).fetchall()]
                sample['six_metadata_ms'] = round((perf_counter() - started) * 1000, 1)
                started = perf_counter()
                rows = connection.execute("SELECT table_name,column_name FROM information_schema.columns WHERE table_schema='public' AND table_name=ANY(%s) ORDER BY table_name,ordinal_position", (sorted(TABLES),)).fetchall()
                sample['batched_metadata_ms'] = round((perf_counter() - started) * 1000, 1)
                batched = {table: [] for table in TABLES}
                for table, column in rows:
                    batched[table].append(column)
                assert original == batched, 'Metadata result mismatch'
                samples.append(sample)
            finally:
                connection.execute('ROLLBACK')
    print(json.dumps({'read_only': True, 'business_rows_read': False, 'metadata_equivalent': True, 'samples': samples}, indent=2))


if __name__ == '__main__':
    try:
        main()
    except psycopg.Error as error:
        print(json.dumps({'result': 'failed', 'error_type': type(error).__name__, 'sqlstate': error.sqlstate}))
        raise SystemExit(1) from None
