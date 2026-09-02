import json

log_path = r"C:\Users\Rahul Pachute\.gemini\antigravity\brain\4fa879da-e65e-482d-99a4-162d252c2bb7\.system_generated\logs\transcript.jsonl"

with open(log_path, 'r', encoding='utf-8') as f:
    for line in f:
        try:
            data = json.loads(line)
            step = data.get("step_index")
            if step == 2948:
                print(json.dumps(data, indent=2))
        except Exception as e:
            pass
