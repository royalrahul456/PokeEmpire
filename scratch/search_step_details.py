import json

log_path = r"C:\Users\Rahul Pachute\.gemini\antigravity\brain\4fa879da-e65e-482d-99a4-162d252c2bb7\.system_generated\logs\transcript.jsonl"

with open(log_path, 'r', encoding='utf-8') as f:
    for line in f:
        try:
            data = json.loads(line)
            step = data.get("step_index")
            if step is not None and 2940 <= step <= 2960:
                print(f"=== STEP {step} ===")
                print("Source:", data.get("source"))
                print("Type:", data.get("type"))
                print("Content:", data.get("content"))
                # Print any file paths or attached media details
                for k, v in data.items():
                    if k not in ["content", "step_index", "source", "type"]:
                        print(f"{k}: {v}")
                print("-" * 50)
        except Exception as e:
            pass
