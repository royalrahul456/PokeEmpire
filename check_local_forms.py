import asyncio
import sqlite3

def check_db():
    conn = sqlite3.connect("pokeempire.db")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM pokemon_form_media")
    rows = cursor.fetchall()
    print("pokemon_form_media rows:")
    for r in rows:
        print(r)
    conn.close()

check_db()
