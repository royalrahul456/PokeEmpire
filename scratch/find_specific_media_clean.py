import json

log_path = r"C:\Users\Rahul Pachute\.gemini\antigravity\brain\4fa879da-e65e-482d-99a4-162d252c2bb7\.system_generated\logs\transcript_full.jsonl"

with open(log_path, 'r', encoding='utf-8') as f:
    for line in f:
        try:
            data = json.loads(line)
            if data.get("type") == "CHECKPOINT":
                continue
            content = data.get("content", "")
            if "media__1781972442575" in content or "pokedex" in content.lower():
                if data.get("type") == "USER_INPUT":
                    print(f"=== STEP {data.get('step_index')} ===")
                    print("Content:", content)
                    print("=" * 60)
        except Exception as e:
            pass
