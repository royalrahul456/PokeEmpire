import asyncio
import asyncpg

SUPABASE_DB_URL = "postgresql://postgres:rahulmahadevpachpute@db.dlxlqrerxplqevvutgsn.supabase.co:5432/postgres"

async def main():
    print("Connecting to Supabase PostgreSQL...")
    conn = await asyncpg.connect(SUPABASE_DB_URL)
    try:
        tables = await conn.fetch("""
            SELECT tablename FROM pg_tables WHERE schemaname = 'public';
        """)
        table_names = [r['tablename'] for r in tables]
        print(f"Found {len(table_names)} tables in public schema: {table_names}")

        for tbl in table_names:
            await conn.execute(f'ALTER TABLE public."{tbl}" ENABLE ROW LEVEL SECURITY;')
            print(f"[OK] Enabled RLS on public.{tbl}")

        print("\nRow Level Security (RLS) enabled on all tables successfully!")
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
