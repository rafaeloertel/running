"""Acesso mínimo ao Supabase pela API REST, só com a biblioteca padrão do Python.

Usado pelos robôs do GitHub Actions. Autentica com a chave SECRETA do projeto
(segredo SUPABASE_SECRET_KEY no GitHub), que ignora as regras de acesso; por isso
os robôs gravam sempre com o user_id do dono, descoberto por robot_user_id().
A chave secreta nunca vai para o site.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

URL = os.getenv("SUPABASE_URL", "https://daeokijmcstzxiaryaks.supabase.co").rstrip("/")
KEY = os.getenv("SUPABASE_SECRET_KEY", "").strip()


def enabled() -> bool:
    return bool(KEY)


def _req(method: str, path: str, body=None, prefer: str | None = None):
    headers = {"apikey": KEY, "Content-Type": "application/json", "Accept": "application/json"}
    if KEY.startswith("eyJ"):  # chave antiga (JWT service_role) também precisa do Authorization
        headers["Authorization"] = f"Bearer {KEY}"
    if prefer:
        headers["Prefer"] = prefer
    data = json.dumps(body, ensure_ascii=False, default=str).encode() if body is not None else None
    req = urllib.request.Request(f"{URL}{path}", data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            raw = r.read()
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Supabase {method} {path.split('?')[0]}: {e.code} {e.read().decode()[:300]}") from None


def user_id() -> str:
    uid = _req("POST", "/rest/v1/rpc/robot_user_id", {})
    if not uid:
        raise RuntimeError("Nenhum usuário autorizado ainda. Entre uma vez no site com a conta Microsoft e rode de novo.")
    return uid


def upsert(table: str, rows: list[dict], on_conflict: str) -> None:
    for i in range(0, len(rows), 500):
        _req("POST", f"/rest/v1/{table}?on_conflict={on_conflict}", rows[i:i + 500], "resolution=merge-duplicates,return=minimal")


def insert(table: str, rows: list[dict]) -> None:
    _req("POST", f"/rest/v1/{table}", rows, "return=minimal")


def select(table: str, query: str = "select=*") -> list[dict]:
    out, start = [], 0
    while True:
        page = _req("GET", f"/rest/v1/{table}?{query}&limit=1000&offset={start}")
        out += page or []
        if not page or len(page) < 1000:
            return out
        start += 1000


def log_run(uid: str, job: str, ok: bool, info: dict) -> None:
    try:
        insert("robot_runs", [{"user_id": uid, "job": job, "ok": ok, "info": info}])
    except Exception as e:  # noqa: BLE001  o registro da execução nunca derruba o robô
        print(f"  aviso: não registrei a execução ({e})")
