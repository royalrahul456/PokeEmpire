import asyncio
import sys
import os

# Add parent directory to sys.path so we can import modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from database.database import init_db

async def test():
    print("Testing self-healing database migrations...")
    try:
        await init_db()
        print("Success: Database migrations and tables initialized successfully!")
    except Exception as e:
        print(f"Error during database migrations: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test())
