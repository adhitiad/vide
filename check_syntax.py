import ast, sys

files = [
    "core/analytics_tracker.py",
    "core/comment_generator.py",
    "data/models.py",
    "environment/clipper_env.py",
    "scheduler_control.py",
    "core/editor.py",
]

all_ok = True
for f in files:
    try:
        with open(f, "r", encoding="utf-8") as fp:
            source = fp.read()
        ast.parse(source)
        print(f"✅ VALID : {f}")
    except SyntaxError as e:
        print(f"❌ ERROR : {f} → {e}")
        all_ok = False

print()
print("✅ Semua file sintaks valid!" if all_ok else "❌ Ada file yang gagal!")
sys.exit(0 if all_ok else 1)
