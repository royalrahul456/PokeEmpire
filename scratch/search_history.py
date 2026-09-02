import json

log_path = r"C:\Users\Rahul Pachute\.gemini\antigravity\brain\4fa879da-e65e-482d-99a4-162d252c2bb7\.system_generated\logs\transcript.jsonl"

with open(log_path, 'r', encoding='utf-8') as f:
    for line in f:
        try:
            data = json.loads(line)
            if data.get("type") == "USER_INPUT":
                content = data.get("content", "")
                content_lower = content.lower()
                if any(w in content_lower for w in ["pokedex", "stars", "suggest", "look"]):
                    print(f"=== STEP {data.get('step_index')} ===")
                    print(content)
                    print("-" * 50)
        except Exception as e:
            pass
