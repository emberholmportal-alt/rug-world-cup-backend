import random
import time
import bisect

CHAINS = [
    ('Bitcoin', 'BTC', '#f7931a'),
    ('Ethereum', 'ETH', '#7b88c4'),
    ('Solana', 'SOL', '#14c08a'),
    ('BNB Chain', 'BNB', '#f3ba2f'),
    ('XRP', 'XRP', '#7d848c'),
    ('Cardano', 'ADA', '#3468d1'),
    ('Avalanche', 'AVAX', '#e84142'),
    ('Polygon', 'POL', '#8247e5'),
    ('Tron', 'TRX', '#e0060a'),
    ('Polkadot', 'DOT', '#e6007a'),
    ('Hyperliquid', 'HYPE', '#0f9d86'),
    ('Sui', 'SUI', '#4da2ff'),
    ('Aptos', 'APT', '#5a5a5a'),
    ('Near', 'NEAR', '#2bbf6e'),
    ('Base', 'BASE', '#0052ff'),
    ('Arbitrum', 'ARB', '#28a0f0'),
    ('Optimism', 'OP', '#ff0420'),
    ('Monad', 'MON', '#836ef9'),
    ('MegaETH', 'MEGA', '#8a6df0'),
    ('Berachain', 'BERA', '#d98a3b'),
    ('Abstract', 'ABS', '#1fa94c'),
    ('Sei', 'SEI', '#d6392c'),
    ('Celestia', 'TIA', '#7b2bf9'),
    ('TON', 'TON', '#0098ea'),
    ('Litecoin', 'LTC', '#8a8a8a'),
    ('Dogecoin', 'DOGE', '#c2a633'),
    ('Shibarium', 'SHIB', '#f06a23'),
    ('Blast', 'BLAST', '#b3ad00'),
    ('Scroll', 'SCRL', '#c79a5a'),
    ('zkSync', 'ZK', '#7d848c'),
    ('Linea', 'LINEA', '#5a60d6'),
    ('Mantle', 'MNT', '#2f8f6c'),
    ('Sonic', 'S', '#ff8a3d'),
    ('Injective', 'INJ', '#2891f9'),
    ('Cosmos', 'ATOM', '#6b5bd6'),
    ('Kaspa', 'KAS', '#1fa98c'),
    ('Starknet', 'STRK', '#ec7a3b'),
    ('Cronos', 'CRO', '#1f4dd6'),
    ('Algorand', 'ALGO', '#6a6a6a'),
    ('Stacks', 'STX', '#6b4bff'),
    ('Hedera', 'HBAR', '#6a6a6a'),
    ('Ronin', 'RON', '#1b75ff'),
    ('Flow', 'FLOW', '#1fbf6e'),
    ('Immutable', 'IMX', '#3a8fb0'),
    ('Pulsechain', 'PLS', '#e64db0'),
    ('Tezos', 'XTZ', '#2c7df7'),
    ('Gnosis', 'GNO', '#3ba578'),
    ('Eclipse', 'ECL', '#6b5bd6'),
]

ROUND_NAMES = {32: "16avos de final", 16: "Octavos de final", 8: "Cuartos de final",
               4: "Semifinal", 2: "Final"}
GROUP_LETTERS = "ABCDEFGHIJKL"   # 12 grupos

MATCH_LEN = 90   # minutos de juego (ficticios) por partido
GROUP_PEN_PROB = 0.12  # en grupos casi todos los empates quedan empate; raramente se van a penales

# calendario round-robin de 4 equipos (indices locales 0-3), 3 fechas
RR_ROUNDS = [[(0, 3), (1, 2)], [(0, 2), (3, 1)], [(0, 1), (2, 3)]]

# ===================== TORNEO AUTOCONCLUSIVO (72 HS) =========================
# El reloj lo maneja el TIEMPO REAL, no las compras. 104 partidos repartidos en
# 72hs con ritmo variable (grupos cortos, finales largas y dramaticas).
TOURNAMENT_SECONDS = 72 * 3600          # 259200

# peso de duracion REAL por ronda. TUNEABLE: subir un peso = esa ronda dura mas.
ROUND_WEIGHT = {"grupos": 1.0, 32: 1.05, 16: 1.13, 8: 1.2, 4: 1.28, "3er": 1.23, 2: 1.54}


def _slot_rounds():
    """Las 104 ranuras del torneo, en orden, con su ronda (sirve para la duracion)."""
    r = ["grupos"] * 72   # fase de grupos: 72 partidos
    r += [32] * 16        # 16avos
    r += [16] * 8         # octavos
    r += [8] * 4          # cuartos
    r += [4] * 2          # semifinales
    r += ["3er"] * 1      # tercer puesto
    r += [2] * 1          # final
    return r              # total = 104


SLOT_ROUNDS = _slot_rounds()
_W = [ROUND_WEIGHT[r] for r in SLOT_ROUNDS]
_TOT = sum(_W)
SLOT_DUR = [w / _TOT * TOURNAMENT_SECONDS for w in _W]   # duracion real de cada ranura (seg)
SLOT_CUM = []
_acc = 0.0
for _d in SLOT_DUR:
    _acc += _d
    SLOT_CUM.append(_acc)   # SLOT_CUM[-1] == TOURNAMENT_SECONDS


def _goals_one_side():
    """Goles de un equipo en un partido: marcador realista (promedio ~1.3)."""
    r = random.random()
    if r < 0.30:
        return 0
    if r < 0.62:
        return 1
    if r < 0.83:
        return 2
    if r < 0.94:
        return 3
    if r < 0.985:
        return 4
    return 5


class Match:
    def __init__(self, a, b, group=None, stage="grupos", round_size=0):
        self.a = a
        self.b = b
        self.group = group
        self.stage = stage
        self.round_size = round_size
        # marcador final pre-sorteado al iniciar el partido
        self.final_a = 0
        self.final_b = 0
        # timeline de goles: lista de (minuto, "a"/"b") ordenada
        self.goals = []
        self.pen_winner = None     # "a"/"b" si se define por penales
        self.pen = False           # True si este partido se resuelve por penales
        # estado revelado en vivo
        self.ga = 0
        self.gb = 0
        self.minuto = 0
        self.shown = 0             # cuantos goles del timeline ya se revelaron


class Tournament:
    def __init__(self):
        self.energy = 0.0
        self.mcap_sol = 0.0
        self.price_sol = 0.0
        self.start_ts = None       # timestamp real de arranque (None = no arrancado)
        self.started = False
        self.cur_slot = 0          # ranura (partido global 0..103) que se esta jugando
        self.version = 0
        self.reset()

    # ---------- armado ----------
    def reset(self):
        order = list(range(len(CHAINS)))
        random.shuffle(order)
        self.groups = [order[i * 4:(i + 1) * 4] for i in range(12)]
        self.stats = {t: {"pj": 0, "g": 0, "e": 0, "p": 0, "gf": 0, "gc": 0, "pts": 0}
                      for t in range(len(CHAINS))}
        self.schedule = self._build_schedule()
        self.gm_pos = 0
        self.phase = "grupos"
        self.results = []
        self.champion = None
        self.third = None
        self.ko_teams = []
        self.round_size = 0
        self.pos = 0
        self.winners = []
        self.sf_losers = []
        self.is_third = False
        self._final_teams = None
        self.cur_slot = 0
        self.start_ts = None
        self.started = False
        self.energy = 0.0
        self.version += 1
        self._start_group_match()

    def _build_schedule(self):
        s = []
        for rnd in RR_ROUNDS:
            for gi, g in enumerate(self.groups):
                for (i, j) in rnd:
                    s.append((gi, g[i], g[j]))
        return s   # 3 fechas * 12 grupos * 2 = 72

    def _roll_match(self, m):
        """Pre-sortea el resultado del partido al momento de iniciarlo."""
        ga = _goals_one_side()
        gb = _goals_one_side()
        m.final_a = ga
        m.final_b = gb
        goals = [(random.randint(1, 89), "a") for _ in range(ga)]
        goals += [(random.randint(1, 89), "b") for _ in range(gb)]
        goals.sort(key=lambda x: x[0])
        m.goals = goals
        m.pen_winner = None
        m.pen = False
        if ga == gb:
            # en KO siempre se define por penales; en grupos casi siempre queda empate
            m.pen = True if m.stage != "grupos" else (random.random() < GROUP_PEN_PROB)
            if m.pen:
                m.pen_winner = "a" if random.random() < 0.5 else "b"
        m.ga = 0
        m.gb = 0
        m.minuto = 0
        m.shown = 0

    def _start_group_match(self):
        gi, a, b = self.schedule[self.gm_pos]
        self.match = Match(a, b, group=gi, stage="grupos", round_size=0)
        self._roll_match(self.match)

    def _start_ko_match(self):
        a = self.ko_teams[self.pos * 2]
        b = self.ko_teams[self.pos * 2 + 1]
        rs = 3 if self.is_third else self.round_size
        self.match = Match(a, b, group=None,
                           stage=("3er" if self.is_third else "ko"), round_size=rs)
        self._roll_match(self.match)

    def matches_in_round(self):
        if self.phase == "grupos":
            return len(self.schedule)
        if self.is_third:
            return 1
        return len(self.ko_teams) // 2

    # ---------- arranque manual ----------
    def start(self, seconds_ago=0.0):
        if self.start_ts is not None:
            return False
        self.start_ts = time.time() - max(0.0, float(seconds_ago))
        self.started = True
        self.version += 1
        return True

    # ---------- reloj por tiempo ----------
    def _slot_for_elapsed(self, elapsed):
        i = bisect.bisect_right(SLOT_CUM, elapsed)
        return min(i, 103)

    def _reveal_goals(self, minuto):
        m = self.match
        while m.shown < len(m.goals) and m.goals[m.shown][0] <= minuto:
            side = m.goals[m.shown][1]
            if side == "a":
                m.ga += 1
            else:
                m.gb += 1
            m.shown += 1
            self.energy = min(100.0, self.energy + 45.0)

    def tick(self):
        # sin arrancar, o terminado: solo se calma la energia
        if not self.started or self.start_ts is None or self.champion is not None:
            self.energy *= 0.92
            return
        now = time.time()
        elapsed = now - self.start_ts
        if elapsed < 0:
            elapsed = 0.0
        over = elapsed >= TOURNAMENT_SECONDS
        e = min(elapsed, TOURNAMENT_SECONDS - 0.001)
        # al cumplirse las 72hs se fuerza la resolucion de TODO (incluida la final)
        target = 104 if over else self._slot_for_elapsed(e)
        guard = 0
        while self.cur_slot < target and self.champion is None and guard < 140:
            self._end_match()
            guard += 1
        if self.champion is not None:
            self.energy *= 0.92
            return
        slot_start = SLOT_CUM[self.cur_slot] - SLOT_DUR[self.cur_slot]
        dur = SLOT_DUR[self.cur_slot]
        frac = 0.0 if dur <= 0 else max(0.0, min(1.0, (e - slot_start) / dur))
        self.match.minuto = int(round(frac * MATCH_LEN))
        self._reveal_goals(self.match.minuto)
        self.energy *= 0.92

    # ---------- standings ----------
    def _record_group(self, m):
        a, b = m.a, m.b
        sa, sb = m.final_a, m.final_b
        A, B = self.stats[a], self.stats[b]
        A["pj"] += 1
        B["pj"] += 1
        if sa > sb:
            A["g"] += 1
            B["p"] += 1
            A["pts"] += 3
        elif sb > sa:
            B["g"] += 1
            A["p"] += 1
            B["pts"] += 3
        elif m.pen:
            # empate definido por penales (raro en grupos): el ganador mete el gol decisivo
            if m.pen_winner == "a":
                sa += 1
                A["g"] += 1
                B["p"] += 1
                A["pts"] += 3
            else:
                sb += 1
                B["g"] += 1
                A["p"] += 1
                B["pts"] += 3
        else:
            # empate real: 1 punto para cada uno
            A["e"] += 1
            B["e"] += 1
            A["pts"] += 1
            B["pts"] += 1
        A["gf"] += sa
        A["gc"] += sb
        B["gf"] += sb
        B["gc"] += sa

    def _rank_key(self, t):
        s = self.stats[t]
        return (s["pts"], s["gf"] - s["gc"], s["gf"])

    def _group_table(self, gi):
        return sorted(self.groups[gi], key=self._rank_key, reverse=True)

    def _qualify(self):
        winners, runners, thirds = [], [], []
        for gi in range(12):
            tbl = self._group_table(gi)
            winners.append(tbl[0])
            runners.append(tbl[1])
            thirds.append(tbl[2])
        best_thirds = sorted(thirds, key=self._rank_key, reverse=True)[:8]
        return winners, runners, best_thirds

    # ---------- transiciones ----------
    def _start_knockout(self):
        w, r, th = self._qualify()
        qualified = w + r + th     # 12 + 12 + 8 = 32
        random.shuffle(qualified)  # sorteo del cuadro
        self.ko_teams = qualified
        self.phase = "ko"
        self.round_size = 32
        self.pos = 0
        self.winners = []
        self.sf_losers = []
        self.is_third = False
        self._start_ko_match()

    def _end_match(self):
        m = self.match
        # revelar marcador final completo
        m.ga = m.final_a
        m.gb = m.final_b
        m.shown = len(m.goals)
        self.version += 1
        self.cur_slot += 1
        pen = m.pen

        if self.phase == "grupos":
            self._record_group(m)
            self.results.append({"fase": "grupos", "grupo": GROUP_LETTERS[m.group],
                                 "a": CHAINS[m.a][1], "b": CHAINS[m.b][1],
                                 "ga": m.ga, "gb": m.gb, "pen": pen})
            self.gm_pos += 1
            if self.gm_pos >= len(self.schedule):
                self._start_knockout()
            else:
                self._start_group_match()
            return

        # --- eliminatoria: siempre hay ganador (penales si empate) ---
        if not pen:
            win, lose = (m.a, m.b) if m.final_a > m.final_b else (m.b, m.a)
        else:
            win, lose = (m.a, m.b) if m.pen_winner == "a" else (m.b, m.a)
        size = 3 if self.is_third else self.round_size
        ronda = "Tercer puesto" if self.is_third else ROUND_NAMES.get(self.round_size, "")
        self.results.append({"fase": "ko", "ronda": ronda, "size": size,
                             "a": CHAINS[m.a][1], "b": CHAINS[m.b][1],
                             "ga": m.ga, "gb": m.gb, "win": CHAINS[win][1], "pen": pen})

        if self.is_third:
            self.third = win
            self.is_third = False
            self.ko_teams = self._final_teams
            self.round_size = 2
            self.pos = 0
            self.winners = []
            self._start_ko_match()
            return

        self.winners.append(win)
        if self.round_size == 4:
            self.sf_losers.append(lose)
        self.pos += 1
        if self.pos * 2 >= len(self.ko_teams):
            if self.round_size == 2:
                self.champion = self.winners[0]
            elif self.round_size == 4:
                # semis terminadas: primero 3er puesto, despues final
                self._final_teams = self.winners[:]
                self.ko_teams = self.sf_losers[:]
                self.is_third = True
                self.pos = 0
                self.winners = []
                self._start_ko_match()
            else:
                self.ko_teams = self.winners[:]
                self.round_size = self.round_size // 2
                self.pos = 0
                self.winners = []
                self._start_ko_match()
        else:
            self._start_ko_match()

    # ---------- mercado (para cuando se reactive PumpPortal; inerte por ahora) -----
    def set_market(self, mcap_sol, price_sol):
        if mcap_sol is not None:
            try:
                self.mcap_sol = float(mcap_sol)
            except (TypeError, ValueError):
                pass
        if price_sol is not None:
            try:
                self.price_sol = float(price_sol)
            except (TypeError, ValueError):
                pass

    # ---------- snapshots ----------
    def snapshot(self):
        m = self.match
        a, b = CHAINS[m.a], CHAINS[m.b]
        if self.start_ts is not None:
            elapsed = time.time() - self.start_ts
        else:
            elapsed = 0.0
        remaining = max(0, int(TOURNAMENT_SECONDS - elapsed)) if self.started else TOURNAMENT_SECONDS

        if not self.started:
            fase = "pre"
            ronda = "Pre-partido"
            fecha = None
            grupo = None
            partido = 0
            total = len(self.schedule)
        elif self.phase == "grupos":
            fase = "grupos"
            ronda = "Fase de grupos"
            fecha = self.gm_pos // 24 + 1
            grupo = GROUP_LETTERS[m.group]
            partido = self.gm_pos + 1
            total = len(self.schedule)
        else:
            fase = "ko"
            ronda = "Tercer puesto" if self.is_third else ROUND_NAMES.get(self.round_size, "")
            fecha = None
            grupo = None
            partido = self.pos + 1
            total = self.matches_in_round()

        penales = bool(self.started and self.champion is None
                       and m.pen and m.minuto >= 86)

        return {
            "type": "state", "fase": fase, "ronda": ronda, "fecha": fecha,
            "grupo": grupo, "partido": partido, "partidos_ronda": total,
            "minuto": m.minuto, "energia": round(self.energy),
            "started": self.started, "remaining": remaining, "penales": penales,
            "activo": True, "buys": 0, "sol_max": 0, "bver": self.version,
            "volumen": 0, "mcap_sol": round(self.mcap_sol, 4), "price_sol": self.price_sol,
            "local": {"short": a[1], "name": a[0], "color": a[2], "goles": m.ga, "atk": 0},
            "visita": {"short": b[1], "name": b[0], "color": b[2], "goles": m.gb, "atk": 0},
            "campeon": (CHAINS[self.champion][1] if self.champion is not None else None),
            "tercero": (CHAINS[self.third][1] if self.third is not None else None),
        }

    def groups_state(self):
        grupos = []
        for gi in range(12):
            filas = []
            for pos, t in enumerate(self._group_table(gi)):
                s = self.stats[t]
                filas.append({"short": CHAINS[t][1], "name": CHAINS[t][0], "color": CHAINS[t][2],
                              "pj": s["pj"], "g": s["g"], "e": s["e"], "p": s["p"],
                              "gf": s["gf"], "gc": s["gc"], "dg": s["gf"] - s["gc"],
                              "pts": s["pts"], "pos": pos + 1})
            grupos.append({"grupo": GROUP_LETTERS[gi], "tabla": filas})
        return {"type": "groups", "fase": self.phase, "grupos": grupos}

    def bracket_state(self):
        rounds = []
        if self.phase == "ko" or self.champion is not None:
            by = {}
            for r in self.results:
                if r.get("fase") == "ko" and r.get("size") != 3:
                    by.setdefault(r["size"], []).append(r)
            for size in (32, 16, 8, 4, 2):
                done = by.get(size, [])
                is_current = (self.phase == "ko" and not self.is_third
                              and self.round_size == size and self.champion is None)
                if not done and not is_current:
                    continue
                matches = []
                for r in done:
                    matches.append({"a": r["a"], "b": r["b"], "ga": r["ga"], "gb": r["gb"],
                                    "win": r["win"], "st": "done"})
                if is_current:
                    for i in range(self.pos, self.matches_in_round()):
                        ca = CHAINS[self.ko_teams[i * 2]][1]
                        cb = CHAINS[self.ko_teams[i * 2 + 1]][1]
                        if i == self.pos:
                            mm = self.match
                            matches.append({"a": ca, "b": cb, "ga": mm.ga, "gb": mm.gb,
                                            "win": None, "st": "live"})
                        else:
                            matches.append({"a": ca, "b": cb, "ga": 0, "gb": 0,
                                            "win": None, "st": "next"})
                rounds.append({"size": size, "name": ROUND_NAMES.get(size, ""), "matches": matches})
        return {"type": "bracket", "rounds": rounds,
                "campeon": (CHAINS[self.champion][1] if self.champion is not None else None),
                "tercero": (CHAINS[self.third][1] if self.third is not None else None)}

    # ---------- persistencia (serializacion para Postgres) ----------
    def to_dict(self):
        m = self.match
        return {
            "schema": 2,
            "groups": self.groups,
            "stats": {str(k): v for k, v in self.stats.items()},
            "gm_pos": self.gm_pos,
            "phase": self.phase,
            "results": self.results,
            "champion": self.champion,
            "third": self.third,
            "ko_teams": self.ko_teams,
            "round_size": self.round_size,
            "pos": self.pos,
            "winners": self.winners,
            "sf_losers": self.sf_losers,
            "is_third": self.is_third,
            "final_teams": self._final_teams,
            "cur_slot": self.cur_slot,
            "start_ts": self.start_ts,
            "started": self.started,
            "version": self.version,
            "mcap_sol": self.mcap_sol,
            "price_sol": self.price_sol,
            "match": {
                "a": m.a, "b": m.b, "group": m.group, "stage": m.stage,
                "round_size": m.round_size, "final_a": m.final_a, "final_b": m.final_b,
                "goals": [list(g) for g in m.goals], "pen_winner": m.pen_winner,
                "ga": m.ga, "gb": m.gb, "minuto": m.minuto, "shown": m.shown,
            },
        }

    def from_dict(self, d):
        self.groups = d["groups"]
        self.stats = {int(k): v for k, v in d["stats"].items()}
        self.schedule = self._build_schedule()
        self.gm_pos = d["gm_pos"]
        self.phase = d["phase"]
        self.results = d["results"]
        self.champion = d["champion"]
        self.third = d["third"]
        self.ko_teams = d["ko_teams"]
        self.round_size = d["round_size"]
        self.pos = d["pos"]
        self.winners = d["winners"]
        self.sf_losers = d["sf_losers"]
        self.is_third = d["is_third"]
        self._final_teams = d.get("final_teams")
        self.cur_slot = d["cur_slot"]
        self.start_ts = d["start_ts"]
        self.started = d["started"]
        self.version = d.get("version", 1)
        self.mcap_sol = d.get("mcap_sol", 0.0)
        self.price_sol = d.get("price_sol", 0.0)
        self.energy = 0.0
        md = d["match"]
        mm = Match(md["a"], md["b"], group=md["group"], stage=md["stage"],
                   round_size=md.get("round_size", 0))
        mm.final_a = md["final_a"]
        mm.final_b = md["final_b"]
        mm.goals = [tuple(g) for g in md["goals"]]
        mm.pen_winner = md["pen_winner"]
        mm.ga = md["ga"]
        mm.gb = md["gb"]
        mm.minuto = md["minuto"]
        mm.shown = md["shown"]
        self.match = mm
