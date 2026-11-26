#!/usr/bin/env python3
"""Envia os treinos do plan.json para o Garmin Connect e agenda no calendário.

Usa a biblioteca não oficial python-garminconnect (login com a sua própria conta).
Os treinos agendados sincronizam com o relógio na próxima sincronização do app Garmin Connect.

Uso:
  python tools/garmin_sync.py --dry-run          # mostra o que faria, sem login
  python tools/garmin_sync.py                    # próximos 14 dias a partir de hoje
  python tools/garmin_sync.py --days 21
  python tools/garmin_sync.py --from 2026-11-16 --days 7
  python tools/garmin_sync.py --week 3           # uma semana inteira do plano

Autenticação (nesta ordem):
  1. GARMIN_TOKENS  = JSON gerado por tools/garmin_login.py (recomendado; funciona com MFA)
  2. GARMIN_EMAIL + GARMIN_PASSWORD (só contas sem verificação em duas etapas)
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import time
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
PLAN = ROOT / "plan.json"
STATE = ROOT / "garmin_state.json"
TZ = ZoneInfo("America/Sao_Paulo")
TAG = "plano-anual"  # marcador na descrição dos treinos criados por este script

STEP_TYPE = {
    "warmup": (1, "warmup", 1),
    "cooldown": (2, "cooldown", 2),
    "active": (3, "interval", 3),
    "recovery": (4, "recovery", 4),
    "rest": (5, "rest", 5),
}
COND = {
    "time": {"conditionTypeId": 2, "conditionTypeKey": "time", "displayOrder": 2, "displayable": True},
    "dist": {"conditionTypeId": 3, "conditionTypeKey": "distance", "displayOrder": 3, "displayable": True},
    "open": {"conditionTypeId": 1, "conditionTypeKey": "lap.button", "displayOrder": 1, "displayable": True},
}
NO_TARGET = {"workoutTargetTypeId": 1, "workoutTargetTypeKey": "no.target", "displayOrder": 1}
HR_ZONE = {"workoutTargetTypeId": 4, "workoutTargetTypeKey": "heart.rate.zone", "displayOrder": 1}
RUNNING = {"sportTypeId": 1, "sportTypeKey": "running", "displayOrder": 1}
CYCLING = {"sportTypeId": 2, "sportTypeKey": "cycling", "displayOrder": 2}


def sig(session: dict) -> str:
    """Assinatura do treino: se o título ou a data mudarem no plano, o envio antigo fica desatualizado."""
    return f"{session['title']}|{session['date']}"


def to_garmin_steps(steps: list[dict], counter: list[int], hr_targets: bool = True) -> list[dict]:
    out = []
    for s in steps:
        counter[0] += 1
        order = counter[0]
        if s["t"] == "r":
            out.append({
                "type": "RepeatGroupDTO",
                "stepOrder": order,
                "stepType": {"stepTypeId": 6, "stepTypeKey": "repeat", "displayOrder": 6},
                "numberOfIterations": s["x"],
                "endCondition": {"conditionTypeId": 7, "conditionTypeKey": "iterations", "displayOrder": 7, "displayable": False},
                "endConditionValue": float(s["x"]),
                "smartRepeat": False,
                "workoutSteps": to_garmin_steps(s["s"], counter, hr_targets),
            })
            continue
        sid, skey, sord = STEP_TYPE.get(s.get("i", "active"), STEP_TYPE["active"])
        step = {
            "type": "ExecutableStepDTO",
            "stepOrder": order,
            "stepType": {"stepTypeId": sid, "stepTypeKey": skey, "displayOrder": sord},
            "endCondition": COND[s["k"]],
            "targetType": HR_ZONE if s.get("z") and hr_targets else NO_TARGET,
            "description": (s["n"] + (f" — {s['d']}" if s.get("d") else ""))[:250],
        }
        if s["k"] != "open":
            step["endConditionValue"] = float(s["v"])
        if s.get("z") and hr_targets:
            step["zoneNumber"] = int(s["z"])
        out.append(step)
    return out


STRENGTH = {"sportTypeId": 5, "sportTypeKey": "strength_training", "displayOrder": 5}
REPS = {"conditionTypeId": 10, "conditionTypeKey": "reps", "displayOrder": 10, "displayable": True}
ITER = {"conditionTypeId": 7, "conditionTypeKey": "iterations", "displayOrder": 7, "displayable": False}


def _catalog() -> set[tuple[str, str]]:
    """Pares (categoria, exercício) que o Garmin aceita, do catálogo da biblioteca; vazio se não der para ler."""
    try:
        from garminconnect.exercises import EXERCISES
        return {(e["category"], e["exercise"]) for e in EXERCISES}
    except Exception:  # noqa: BLE001
        return set()


def build_strength(session: dict) -> dict:
    """Treino de força no formato do Garmin Connect (o mesmo de garminconnect.workout.create_strength_set)."""
    known = _catalog()
    order = [0]

    def nxt() -> int:
        order[0] += 1
        return order[0]

    steps = []
    if session.get("wu"):
        steps.append({"type": "ExecutableStepDTO", "stepOrder": nxt(),
                      "stepType": {"stepTypeId": 1, "stepTypeKey": "warmup", "displayOrder": 1},
                      "endCondition": COND["time"], "endConditionValue": float(session["wu"]), "targetType": NO_TARGET,
                      "description": "Aquecimento: bike leve e mobilidade"})
    for e in session.get("ex", []):
        g = e.get("g", "")
        if known and (e["cat"], g) not in known:
            g = ""                                   # nome desconhecido: o relógio mostra só a categoria
        group = nxt()
        ex_step = {"type": "ExecutableStepDTO", "stepOrder": nxt(),
                   "stepType": {"stepTypeId": 3, "stepTypeKey": "interval", "displayOrder": 3},
                   "endCondition": REPS if e.get("reps") else COND["time"],
                   "endConditionValue": float(e.get("reps") or e.get("sec") or 30),
                   "targetType": NO_TARGET, "category": e["cat"], "exerciseName": g,
                   "description": (e["n"] + (f" — {e['d']}" if e.get("d") else ""))[:250]}
        rest = {"type": "ExecutableStepDTO", "stepOrder": nxt(),
                "stepType": {"stepTypeId": 5, "stepTypeKey": "rest", "displayOrder": 5},
                "endCondition": COND["time"], "endConditionValue": float(e.get("rest", 60)), "targetType": NO_TARGET}
        steps.append({"type": "RepeatGroupDTO", "stepOrder": group,
                      "stepType": {"stepTypeId": 6, "stepTypeKey": "repeat", "displayOrder": 6},
                      "numberOfIterations": int(e["sets"]), "workoutSteps": [ex_step, rest],
                      "endCondition": ITER, "endConditionValue": float(e["sets"]), "smartRepeat": False})
    return {
        "workoutName": f"{session['id']} {session['title']}"[:80],
        "description": f"{TAG}:{session['id']} · {session['title']} · {session['date']}",
        "sportType": STRENGTH,
        "author": {},
        "estimatedDurationInSecs": int(session.get("est", 0)),
        "workoutSegments": [{"segmentOrder": 1, "sportType": STRENGTH, "workoutSteps": steps}],
    }


def build_workout(session: dict) -> dict:
    if session.get("kind") == "f":                 # força: exercícios com séries, repetições e descanso
        return build_strength(session)
    name = f"{session['id']} {session['title']}"[:80]
    bike = session.get("kind") == "x"          # bicicleta ergométrica: treino de ciclismo, sem alvo de FC (zonas de corrida não servem)
    sport = CYCLING if bike else RUNNING
    return {
        "workoutName": name,
        "description": f"{TAG}:{session['id']} · {session['title']} · {session['date']}",
        "sportType": sport,
        "estimatedDurationInSecs": int(session.get("est", 0)),
        "workoutSegments": [{
            "segmentOrder": 1,
            "sportType": sport,
            "workoutSteps": to_garmin_steps(session["steps"], [0], hr_targets=not bike),
        }],
    }


sys.path.insert(0, str(Path(__file__).resolve().parent))
import supa  # noqa: E402

UID = None


def load_state() -> dict:
    """O que já foi enviado: no Supabase (tabela sent_workouts); sem a chave, no arquivo local."""
    global UID
    if supa.enabled():
        UID = supa.user_id()
        rows = supa.select("sent_workouts", f"select=session_id,workout_id,date,sig&user_id=eq.{UID}")
        return {r["session_id"]: {"workoutId": r["workout_id"], "date": r["date"], "sig": r.get("sig")} for r in rows}
    if STATE.exists():
        return json.loads(STATE.read_text(encoding="utf-8"))
    return {}


def save_state(state: dict, sid: str | None = None) -> None:
    if supa.enabled() and sid:
        st = state[sid]
        supa.upsert("sent_workouts", [{"user_id": UID, "session_id": sid, "workout_id": str(st.get("workoutId") or ""), "date": st["date"], "sig": st.get("sig")}], "user_id,session_id")
        return
    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")


def select_sessions(plan: dict, args) -> list[dict]:
    all_s = [s for w in plan["weeks"] for s in w["sessions"]]
    if args.week:
        return [s for w in plan["weeks"] if w["n"] == args.week for s in w["sessions"]]
    start = dt.date.fromisoformat(args.from_date) if args.from_date else dt.datetime.now(TZ).date()
    end = start + dt.timedelta(days=args.days - 1)
    return [s for s in all_s if start <= dt.date.fromisoformat(s["date"]) <= end]


def missing_on_calendar(api, sessions: list[dict], state: dict) -> set[str]:
    """Sessões que constam como enviadas mas não estão no calendário do Garmin na data certa.

    Se não der para ler o calendário, não aponta nada (melhor não duplicar do que adivinhar)."""
    months = sorted({(int(s["date"][:4]), int(s["date"][5:7])) for s in sessions})
    items = []
    try:
        for y, m in months:
            items += (api.get_scheduled_workouts(y, m) or {}).get("calendarItems") or []
    except Exception as e:  # noqa: BLE001
        print(f"(aviso) não consegui ler o calendário do Garmin: {e}")
        return set()
    wk = [it for it in items if it.get("itemType") == "workout"]
    by_id = {(it.get("date"), str(it.get("workoutId") or "")) for it in wk}
    by_title = {(it.get("date"), (it.get("title") or "").split(" ")[0]) for it in wk}
    out = set()
    for s in sessions:
        st = state.get(s["id"])
        if not st or (st.get("sig") and st["sig"] != sig(s)):
            continue                                  # ainda não enviado ou já marcado para trocar
        if (s["date"], str(st.get("workoutId") or "")) in by_id or (s["date"], s["id"]) in by_title:
            continue
        out.add(s["id"])
    return out


def login():
    from garminconnect import Garmin  # import tardio: --dry-run funciona sem a biblioteca

    tokens = os.getenv("GARMIN_TOKENS", "").strip()
    email, pwd = os.getenv("GARMIN_EMAIL"), os.getenv("GARMIN_PASSWORD")
    api = Garmin(email, pwd)
    api.login(tokens or None)
    return api


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--days", type=int, default=14)
    ap.add_argument("--from", dest="from_date")
    ap.add_argument("--week", type=int)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force", action="store_true", help="reenvia mesmo o que já consta como enviado")
    args = ap.parse_args()

    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    sessions = select_sessions(plan, args)
    state = load_state()
    # desatualizado = já enviado, mas o treino mudou no plano (título ou data): apaga o antigo no Garmin e envia de novo
    stale = {s["id"] for s in sessions if s["id"] in state and state[s["id"]].get("sig") and state[s["id"]]["sig"] != sig(s)}
    todo = [s for s in sessions if args.force or s["id"] not in state or s["id"] in stale]

    api = None
    missing: set[str] = set()
    if not args.dry_run:
        api = login()
        # confere no calendário do Garmin: o que consta como enviado mas sumiu é reposto
        missing = missing_on_calendar(api, sessions, state)
        todo += [s for s in sessions if s["id"] in missing and s not in todo]

    print(f"{len(sessions)} sessões no período; {len(todo)} para enviar.")
    for s in sessions:
        mark = "↻" if s["id"] in stale else "⟲" if s["id"] in missing else "→" if s in todo else "✓"
        print(f"  {mark} {s['date']} {s['id']:8} {s['title']}")
    if missing:
        print(f"  (⟲ = constava como enviado mas não está no calendário do Garmin: {len(missing)})")
    if args.dry_run or not todo:
        if args.dry_run and todo:
            print("\n--dry-run: exemplo do JSON do primeiro treino:")
            print(json.dumps(build_workout(todo[0]), ensure_ascii=False, indent=1)[:2000])
        if supa.enabled() and not args.dry_run:
            supa.log_run(UID, "sync", True, {"enviados": 0, "previstos": 0, "conferidos": len(sessions)})
        return 0

    # evita duplicar: reaproveita treinos já existentes com a mesma tag
    existing = {}
    try:
        for w in api.get_workouts(0, 400):
            desc = (w.get("description") or "")
            if desc.startswith(f"{TAG}:"):
                existing[desc.split()[0].split(":", 1)[1]] = (w.get("workoutId"), desc)
    except Exception as e:  # lista é só otimização
        print(f"(aviso) não consegui listar treinos existentes: {e}")

    ok = 0
    for s in todo:
        try:
            if s["id"] in stale:
                old = state[s["id"]].get("workoutId")
                if old:
                    try:
                        api.delete_workout(old)          # apagar o treino também tira o agendamento do calendário
                        print(f"  − apagado no Garmin: {s['id']} (versão antiga)")
                    except Exception as e:
                        print(f"  (aviso) não consegui apagar o treino antigo {old}: {e}")
                existing.pop(s["id"], None)
            if s["id"] in missing:
                old = state[s["id"]].get("workoutId")
                try:                                     # o treino ainda existe na biblioteca? só reagenda
                    if not old:
                        raise ValueError("sem id")
                    api.get_workout_by_id(old)
                    api.schedule_workout(old, s["date"])
                    ok += 1
                    print(f"  ⟲ {s['date']} {s['title']} reagendado (workoutId {old})")
                    time.sleep(1.0)
                    continue
                except Exception:  # noqa: BLE001
                    existing.pop(s["id"], None)          # não existe mais: envia de novo
            wid, desc = existing.get(s["id"], (None, None))
            if desc != build_workout(s)["description"]:
                wid = None                               # só reaproveita se for exatamente o mesmo treino
            if not wid or args.force:
                res = api.upload_workout(build_workout(s))
                wid = res.get("workoutId")
            sched = api.schedule_workout(wid, s["date"])
            state[s["id"]] = {
                "workoutId": wid,
                "scheduleId": (sched or {}).get("workoutScheduleId"),
                "date": s["date"],
                "sig": sig(s),
                "sentAt": dt.datetime.now(TZ).isoformat(timespec="seconds"),
            }
            save_state(state, s["id"])
            ok += 1
            print(f"  ✓ {s['date']} {s['title']} (workoutId {wid})")
            time.sleep(1.0)
        except Exception as e:
            print(f"  ✗ {s['date']} {s['title']}: {e}", file=sys.stderr)
    print(f"\nEnviados {ok}/{len(todo)}. Sincronize o relógio no app Garmin Connect.")
    if supa.enabled():
        supa.log_run(UID, "sync", ok == len(todo), {"enviados": ok, "previstos": len(todo), "repostos": len(missing)})
    return 0 if ok == len(todo) else 1


if __name__ == "__main__":
    raise SystemExit(main())
