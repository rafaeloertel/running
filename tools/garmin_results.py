#!/usr/bin/env python3
"""Busca no Garmin Connect o que foi feito e grava para o site.

Grava no banco Supabase do app (tabelas activities, wellness_days, race_predictions):
  atividades (corridas, fortalecimento e outras) com distância, tempo, ritmo, FC média e
  máxima, tempo em cada zona, carga e efeito de treino; e sinais diários de recuperação:
  FC de repouso, VFC (HRV), sono, prontidão, VO2máx e previsões de prova do Garmin.
Sem a chave do Supabase (SUPABASE_SECRET_KEY), grava em arquivos (data/*.json), útil para testes.

Quem casa cada corrida com o treino planejado é o próprio app, para continuar certo
mesmo se o plano mudar. Atividades antigas ficam guardadas; as novas são acrescentadas.

Uso:
  python tools/garmin_results.py                 # últimos 10 dias
  python tools/garmin_results.py --days 30
  python tools/garmin_results.py --from 2026-11-16 --days 7
  python tools/garmin_results.py --dry-run       # busca e mostra, sem gravar
  python tools/garmin_results.py --sample DIR    # gera dados de exemplo em DIR (sem login)
  python tools/garmin_results.py --export ARQ    # cópia de segurança de todo o banco num .json

Autenticação: a mesma de tools/garmin_sync.py (secret GARMIN_TOKENS).
A cópia de segurança tem dados de saúde: mantenha o repositório PRIVADO.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import os
import random
import sys
import time
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
import supa  # noqa: E402
DATA = ROOT / "data"
TZ = ZoneInfo("America/Sao_Paulo")

RUN_TYPES = {
    "running", "treadmill_running", "trail_running", "track_running", "street_running",
    "indoor_running", "virtual_run", "ultra_run", "obstacle_run",
}
STRENGTH_TYPES = {"strength_training", "indoor_cardio", "hiit", "pilates", "yoga", "mobility"}


def kind_of(type_key: str) -> str:
    if type_key in RUN_TYPES or type_key.endswith("_running"):
        return "run"
    if type_key in {"strength_training", "hiit"}:
        return "strength"
    if type_key in STRENGTH_TYPES:
        return "mobility"
    if "cycling" in type_key or "biking" in type_key or type_key in {"virtual_ride", "spinning", "indoor_biking"}:
        return "bike"
    if "swimming" in type_key:
        return "swim"
    return "other"


def num(v, nd=1):
    try:
        if v is None:
            return None
        f = float(v)
        if math.isnan(f):
            return None
        return int(round(f)) if nd == 0 else round(f, nd)
    except (TypeError, ValueError):
        return None


def safe(fn, *a, **k):
    """Chamada tolerante: a API não oficial muda; um campo faltando não derruba a busca."""
    try:
        return fn(*a, **k)
    except Exception as e:  # noqa: BLE001
        print(f"  aviso: {getattr(fn, '__name__', fn)} falhou ({type(e).__name__}: {str(e)[:120]})")
        return None


def dig(d, *path, default=None):
    for p in path:
        if isinstance(d, dict):
            d = d.get(p)
        elif isinstance(d, list) and isinstance(p, int) and len(d) > p:
            d = d[p]
        else:
            return default
    return default if d is None else d


def login():
    from garminconnect import Garmin  # import tardio: --sample funciona sem a biblioteca

    tokens = os.getenv("GARMIN_TOKENS", "").strip()
    api = Garmin(os.getenv("GARMIN_EMAIL"), os.getenv("GARMIN_PASSWORD"))
    api.login(tokens or None)
    return api


# ---------------------------------------------------------------- atividades
def zones_from(api, a: dict) -> list[int] | None:
    z = [a.get(f"hrTimeInZone_{i}") for i in range(1, 6)]
    if any(v is not None for v in z):
        return [int(v or 0) for v in z]
    data = safe(api.get_activity_hr_in_timezones, str(a["activityId"]))
    if isinstance(data, list) and data:
        out = [0] * 5
        for row in data:
            n = int(row.get("zoneNumber") or 0)
            if 1 <= n <= 5:
                out[n - 1] = int(row.get("secsInZone") or 0)
        return out
    return None


def strength_from(api, a: dict) -> dict:
    out = {"sets": a.get("activeSets") or a.get("totalSets"), "reps": a.get("totalReps"), "exercises": []}
    data = safe(api.get_activity_exercise_sets, a["activityId"])
    sets = dig(data, "exerciseSets", default=[]) or []
    names: dict[str, int] = {}
    active = 0
    reps = 0
    for s in sets:
        if s.get("setType") != "ACTIVE":
            continue
        active += 1
        reps += int(s.get("repetitionCount") or 0)
        ex = (s.get("exercises") or [{}])[0]
        name = (ex.get("name") or ex.get("category") or "").replace("_", " ").lower()
        if name:
            names[name] = names.get(name, 0) + 1
    if active:
        out["sets"], out["reps"] = active, reps or out["reps"]
    out["exercises"] = [n for n, _ in sorted(names.items(), key=lambda x: -x[1])][:6]
    return out


def normalize(api, a: dict) -> dict:
    tkey = dig(a, "activityType", "typeKey", default="other")
    kind = kind_of(tkey)
    start = a.get("startTimeLocal") or a.get("startTimeGMT") or ""
    dist_km = num((a.get("distance") or 0) / 1000, 2)
    moving = a.get("movingDuration") or a.get("elapsedDuration") or a.get("duration")
    speed = a.get("averageSpeed")
    rec = {
        "id": str(a["activityId"]),
        "date": start[:10],
        "start": start[11:16],
        "kind": kind,
        "type": tkey,
        "name": a.get("activityName") or "",
        "duration_s": int(a.get("duration") or 0),
        "moving_s": int(moving or 0),
        "distance_km": dist_km if kind == "run" or (dist_km or 0) > 0.2 else None,
        "pace_s_km": int(1000 / speed) if kind == "run" and speed else None,
        "avg_hr": num(a.get("averageHR"), 0),
        "max_hr": num(a.get("maxHR"), 0),
        "elev_m": num(a.get("elevationGain"), 0),
        "cadence": num(a.get("averageRunningCadenceInStepsPerMinute"), 0),
        "calories": num(a.get("calories"), 0),
        "te_aerobic": num(a.get("aerobicTrainingEffect")),
        "te_anaerobic": num(a.get("anaerobicTrainingEffect")),
        "load": num(a.get("activityTrainingLoad"), 0),
        "vo2max": num(a.get("vO2MaxValue")),
        "zones_s": None,
    }
    if rec["avg_hr"]:
        rec["zones_s"] = zones_from(api, a)
    if kind == "strength":
        rec["strength"] = strength_from(api, a)
    return rec


def fetch_activities(api, start: dt.date, end: dt.date) -> list[dict]:
    raw = safe(api.get_activities_by_date, start.isoformat(), end.isoformat()) or []
    out = []
    for a in raw:
        try:
            out.append(normalize(api, a))
        except Exception as e:  # noqa: BLE001
            print(f"  aviso: atividade {a.get('activityId')} ignorada ({e})")
        time.sleep(0.3)
    return out


# ---------------------------------------------------------------- recuperação
def fetch_wellness(api, start: dt.date, end: dt.date) -> tuple[dict, dict]:
    days: dict[str, dict] = {}
    d = start
    while d <= end:
        iso = d.isoformat()
        row: dict = {}
        stats = safe(api.get_stats, iso) or {}
        row["rhr"] = num(stats.get("restingHeartRate"), 0)
        row["body_battery"] = num(stats.get("bodyBatteryHighestValue"), 0)
        row["stress"] = num(stats.get("averageStressLevel"), 0)
        row["steps"] = num(stats.get("totalSteps"), 0)
        hrv = safe(api.get_hrv_data, iso) or {}
        row["hrv"] = num(dig(hrv, "hrvSummary", "lastNightAvg"), 0)
        row["hrv_week"] = num(dig(hrv, "hrvSummary", "weeklyAvg"), 0)
        row["hrv_status"] = dig(hrv, "hrvSummary", "status")
        sleep = safe(api.get_sleep_data, iso) or {}
        row["sleep_s"] = num(dig(sleep, "dailySleepDTO", "sleepTimeSeconds"), 0)
        row["sleep_score"] = num(dig(sleep, "dailySleepDTO", "sleepScores", "overall", "value"), 0)
        tr = safe(api.get_training_readiness, iso)
        if isinstance(tr, list) and tr:
            row["readiness"] = num(tr[0].get("score"), 0)
            row["readiness_level"] = tr[0].get("level")
        mm = safe(api.get_max_metrics, iso)
        vo2 = dig(mm, 0, "generic", "vo2MaxPreciseValue") if isinstance(mm, list) else dig(mm, "generic", "vo2MaxPreciseValue")
        row["vo2max"] = num(vo2)
        clean = {k: v for k, v in row.items() if v not in (None, "")}
        if clean:
            days[iso] = clean
        d += dt.timedelta(days=1)
        time.sleep(0.3)
    pred = safe(api.get_race_predictions) or {}
    race = {}
    if isinstance(pred, dict) and pred:
        race = {
            "date": (pred.get("calendarDate") or end.isoformat())[:10],
            "t5k": pred.get("time5K"), "t10k": pred.get("time10K"),
            "t21k": pred.get("timeHalfMarathon"), "t42k": pred.get("timeMarathon"),
        }
    return days, race


# ---------------------------------------------------------------- gravação
def load_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return default


def merge_and_save(outdir: Path, acts: list[dict], days: dict, race: dict, dry: bool) -> None:
    res = load_json(outdir / "results.json", {"updated": None, "activities": []})
    well = load_json(outdir / "wellness.json", {"updated": None, "days": {}, "race_predictions": []})
    by_id = {a["id"]: a for a in res.get("activities", [])}
    new = sum(1 for a in acts if a["id"] not in by_id)
    for a in acts:
        by_id[a["id"]] = a
    res["activities"] = sorted(by_id.values(), key=lambda a: (a["date"], a.get("start") or ""))
    res["updated"] = dt.datetime.now(TZ).isoformat(timespec="minutes")
    well.setdefault("days", {}).update(days)
    well["days"] = dict(sorted(well["days"].items()))
    if race and race.get("t21k"):
        preds = [p for p in well.get("race_predictions", []) if p.get("date") != race["date"]]
        well["race_predictions"] = sorted(preds + [race], key=lambda p: p["date"])
    well["updated"] = res["updated"]
    runs = sum(1 for a in acts if a["kind"] == "run")
    stren = sum(1 for a in acts if a["kind"] == "strength")
    print(f"Atividades no período: {len(acts)} ({runs} corridas, {stren} de força), {new} novas. Dias de saúde: {len(days)}.")
    if dry:
        print(json.dumps(acts[:3], ensure_ascii=False, indent=1))
        return
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "results.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    (outdir / "wellness.json").write_text(json.dumps(well, ensure_ascii=False, indent=1), encoding="utf-8")


ACT_COLS = ["id", "date", "start", "kind", "type", "name", "duration_s", "moving_s", "distance_km", "pace_s_km", "avg_hr", "max_hr",
            "elev_m", "cadence", "calories", "te_aerobic", "te_anaerobic", "load", "vo2max", "zones_s", "strength"]


def save_supabase(acts: list[dict], days: dict, race: dict, dry: bool) -> None:
    uid = supa.user_id()
    rows = [{**{k: a.get(k) for k in ACT_COLS}, "user_id": uid, "src": "garmin"} for a in acts]
    wrows = [{"user_id": uid, "date": d, "data": v} for d, v in days.items()]
    prow = [{"user_id": uid, "date": race["date"], "t5k": race.get("t5k"), "t10k": race.get("t10k"), "t21k": race.get("t21k"), "t42k": race.get("t42k")}] if race and race.get("t21k") else []
    runs = sum(1 for a in acts if a["kind"] == "run")
    print(f"Atividades no período: {len(acts)} ({runs} corridas). Dias de saúde: {len(days)}. Previsão: {'sim' if prow else 'não'}.")
    if dry:
        print(json.dumps(rows[:2], ensure_ascii=False, indent=1)[:1500])
        return
    if rows:
        supa.upsert("activities", rows, "user_id,id")
    if wrows:
        supa.upsert("wellness_days", wrows, "user_id,date")
    if prow:
        supa.upsert("race_predictions", prow, "user_id,date")
    supa.log_run(uid, "results", True, {"atividades": len(rows), "corridas": runs, "dias": len(wrows)})
    print("Gravado no Supabase.")


def export_all(path: Path) -> None:
    """Cópia de segurança completa do banco (o plano gratuito do Supabase não guarda backups para baixar)."""
    uid = supa.user_id()
    out = {"exported_at": dt.datetime.now(TZ).isoformat(timespec="minutes"), "user_id": uid}
    for t in ["activities", "wellness_days", "race_predictions", "notes", "progress", "settings", "sent_workouts"]:
        out[t] = supa.select(t, f"select=*&user_id=eq.{uid}&order=" + ("date" if t in ("wellness_days", "race_predictions", "sent_workouts") else "updated_at" if t in ("notes", "progress", "settings") else "date,id"))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print(f"Cópia de segurança em {path}: " + ", ".join(f"{t} {len(out[t])}" for t in out if isinstance(out[t], list)))


# ---------------------------------------------------------------- exemplo
def sample(outdir: Path, until: dt.date) -> None:
    """Dados fictícios, só para ver o app funcionando antes de ligar o Garmin."""
    plan = json.loads((ROOT / "plan.json").read_text(encoding="utf-8"))
    rnd = random.Random(7)
    acts, days = [], {}
    sessions = [s for w in plan["weeks"] for s in w["sessions"] if s["date"] <= until.isoformat()]
    for i, s in enumerate(sessions):
        if rnd.random() < 0.1:
            continue  # treino perdido
        f = rnd.uniform(0.82, 1.08) if rnd.random() > 0.12 else rnd.uniform(0.5, 0.7)
        mov = int(s["est"] * f)
        km = round(s["km"] * f * rnd.uniform(0.97, 1.03), 2)
        hr = {"q": 156, "e": 132, "l": 145, "p": 170}[s["kind"]] + rnd.randint(-5, 5)
        z = {"q": [0.25, 0.25, 0.3, 0.15, 0.05], "e": [0.7, 0.28, 0.02, 0, 0], "l": [0.15, 0.7, 0.13, 0.02, 0], "p": [0, 0.05, 0.35, 0.5, 0.1]}[s["kind"]]
        acts.append({
            "id": f"9{i:07d}", "date": s["date"], "start": "06:3" + str(rnd.randint(0, 9)), "kind": "run", "type": "running",
            "name": f"Corrida, {s['title']}", "duration_s": mov + 60, "moving_s": mov, "distance_km": km,
            "pace_s_km": int(mov / km) if km else None, "avg_hr": hr, "max_hr": hr + rnd.randint(12, 22),
            "elev_m": rnd.randint(20, 90), "cadence": rnd.randint(164, 176), "calories": int(mov / 60 * 11),
            "te_aerobic": round(rnd.uniform(2.4, 4.2), 1), "te_anaerobic": round(rnd.uniform(0.2, 2.8), 1),
            "load": int(mov / 60 * {"q": 2.6, "e": 1.3, "l": 1.9, "p": 3.2}[s["kind"]]), "vo2max": None,
            "zones_s": [int(mov * p) for p in z],
        })
    d = dt.date.fromisoformat(plan["weeks"][0]["start"])
    k = 0
    while d <= until:
        if d.weekday() in (1, 3) and rnd.random() < 0.8:
            mov = rnd.randint(28, 42) * 60
            acts.append({"id": f"8{k:07d}", "date": d.isoformat(), "start": "19:0" + str(rnd.randint(0, 9)), "kind": "strength",
                         "type": "strength_training", "name": "Força", "duration_s": mov, "moving_s": mov, "distance_km": None,
                         "pace_s_km": None, "avg_hr": rnd.randint(98, 118), "max_hr": rnd.randint(135, 150), "elev_m": None, "cadence": None,
                         "calories": int(mov / 60 * 6), "te_aerobic": 1.2, "te_anaerobic": 1.6, "load": int(mov / 60 * 0.9),
                         "vo2max": None, "zones_s": [int(mov * .6), int(mov * .3), int(mov * .1), 0, 0],
                         "strength": {"sets": 12, "reps": 120, "exercises": ["agachamento", "afundo", "panturrilha", "prancha"]}})
            k += 1
        n = (d - dt.date.fromisoformat(plan["weeks"][0]["start"])).days
        days[d.isoformat()] = {"rhr": 52 + rnd.randint(-2, 3) - min(n // 30, 3), "hrv": 58 + rnd.randint(-8, 8), "hrv_week": 58,
                               "hrv_status": "BALANCED", "sleep_s": rnd.randint(6 * 3600, 8 * 3600), "sleep_score": rnd.randint(62, 90),
                               "readiness": rnd.randint(45, 88), "body_battery": rnd.randint(60, 95), "vo2max": round(49 + n / 60, 1)}
        d += dt.timedelta(days=1)
    preds = []
    d = dt.date.fromisoformat(plan["weeks"][0]["start"])
    t21 = 6720
    while d <= until:
        preds.append({"date": d.isoformat(), "t5k": int(t21 * .215), "t10k": int(t21 * .46), "t21k": t21, "t42k": int(t21 * 2.1)})
        t21 -= rnd.randint(5, 25)
        d += dt.timedelta(days=7)
    stamp = dt.datetime.now(TZ).isoformat(timespec="minutes")
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "results.json").write_text(json.dumps({"updated": stamp, "sample": True, "activities": sorted(acts, key=lambda a: (a["date"], a["start"]))}, ensure_ascii=False, indent=1), encoding="utf-8")
    (outdir / "wellness.json").write_text(json.dumps({"updated": stamp, "sample": True, "days": days, "race_predictions": preds}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Exemplo gravado em {outdir}: {len(acts)} atividades, {len(days)} dias.")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--days", type=int, default=10, help="quantos dias para trás (padrão 10)")
    ap.add_argument("--from", dest="start", help="data inicial AAAA-MM-DD (anda --days para frente)")
    ap.add_argument("--dry-run", action="store_true", help="busca e mostra, sem gravar")
    ap.add_argument("--sample", metavar="DIR", help="gera dados de exemplo em DIR, sem login")
    ap.add_argument("--until", help="com --sample: até que data gerar (padrão hoje)")
    ap.add_argument("--export", metavar="ARQ", help="só grava a cópia de segurança do banco em ARQ e sai")
    args = ap.parse_args()
    today = dt.datetime.now(TZ).date()
    if args.sample:
        sample(Path(args.sample), dt.date.fromisoformat(args.until) if args.until else today)
        return 0
    if args.export:
        export_all(Path(args.export))
        return 0
    if args.start:
        start = dt.date.fromisoformat(args.start)
        end = min(start + dt.timedelta(days=args.days - 1), today)
    else:
        end, start = today, today - dt.timedelta(days=args.days - 1)
    print(f"Buscando de {start} a {end}…")
    api = login()
    acts = fetch_activities(api, start, end)
    days, race = fetch_wellness(api, start, end)
    if supa.enabled():
        save_supabase(acts, days, race, args.dry_run)
    else:
        merge_and_save(DATA, acts, days, race, args.dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
