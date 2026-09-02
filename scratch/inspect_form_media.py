import sqlite3
conn = sqlite3.connect('pokeempire.db')
cursor = conn.cursor()
cursor.execute("SELECT * FROM pokemon_form_media")
rows = cursor.fetchall()
print("All Form Media:", rows)
conn.close()
