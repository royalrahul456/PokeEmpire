import json
import os
import config

def check():
    json_path = os.path.join(config.DATA_DIR, "pokemon_seeds.json")
    if os.path.exists(json_path):
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        rarities = {}
        for r in data:
            rarities[r["rarity"]] = rarities.get(r["rarity"], 0) + 1
        print("pokemon_seeds.json rarities:", rarities)
        
    monsters_path = os.path.join(config.DATA_DIR, "monsters.json")
    if os.path.exists(monsters_path):
        with open(monsters_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        rarities = {}
        for r_id, r in data.items():
            rarities[r["tier"]] = rarities.get(r["tier"], 0) + 1
        print("monsters.json rarities:", rarities)

if __name__ == '__main__':
    check()
