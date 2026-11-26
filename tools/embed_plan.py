"""Copia o plan.json para dentro do index.html (bloco <script id="plan-data">).

Uso, depois de rodar tools/build_plan.py:
  python tools/embed_plan.py
"""
import json, re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
plan = json.loads((ROOT / "plan.json").read_text(encoding="utf-8"))
data = json.dumps(plan, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
html = (ROOT / "index.html").read_text(encoding="utf-8")
new, n = re.subn(r'(<script type="application/json" id="plan-data">).*?(</script>)', lambda m: m.group(1) + data + m.group(2), html, count=1, flags=re.S)
assert n == 1, "bloco plan-data não encontrado"
(ROOT / "index.html").write_text(new, encoding="utf-8")
print("plano embutido:", sum(len(w["sessions"]) for w in plan["weeks"]), "sessões,", len(new), "bytes")
