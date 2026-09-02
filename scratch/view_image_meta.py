import os
import json

brain_dir = r"C:\Users\Rahul Pachute\.gemini\antigravity\brain\4fa879da-e65e-482d-99a4-162d252c2bb7"

for f in os.listdir(brain_dir):
    if f.endswith(".metadata.json"):
        path = os.path.join(brain_dir, f)
        with open(path, 'r', encoding='utf-8') as file:
            print(f"=== {f} ===")
            print(json.load(file))
            print("-" * 50)
