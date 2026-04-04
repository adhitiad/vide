import json
import glob
import os

data_dir = "modulTrain"
json_files = glob.glob(os.path.join(data_dir, "*.json"))

print(f"Checking {len(json_files)} files in {data_dir}...")

for f_path in json_files:
    try:
        with open(f_path, "r", encoding="utf-8") as infile:
            json.load(infile)
    except json.JSONDecodeError as e:
        print(f"❌ Corrupted file: {f_path}")
        print(f"Error: {e}")
        # Print surroundings of the error
        with open(f_path, "r", encoding="utf-8") as infile:
            content = infile.read()
            # Extract line with context
            lines = content.splitlines()
            if e.lineno <= len(lines):
                print(f"--- File Sample around line {e.lineno} ---")
                start_line = max(0, e.lineno - 3)
                end_line = min(len(lines), e.lineno + 3)
                for i in range(start_line, end_line):
                    marker = ">> " if i + 1 == e.lineno else "   "
                    print(f"{marker}{i+1}: {lines[i]}")
                print("------------------------------------------")
