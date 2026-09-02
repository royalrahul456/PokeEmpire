import sqlite3
conn = sqlite3.connect('pokeempire.db')
cursor = conn.cursor()
cursor.execute("SELECT id, name, rarity, generation FROM pokemon LIMIT 50")
rows = cursor.fetchall()
print("First 50 Pokémon in database:")
for r in rows:
    print(r)
conn.close()
