import sqlite3
conn = sqlite3.connect('pokeempire.db')
cursor = conn.cursor()
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
print("Tables:", cursor.fetchall())

try:
    cursor.execute("SELECT * FROM pokemon_form_media LIMIT 5")
    print("Pokemon Form Media:", cursor.fetchall())
except Exception as e:
    print("Error querying pokemon_form_media:", e)

conn.close()
