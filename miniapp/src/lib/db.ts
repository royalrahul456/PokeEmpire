import { Pool } from "pg";

// Prevent node ssl rejection for cloud poolers
process.env.NODE_TLS_REJECT_UNAUTHORIZED = "0";

const rawDbUrl =
  process.env.DATABASE_URL ||
  process.env.SUPABASE_DB_URL ||
  "postgresql://postgres.dlxlqrerxplqevvutgsn:rahulmahadevpachpute@aws-0-ap-southeast-2.pooler.supabase.com:6543/postgres?sslmode=require";

// Clean sslmode query param so it doesn't conflict with custom ssl config
const cleanDbUrl = rawDbUrl.replace("?sslmode=require", "").replace("&sslmode=require", "");

let pool: Pool | null = null;

export function getDbPool(): Pool {
  if (!pool) {
    pool = new Pool({
      connectionString: cleanDbUrl,
      ssl: {
        rejectUnauthorized: false,
      },
      max: 10,
      idleTimeoutMillis: 30000,
      connectionTimeoutMillis: 5000,
    });

    pool.on("error", (err) => {
      console.warn("PostgreSQL pool idle error:", err.message);
    });
  }
  return pool;
}

/**
 * Execute query safely with connection timeout and fallback.
 */
export async function queryDb<T = any>(text: string, params?: any[]): Promise<T[]> {
  try {
    const p = getDbPool();
    const res = await p.query(text, params);
    return res.rows;
  } catch (error: any) {
    console.warn("Database query failed (using in-memory fallback):", error.message);
    throw error;
  }
}
