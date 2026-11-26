"""Gera plan.json: fonte única do plano (app + sincronizador Garmin)."""
import json, datetime as dt
from pathlib import Path

START = dt.date(2026, 11, 23)  # reinício em 23/11; a 1ª semana segue a última planilha EZK (16–22/11)
DOW = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]

def S(n, k, v, z, i="active", d=None):
    s = {"t": "s", "n": n, "k": k, "v": v, "z": z, "i": i}
    if d: s["d"] = d
    return s
def R(x, steps): return {"t": "r", "x": x, "s": steps}
def WU(m): return S(f"Aquecer {m}'", "time", m*60, 1, "warmup", "trote leve, devagar")
def CD(m): return S(f"Desaquecer {m}'", "time", m*60, 1, "cooldown", "trote leve, devagar")
def STRIDES(): return [R(6, [S("Aceleração 80 m", "dist", 80, None, "active", "acelerações curtas, soltas"), S("Descanso 30\"", "time", 30, None, "rest")])]
def km(x): return int(round(x*1000))
def mm(sec):
    m, s = divmod(int(sec), 60)
    return f"{m}'" if not s else f"{m}'{s:02d}\""

# ---------- construtores (mesma lógica da biblioteca do documento) ----------
def F1(n): return dict(code="F1", title=f"Fartlek {n}×1'", kind="q", steps=[WU(15), R(n, [S("1' moderado", "time", 60, 3, "active", "ritmo moderado, constante"), S("1' trote", "time", 60, 1, "recovery")]), CD(15)])
def F2():
    blk = lambda: R(4, [S("1'30\" ritmo", "time", 90, 4, "active", "2ª série ~5\"/km mais rápida"), S("1' trote", "time", 60, 1, "recovery")])
    return dict(code="F2", title="Fartlek 2×(4×1'30\")", kind="q", steps=[WU(15), blk(), S("Descanso 1'30\"", "time", 90, None, "rest", "parado ou andando"), blk(), CD(15)])
def F3(): return dict(code="F3", title="Fartlek 3×(3' + 2×1')", kind="q", steps=[WU(12), R(3, [S("3' moderado", "time", 180, 4), S("1' trote", "time", 60, 1, "recovery"), S("1' forte", "time", 60, 4), S("1' trote", "time", 60, 1, "recovery"), S("1' forte", "time", 60, 4), S("1' trote", "time", 60, 1, "recovery"), S("Descanso 1'30\"", "time", 90, None, "rest")]), CD(12)])
def F4(r, m): return dict(code="F4", title=f"Limiar {r}×{m}'", kind="q", steps=[WU(15), R(r, [S(f"{m}' limiar", "time", m*60, 4, "active", "ritmo de 10 km, controlado"), S("2' trote", "time", 120, 1, "recovery")]), CD(10)])
def F5(r, m): return dict(code="F5", title=f"Ritmo de meia {r}×{m}'", kind="q", steps=[WU(15), R(r, [S(f"{m}' ritmo meia", "time", m*60, 3, "active", "ritmo de prova dos 21 km"), S("3' trote", "time", 180, 1, "recovery")]), CD(10)])
def F6(m):
    c = m - 30
    return dict(code="F6", title=f"Progressivo {m}'", kind="q", steps=[WU(10), S("15' leve", "time", 900, 2), S("15' moderado", "time", 900, 3), S(f"{c}' forte", "time", c*60, 4, "active", "limiar baixo"), CD(5)])
def I1(n): return dict(code="I1", title=f"Intervalado {n}×400 m", kind="q", steps=[WU(12)] + STRIDES() + [R(n, [S("400 m forte", "dist", 400, 5, "active", "corrida a ritmo"), S("Descanso 1'15\"", "time", 75, None, "rest")]), CD(12)])
def I2(sets, reps):
    st = [WU(10)] + STRIDES()
    for i in range(sets):
        st.append(R(reps, [S("1' subida", "time", 60, 5, "active", "subida 5–6%, 80% de esforço"), S("Descer devagar", "time", 105, 1, "recovery", "volta ao ponto de partida")]))
        st.append(S("Descanso 1'30\"", "time", 90, None, "rest"))
    st += [R(2, [S("400 m plano", "dist", 400, 5, "active", "levar a força da subida para o plano"), S("Descanso 1'30\"", "time", 90, None, "rest")]), CD(10)]
    return dict(code="I2", title=f"Subidas {sets}×{reps}×1'", kind="q", steps=st)
def I3(): return dict(code="I3", title="Pirâmide 800-600-400", kind="q", steps=[WU(12)] + STRIDES() + [R(2, [S("800 m", "dist", 800, 4), S("200 m trote", "dist", 200, 1, "recovery")]), R(2, [S("600 m", "dist", 600, 5), S("200 m trote", "dist", 200, 1, "recovery")]), R(3, [S("400 m", "dist", 400, 5), S("Descanso 1'15\"", "time", 75, None, "rest")]), CD(12)])
def I4(n): return dict(code="I4", title=f"Limiar {n}×1.600 m", kind="q", steps=[WU(12)] + STRIDES() + [R(n, [S("1.600 m limiar", "dist", 1600, 4), S("Descanso 1'30\"", "time", 90, None, "rest")]), CD(12)])
def I5(n): return dict(code="I5", title=f"VO2 {n}×1.000 m", kind="q", steps=[WU(12)] + STRIDES() + [R(n, [S("1.000 m forte", "dist", 1000, 5, "active", "ritmo de 5 km"), S("2' trote", "time", 120, 1, "recovery")]), CD(12)])
def I6(n, k):
    kk = f"{k:g}".replace(".", ",")
    return dict(code="I6", title=f"Ritmo de meia {n}×{kk} km", kind="q", steps=[WU(12), R(n, [S(f"{kk} km ritmo meia", "dist", km(k), 3, "active", "ritmo de prova dos 21 km"), S("2' trote", "time", 120, 1, "recovery")]), CD(10)])
def I7(n, m, leve=False): return dict(code="I7", title=f"Afiação {n}×{m} m" + (" (leve)" if leve else ""), kind="q", steps=[WU(12)] + STRIDES() + [R(n, [S(f"{m} m ritmo 5 km", "dist", m, 5), S("Descanso 1'30\"", "time", 90, None, "rest")]), CD(12)])
def T3(): return dict(code="T3", title="Teste de 3 km", kind="q", steps=[WU(12)] + STRIDES() + [S("3 km teste", "dist", 3000, 5, "active", "forte e constante; anote o tempo"), CD(10)])
def RG(m, strides=False):
    st = [S(f"Regenerativo {m}'", "time", m*60, 1, "active", "ritmo devagar, fácil")]
    if strides: st += STRIDES()
    return dict(code="R", title=f"Regenerativo {m}'" + (" + 6×80 m" if strides else ""), kind="e", steps=st)
def L(m, note="Z2"): return dict(code="L", title=f"Longão {m}'" + (f" {note}" if note else ""), kind="l", steps=[S(f"Longão {m}'", "time", m*60, 2, "active", note if note != "Z2" else "ritmo fácil de corrida longa")])
def LK(k, note=""): return dict(code="L", title=f"Longão {k} km" + (f" {note}" if note else ""), kind="l", steps=[S(f"Longão {k} km", "dist", km(k), 2, "active", note or "ritmo fácil de corrida longa")])
def LP(k):
    a, b = k//2, k//3
    c = k - a - b
    return dict(code="L", title=f"{k} km progressivo", kind="l", steps=[S(f"{a} km leve", "dist", km(a), 2), S(f"{b} km moderado", "dist", km(b), 3), S(f"{c} km forte", "dist", km(c), 4)])
def LT(k, tail, z):
    lab = "RM" if z == 3 else f"Z{z}"
    return dict(code="L", title=f"{k} km, últimos {tail} km {lab}", kind="l", steps=[S(f"{k-tail} km leve", "dist", km(k-tail), 2), S(f"{tail} km {lab}", "dist", km(tail), z, "active", "ritmo de meia" if z == 3 else None)])
def LB(k, reps, blk):
    pre = k - reps*blk - 2
    return dict(code="L", title=f"{k} km com {reps}×{blk} km RM", kind="l", steps=[S(f"{pre} km leve", "dist", km(pre), 2), R(reps, [S(f"{blk} km ritmo meia", "dist", km(blk), 3), S("Descanso 2'", "time", 120, None, "rest", "andando, hidratando")]), S("2 km trote", "dist", 2000, 1, "cooldown")])
def LRM(k, rm):
    pre = (k - rm) / 2
    p = f"{pre:g}".replace(".", ",")
    return dict(code="L", title=f"{k} km com {rm} km RM", kind="l", steps=[S(f"{p} km leve", "dist", km(pre), 2), S(f"{rm} km ritmo meia", "dist", km(rm), 3, "active", "ritmo de prova"), S(f"{p} km trote", "dist", km(pre), 1, "cooldown")])
def RACE(k, name): return dict(code="PROVA", title=f"{name}", kind="p", steps=[S(f"Prova {k:g} km".replace(".", ","), "dist", km(k), None, "active", "boa prova!")])

# ---------- bicicleta ergométrica (cardio sem impacto) ----------
def BWU(m): return S(f"Aquecer {m}'", "time", m*60, 1, "warmup", "giro leve, carga baixa")
def BCD(m): return S(f"Soltar {m}'", "time", m*60, 1, "cooldown", "giro leve, carga baixa")
def BK1():
    blk = lambda: R(4, [S("1'30\" forte", "time", 90, 4, "active", "carga alta, cadência 85–95"), S("1' leve", "time", 60, 1, "recovery")])
    return dict(code="B1", title="Bike: blocos 2×(4×1'30\")", kind="x", steps=[BWU(15), blk(), S("1'30\" leve", "time", 90, 1, "recovery"), blk(), BCD(10)])
def BK2():
    pyr = lambda: R(1, [S("4' forte", "time", 240, 4), S("2' leve", "time", 120, 1, "recovery"), S("3' forte", "time", 180, 4), S("2' leve", "time", 120, 1, "recovery"),
                        S("2' muito forte", "time", 120, 5), S("2' leve", "time", 120, 1, "recovery"), S("1' muito forte", "time", 60, 5), S("2' leve", "time", 120, 1, "recovery")])
    return dict(code="B2", title="Bike: pirâmide 4-3-2-1' (2×)", kind="x", steps=[BWU(12), R(2, pyr()["s"]), BCD(8)])

# ---------- força (academia) ----------
# chave: (nome, papel, categoria Garmin, exercício Garmin, dica)
# papel: L = perna principal, U = tronco principal, a = acessório, c = core (fixo), p = pliometria (fixo)
# categoria/exercício vêm do catálogo do Garmin Connect (garminconnect.exercises); o robô confere antes de enviar.
EX = {
    "agacha":   ("Agachamento livre", "L", "SQUAT", "BARBELL_BACK_SQUAT", "desça até a coxa paralela, tronco firme"),
    "terra":    ("Levantamento terra romeno", "L", "DEADLIFT", "ROMANIAN_DEADLIFT", "quadril para trás, barra rente às pernas"),
    "supino":   ("Supino com halteres", "U", "BENCH_PRESS", "DUMBBELL_BENCH_PRESS", ""),
    "remada":   ("Remada curvada com barra", "U", "ROW", "BENT_OVER_ROW_WITH_BARBELL", "costas retas, puxe até o umbigo"),
    "bulg":     ("Búlgaro com halteres", "a", "LUNGE", "DUMBBELL_BULGARIAN_SPLIT_SQUAT", "por perna; pé de trás no banco"),
    "pant":     ("Panturrilha em pé", "a", "CALF_RAISE", "STANDING_CALF_RAISE", "sobe rápido, desce em 3 s"),
    "hip":      ("Elevação de quadril (hip thrust)", "L", "HIP_RAISE", "BARBELL_HIP_THRUST_WITH_BENCH", "pausa de 1 s em cima"),
    "stepup":   ("Step-up no banco", "a", "SQUAT", "DUMBBELL_STEP_UP", "por perna; suba pela perna da frente, sem impulso da de trás"),
    "puxada":   ("Puxada frontal", "U", "PULL_UP", "LAT_PULLDOWN", "ou barra fixa"),
    "desenv":   ("Desenvolvimento com halteres", "U", "SHOULDER_PRESS", "DUMBBELL_SHOULDER_PRESS", ""),
    "flexora":  ("Cadeira flexora", "a", "LEG_CURL", "LEG_CURL", "desça devagar, em 3 s"),
    "pantsent": ("Panturrilha sentado", "a", "CALF_RAISE", "SEATED_CALF_RAISE", ""),
    "legpress": ("Leg press", "a", "SQUAT", "LEG_PRESS", "pés inteiros na plataforma"),
    "hiper":    ("Hiperextensão lombar", "a", "HYPEREXTENSION", "HYPEREXTENSION", ""),
    "incl":     ("Supino inclinado com halteres", "a", "BENCH_PRESS", "INCLINE_DUMBBELL_BENCH_PRESS", ""),
    "cabo":     ("Remada sentada no cabo", "a", "ROW", "SEATED_CABLE_ROW", ""),
    "elev":     ("Elevação lateral", "a", "LATERAL_RAISE", "DUMBBELL_LATERAL_RAISE", ""),
    "rosca":    ("Rosca direta", "a", "CURL", "BARBELL_BICEPS_CURL", ""),
    "triceps":  ("Tríceps na polia", "a", "TRICEPS_EXTENSION", "TRICEPS_PRESSDOWN", ""),
    "face":     ("Face pull", "a", "ROW", "FACE_PULL", "cotovelos altos"),
    "prancha":  ("Prancha", "c", "PLANK", "PLANK", "quadril alinhado"),
    "lateral":  ("Prancha lateral", "c", "PLANK", "SIDE_PLANK", "cada lado"),
    "pallof":   ("Pallof no cabo (antirrotação)", "c", "CORE", "CABLE_CORE_PRESS", "cada lado"),
    "deadbug":  ("Dead bug", "c", "HIP_STABILITY", "DEAD_BUG", "lombar colada no chão"),
    "ponte":    ("Ponte de glúteo", "c", "HIP_RAISE", "HIP_RAISE", ""),
    "quadr":    ("Perdigueiro (quatro apoios)", "c", "HIP_STABILITY", "QUADRUPED_WITH_LEG_LIFT", "braço e perna opostos"),
    "m9090":    ("Mobilidade 90/90 de quadril", "c", "WARM_UP", "STRETCH_90_90", "cada lado"),
    "torac":    ("Rotação torácica", "c", "WARM_UP", "THORACIC_ROTATION", "cada lado"),
    "box":      ("Salto na caixa", "p", "PLYO", "BOX_JUMP", "explosivo, aterrisse macio e desça andando"),
    "skater":   ("Salto lateral (skater)", "p", "PLYO", "LATERAL_LEAP_AND_HOP", "cada lado; estabilize 1 s na aterrissagem"),
}
# séries × repetições × descanso (s) por modo e papel
DOSE = {
    "adapt":  {"L": (3, 10, 90),  "U": (3, 10, 90),  "a": (3, 12, 60)},
    "forca":  {"L": (4, 6, 150),  "U": (4, 8, 120),  "a": (3, 8, 90)},
    "manut":  {"L": (3, 5, 150),  "U": (3, 8, 90),   "a": (2, 8, 75)},
    "transi": {"L": (3, 8, 120),  "U": (3, 10, 90),  "a": (3, 10, 60)},
    "alivio": {"L": (2, 10, 90),  "U": (2, 10, 90),  "a": (2, 12, 60)},
}
# core e pliometria têm dose fixa: (séries, reps ou None, segundos ou None, descanso)
FIX = {"prancha": (3, None, 40, 45), "lateral": (2, None, 30, 30), "pallof": (2, 10, None, 45), "deadbug": (2, 10, None, 45),
       "ponte": (3, 12, None, 45), "quadr": (2, 10, None, 30), "m9090": (2, None, 45, 15), "torac": (2, 8, None, 15),
       "box": (3, 5, None, 90), "skater": (3, 6, None, 60), "pant": (3, 12, None, 60), "pantsent": (3, 15, None, 45)}
SEM_PONTA = {"bulg": "legpress", "pant": "flexora", "stepup": "legpress", "pantsent": "hiper"}  # dedão machucado

def X(key, mode):
    n, role, cat, g, d = EX[key]
    if key in FIX:
        sets, reps, sec, rest = FIX[key]
        if mode == "alivio": sets = min(sets, 2)
    else:
        sets, reps, rest = DOSE[mode][role]; sec = None
    e = {"n": n, "cat": cat, "g": g, "sets": sets, "rest": rest}
    if reps: e["reps"] = reps
    if sec: e["sec"] = sec
    if d: e["d"] = d
    return e

FT = {  # modelos de treino
    "A": ("Força A: perna pesada e tronco", ["agacha", "terra", "supino", "remada", "bulg", "pant", "prancha"]),
    "B": ("Força B: posterior, tronco e core", ["hip", "stepup", "puxada", "desenv", "flexora", "pantsent", "lateral", "pallof", "deadbug"]),
    "C": ("Força C: tronco e braços (opcional)", ["incl", "cabo", "elev", "rosca", "triceps", "face"]),
    "M": ("Tronco e mobilidade", ["m9090", "torac", "ponte", "quadr", "cabo", "prancha", "lateral", "deadbug"]),
}
def STR(t, mode, toe=False, leve=False):
    title, keys = FT[t]
    if mode == "velo":
        keys = (["box"] if t == "A" else ["skater"] if t == "B" else []) + keys
        mode = "manut"
    if toe:
        keys = [SEM_PONTA.get(k, k) for k in keys]
        keys = [k for i, k in enumerate(keys) if k not in keys[:i]]   # sem repetir exercício
        title += " (sem ponta do pé)"
    if leve:
        mode, title = "alivio", "Força B leve" if t == "B" else title + " (leve)"
    ex = [X(k, "adapt" if t in "CM" and mode not in ("alivio",) else mode) for k in keys]
    wu = 300 if t == "M" else 480
    return dict(code="F" + t, title=title, kind="f", opt=(t == "C"), wu=wu, ex=ex)

def str_est(x):
    t = x["wu"]
    for e in x["ex"]:
        work = e.get("sec") or e.get("reps", 10) * 4
        if "cada lado" in e.get("d", "") or "por perna" in e.get("d", ""): work *= 2
        t += e["sets"] * work + (e["sets"] - 1) * e["rest"] + 60   # 1 min de troca entre exercícios
    return t

MODE = {"Base 1": "adapt", "Festas": "adapt", "Base 2 – força": "forca", "Limiar / 10 km": "manut", "Específico 1": "manut",
        "Específico 2": "manut", "Velocidade / VO2": "velo", "Transição 5–10 km": "transi", "Base 2028": "adapt",
        "Carnaval – alívio": "alivio", "Páscoa – alívio": "alivio"}
TER, QUI = 1, 3
def strength_week(n, phase, sess):
    """Sessões de força da semana: terça e quinta (A e B), domingo C opcional. Respeita provas, polimento e recuperação."""
    days = {d for d, _ in sess}
    race = next((x for d, x in sess if x["kind"] == "p"), None)
    big = race and race["steps"][0]["v"] > 15000            # meia: semana de prova A/B
    out = []
    if phase == "Recuperação":
        out = [(TER, STR("M", "adapt")), (QUI, STR("M", "adapt"))]
    elif phase.startswith("Polimento"):
        out = [(TER, STR("M", "adapt"))] if big else [(TER, STR("B", "adapt", leve=True))]
    elif race:                                               # 10 km de controle no domingo
        out = [(TER, STR("B", "manut"))]
    elif n == 1:                                             # início na quarta: só a B (perna leve) antes de sexta e sábado
        out = [(QUI, STR("B", MODE[phase], toe=True))]
    else:
        m = MODE[phase]
        out = [(TER, STR("A", m)), (QUI, STR("B", m))]
    if not race and DOM not in days:
        out.append((DOM, STR("C", "adapt")))
    return out

# ---------- 51 semanas: (fase, volume, [(dia, sessão), ...]) ----------
def wk(phase, vol, seg, qua, sex, wkend):
    s = []
    if seg: s.append((0, seg))
    if qua: s.append((2, qua))
    if sex: s.append((4, sex))
    for d, x in wkend: s.append((d, x))
    return (phase, vol, s)
SAB, DOM = 5, 6
W = [
 wk("Base 1", 105, None, BK1(), RG(45), [(SAB, L(60))]),   # início na quarta 25/11; dedão machucado
 wk("Base 1", 260, F1(12), I1(10), RG(45), [(SAB, L(85, "leves subidas"))]),
 wk("Base 1", 200, F1(8), I1(6), RG(35), [(SAB, L(65))]),
 wk("Base 1", 265, F2(), I3(), RG(45), [(SAB, L(90))]),
 wk("Festas", 180, F1(8), I1(6), RG(35), [(SAB, L(60, "livre"))]),
 wk("Festas", 200, F1(10), I1(8), RG(40), [(SAB, L(70))]),
 wk("Base 2 – força", 250, F3(), I2(2, 4), RG(40), [(SAB, L(80, "com subidas"))]),
 wk("Base 2 – força", 270, F3(), I2(2, 5), RG(45), [(SAB, L(85, "com subidas"))]),
 wk("Base 2 – força", 285, F6(45), I2(3, 4), RG(45), [(SAB, L(90, "muitas subidas"))]),
 wk("Base 2 – força", 220, F1(10), I1(8), RG(40), [(SAB, L(70))]),
 wk("Base 2 – força", 290, F6(50), I2(3, 4), RG(45), [(SAB, L(95, "com subidas"))]),
 wk("Carnaval – alívio", 200, None, F1(10), RG(40), [(SAB, L(60))]),
 wk("Limiar / 10 km", 280, F4(3, 8), I3(), RG(45), [(SAB, LK(14))]),
 wk("Limiar / 10 km", 295, F4(3, 10), I4(4), RG(45), [(SAB, LT(15, 3, 3))]),
 wk("Limiar / 10 km", 310, F4(2, 15), I5(5), RG(45), [(SAB, LK(16))]),
 wk("Limiar / 10 km", 240, F1(10), I1(8), RG(40), [(SAB, LK(12))]),
 wk("Limiar / 10 km", 250, F1(8), I7(4, 600, True), RG(30), [(DOM, RACE(10, "10 km de controle"))]),
 wk("Páscoa – alívio", 210, RG(40), F1(10), RG(40), [(SAB, L(60))]),
 wk("Específico 1", 290, F5(2, 12), I4(4), RG(45), [(SAB, LB(16, 3, 2))]),
 wk("Específico 1", 310, F5(2, 15), I6(3, 3), RG(45), [(SAB, LK(17))]),
 wk("Específico 1", 325, F4(3, 10), I5(5), RG(45), [(SAB, LP(18))]),
 wk("Específico 1", 250, F1(10), I1(8), RG(40), [(SAB, LK(13))]),
 wk("Específico 1", 335, F5(2, 15), I6(3, 3), RG(45), [(SAB, LB(18, 2, 4))]),
 wk("Específico 1", 345, F4(3, 10), I4(5), RG(45), [(SAB, LK(19, "(pico)"))]),
 wk("Específico 1", 300, F5(2, 12), I6(2, 3), RG(40), [(SAB, LRM(16, 10))]),
 wk("Polimento B", 240, F1(10), I6(3, 2), RG(40), [(SAB, LRM(13, 4))]),
 wk("Polimento B", 160, F1(6), I7(4, 400), RG(20, True), [(SAB, RACE(21.1, "Meia da Maratona do Rio"))]),
 wk("Recuperação", 150, None, RG(30), RG(35), [(SAB, RG(45))]),
 wk("Recuperação", 200, F1(8), RG(40), RG(40), [(SAB, L(70))]),
 wk("Velocidade / VO2", 270, F3(), I5(5), RG(45), [(SAB, LK(15))]),
 wk("Velocidade / VO2", 290, F4(3, 10), I7(6, 600), RG(45), [(SAB, LK(16, "com subidas"))]),
 wk("Velocidade / VO2", 305, F4(2, 15), I5(6), RG(45), [(SAB, LK(17))]),
 wk("Velocidade / VO2", 240, F1(10), I1(8), RG(40), [(SAB, LK(13))]),
 wk("Específico 2", 310, F5(2, 15), I7(4, 600, True), RG(30), [(DOM, RACE(10, "10 km de controle"))]),
 wk("Específico 2", 345, F4(3, 10), I6(3, 3), RG(45), [(SAB, LT(20, 5, 3))]),
 wk("Específico 2", 330, F5(2, 15), I4(5), RG(45), [(SAB, LB(16, 2, 5))]),
 wk("Polimento A", 260, F1(10), I6(3, 2), RG(40), [(SAB, LRM(14, 6))]),
 wk("Polimento A", 170, F1(6), I7(4, 400), RG(30), [(SAB, RG(20, True)), (DOM, RACE(21.1, "Meia Maratona Internacional do Rio"))]),
 wk("Recuperação", 140, None, RG(30), RG(35), [(SAB, RG(45))]),
 wk("Recuperação", 200, F1(8), RG(40), RG(40), [(SAB, L(70))]),
 wk("Transição 5–10 km", 240, F2(), I7(6, 600), RG(40), [(SAB, L(75))]),
 wk("Transição 5–10 km", 260, F3(), I3(), RG(45), [(SAB, L(80, "com subidas"))]),
 wk("Transição 5–10 km", 270, F4(3, 8), I5(5), RG(45), [(SAB, L(85))]),
 wk("Transição 5–10 km", 210, F1(10), I1(8), RG(40), []),
 wk("Transição 5–10 km", 260, F2(), I7(6, 600), RG(45), [(SAB, L(80))]),
 wk("Transição 5–10 km", 270, F4(3, 8), I3(), RG(45), [(SAB, L(85, "com subidas"))]),
 wk("Base 2028", 250, F1(10), I2(2, 4), RG(40), [(SAB, L(80))]),
 wk("Base 2028", 260, F3(), I2(2, 5), RG(45), [(SAB, L(85, "com subidas"))]),
 wk("Base 2028", 270, F6(45), I1(10), RG(45), [(SAB, L(90))]),
 wk("Base 2028", 210, F1(8), I1(6), RG(35), [(SAB, L(65))]),
 wk("Base 2028", 230, F1(10), T3(), RG(40), [(SAB, L(75, "balanço do ano"))]),
]
assert len(W) == 51
NOTES = {1: "Início na quarta 25/11 (segunda e terça ficaram de fora). Por causa do dedão: quarta na bicicleta ergométrica, com os mesmos blocos de esforço do fartlek e sem impacto; quinta Força B sem nada apoiado na ponta do pé (sem afundo e sem panturrilha). A corrida volta na sexta com o regenerativo, que serve de teste; longão encurtado para 60'. Domingo: Força C opcional (só tronco e braços) ou natação leve. A Força A entra na semana 2.",
         12: "Carnaval: segunda livre.", 17: "Domingo 21/03: 10 km de controle.", 27: "Sábado 29/05: Meia da Maratona do Rio.",
         34: "Domingo 18/07: 10 km de controle.", 38: "Domingo 15/08: Meia Maratona Internacional do Rio. Sábado só trote.",
         44: "Sábado livre — opção: Maratona de Niterói (6 ou 10 km)."}

PACE = {1: 6.6, 2: 6.1, 3: 5.4, 4: 5.1, 5: 4.8, None: 5.3}  # min/km só para estimar duração
def est(steps):
    t = 0
    for s in steps:
        if s["t"] == "r": t += s["x"] * est(s["s"])
        elif s["k"] == "time": t += s["v"]
        else: t += s["v"]/1000 * PACE[s["z"]] * 60
    return t
def dist(steps):
    d = 0
    for s in steps:
        if s["t"] == "r": d += s["x"] * dist(s["s"])
        elif s["k"] == "dist": d += s["v"]
        else: d += s["v"] / (PACE[s["z"]] * 60) * 1000
    return d

weeks = []
for i, (phase, vol, sess) in enumerate(W):
    mon = START + dt.timedelta(weeks=i)
    out = []
    for d, x in sorted(sess + strength_week(i + 1, phase, sess), key=lambda p: p[0]):
        date = mon + dt.timedelta(days=d)
        sid = f"S{i+1:02d}-{DOW[d].replace('á','a')}"
        if x["kind"] == "f":
            out.append(dict(id=sid, date=date.isoformat(), dow=DOW[d], code=x["code"], title=x["title"], kind="f",
                            est=int(round(str_est(x) / 60) * 60), km=0, opt=x["opt"], steps=[], wu=x["wu"], ex=x["ex"]))
            continue
        out.append(dict(id=sid, date=date.isoformat(), dow=DOW[d], code=x["code"], title=x["title"], kind=x["kind"],
                        est=int(round(est(x["steps"]))), km=0 if x["kind"] == "x" else round(dist(x["steps"])/1000, 1), steps=x["steps"]))
    weeks.append(dict(n=i+1, start=mon.isoformat(), end=(mon+dt.timedelta(days=6)).isoformat(), phase=phase, vol=vol,
                      note=NOTES.get(i+1, ""), sessions=out))

plan = dict(
    version=1, athlete="Rafael Oertel", title="Plano Anual de Corrida 2026–2027",
    goal="Baixar o tempo na meia maratona", start=START.isoformat(),
    races=[
        dict(date="2027-03-21", name="10 km de controle", km=10, prio="C"),
        dict(date="2027-05-29", name="Meia da Maratona do Rio", km=21.1, prio="B"),
        dict(date="2027-07-18", name="10 km de controle", km=10, prio="C"),
        dict(date="2027-08-15", name="Meia Maratona Internacional do Rio", km=21.1, prio="A"),
    ],
    zones=[
        dict(z=1, name="Regenerativo", lo=0.60, hi=0.70, rpe="2–3"),
        dict(z=2, name="Leve / longão", lo=0.70, hi=0.78, rpe="3–4"),
        dict(z=3, name="Moderado / ritmo de meia", lo=0.78, hi=0.85, rpe="5–6"),
        dict(z=4, name="Limiar / ritmo de 10 km", lo=0.85, hi=0.90, rpe="7–8"),
        dict(z=5, name="Ritmo de 5 km / VO2", lo=0.90, hi=0.95, rpe="8–9"),
    ],
    weeks=weeks,
)
json.dump(plan, open(Path(__file__).resolve().parent.parent / "plan.json", "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
n = sum(len(w["sessions"]) for w in weeks)
print("sessions", n, "bytes", len(json.dumps(plan, ensure_ascii=False, separators=(",", ":"))))
# as provas precisam cair no dia certo
for r in plan["races"]:
    assert any(x["date"] == r["date"] and x["kind"] == "p" for w in weeks for x in w["sessions"]), r
ids = [s["id"] for w in weeks for s in w["sessions"]]
assert len(ids) == len(set(ids)), "id repetido"
print("força", sum(1 for w in weeks for s in w["sessions"] if s["kind"] == "f"), "| corrida/bike", sum(1 for w in weeks for s in w["sessions"] if s["kind"] != "f"))
for w in weeks[:2] + weeks[26:27] + weeks[37:38]:
    print(w["n"], w["phase"], [(s["id"], s["title"], s["est"]//60, s["km"]) for s in w["sessions"]])
