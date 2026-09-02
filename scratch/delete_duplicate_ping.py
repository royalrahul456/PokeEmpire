import os

file_path = r"c:\Users\Rahul Pachute\Downloads\coding\PokeEmpire\handlers\start.py"

with open(file_path, "r", encoding="utf-8") as f:
    lines = f.readlines()

# Let's find the second definition of @router.message(Command("ping"))
ping_occurrences = []
for idx, line in enumerate(lines):
    if '@router.message(Command("ping"))' in line:
        ping_occurrences.append(idx)

print("Found ping command at line indices:", ping_occurrences)

if len(ping_occurrences) >= 2:
    second_idx = ping_occurrences[1]
    # Let's find where this second cmd_ping ends
    # It should end before the next decorator, which is @router.message(F.new_chat_members)
    end_idx = second_idx
    while end_idx < len(lines):
        if "@router.message" in lines[end_idx] and end_idx > second_idx:
            break
        end_idx += 1
    
    print(f"Deleting lines from {second_idx} to {end_idx}")
    new_lines = lines[:second_idx] + lines[end_idx:]
    
    with open(file_path, "w", encoding="utf-8") as f:
        f.writelines(new_lines)
    print("Success!")
else:
    print("Could not find second ping definition.")
