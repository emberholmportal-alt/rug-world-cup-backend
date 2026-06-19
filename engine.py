import random

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

MATCH_LEN = 90
CLOCK_STEP = 2
ACTIVE_WINDOW = 3
CHAMP_HOLD = 8
ENERGY_DECAY = 0.90
DEMO = False     # buy-driven: el torneo NO corre solo; arranca con la primera compra

# calendario round-robin de 4 equipos (indices locales 0-3), 3 fechas
RR_ROUNDS = [[(0, 3), (1, 2)], [(0, 2), (3, 1)], [(0, 1), (2, 3)]]


def buy_energy(sol):
    return min(35.0, 9.0 * (max(0.0, sol) ** 0.5))


def buy_attack(sol):
    return min(60.0, 6.0 + sol * 9.0)


class Match:
    def __init__(self, a, b, group=None, stage="grupos"):
        self.a = a
        self.b = b
        self.ga = 0
        self.gb = 0
        self.minuto = 0
        self.atk_a = 0.0
        self.atk_b = 0.0
        self.vol_a = 0.0
        self.vol_b = 0.0
        self.group = group
        self.stage = stage


class Tournament:
    def __init__(self):
        self.version = 0
        self.energy = 0.0
        self.idle_ticks = 999
        self._demo_mood = 0.5
        self._buy_accum = 0
        self._sol_max_accum = 0.0
        self.buys_tick = 0
        self.sol_max_tick = 0.0
        self.reset()

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
        self.champion_hold = 0
        self.ko_teams = []
        self.round_size = 0
        self.pos = 0
        self.winners = []
        self.sf_losers = []
        self.is_third = False
        self._final_teams = None
        self.energy = 0.0
        self.idle_ticks = 999
        self._demo_mood = 0.5
        self._buy_accum = 0
        self._sol_max_accum = 0.0
        self.buys_tick = 0
        self.sol_max_tick = 0.0
        self.version += 1
        self._start_group_match()

    def _build_schedule(self):
        s = []
        for rnd in RR_ROUNDS:
            for gi, g in enumerate(self.groups):
                for (i, j) in rnd:
                    s.append((gi, g[i], g[j]))
        return s   # 3 fechas * 12 grupos * 2 = 72

    def _start_group_match(self):
        gi, a, b = self.schedule[self.gm_pos]
        self.match = Match(a, b, group=gi, stage="grupos")

    def _start_ko_match(self):
        a = self.ko_teams[self.pos * 2]
        b = self.ko_teams[self.pos * 2 + 1]
        self.match = Match(a, b, group=None, stage=("3er" if self.is_third else "ko"))

    def matches_in_round(self):
        if self.phase == "grupos":
            return len(self.schedule)
        if self.is_third:
            return 1
        return len(self.ko_teams) // 2

    # ---------- compras ----------
    def ingest_buy(self, sol):
        if self.champion is not None:
            return
        m = self.match
        self._buy_accum += 1
        self._sol_max_accum = max(self._sol_max_accum, sol)
        self.idle_ticks = 0
        self.energy = min(100.0, self.energy + buy_energy(sol))
        atk = buy_attack(sol)
        if random.random() < 0.5:
            m.atk_a += atk
            m.vol_a += sol
        else:
            m.atk_b += atk
            m.vol_b += sol
        if m.atk_a >= 100:
            m.ga += 1
            m.atk_a -= 100
        if m.atk_b >= 100:
            m.gb += 1
            m.atk_b -= 100

    def _demo_buys(self):
        self._demo_mood += random.uniform(-0.25, 0.25) + (0.5 - self._demo_mood) * 0.1
        self._demo_mood = max(0.0, min(1.0, self._demo_mood))
        if random.random() < self._demo_mood:
            n = 1 + int(random.random() * self._demo_mood * 4)
            for _ in range(n):
                self.ingest_buy(round(random.random() * random.random() * 4 + 0.05, 2))

    def tick(self):
        if self.champion is not None:
            self.champion_hold -= 1
            if self.champion_hold <= 0:
                self.reset()
            return
        self.energy *= ENERGY_DECAY
        self.idle_ticks += 1
        if DEMO:
            self._demo_buys()
        self.buys_tick = self._buy_accum
        self.sol_max_tick = self._sol_max_accum
        self._buy_accum = 0
        self._sol_max_accum = 0.0
        if self.idle_ticks <= ACTIVE_WINDOW:
            for _ in range(CLOCK_STEP):
                self.match.minuto += 1
                if self.match.minuto >= MATCH_LEN:
                    self._end_match()
                    return

    # ---------- standings ----------
    def _record_group(self, m):
        a, b, sa, sb = m.a, m.b, m.ga, m.gb
        A, B = self.stats[a], self.stats[b]
        A["pj"] += 1
        B["pj"] += 1
        A["gf"] += sa
        A["gc"] += sb
        B["gf"] += sb
        B["gc"] += sa
        if sa > sb:
            A["g"] += 1
            B["p"] += 1
            A["pts"] += 3
        elif sb > sa:
            B["g"] += 1
            A["p"] += 1
            B["pts"] += 3
        else:
            A["e"] += 1
            B["e"] += 1
            A["pts"] += 1
            B["pts"] += 1

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
        self.version += 1
        if self.phase == "grupos":
            self._record_group(m)
            self.results.append({"fase": "grupos", "grupo": GROUP_LETTERS[m.group],
                                 "a": CHAINS[m.a][1], "b": CHAINS[m.b][1],
                                 "ga": m.ga, "gb": m.gb})
            self.gm_pos += 1
            if self.gm_pos >= len(self.schedule):
                self._start_knockout()
            else:
                self._start_group_match()
            return

        # --- eliminatoria ---
        if m.ga != m.gb:
            win, lose = (m.a, m.b) if m.ga > m.gb else (m.b, m.a)
        else:
            win, lose = (m.a, m.b) if m.vol_a >= m.vol_b else (m.b, m.a)
        size = 3 if self.is_third else self.round_size
        ronda = "Tercer puesto" if self.is_third else ROUND_NAMES.get(self.round_size, "")
        self.results.append({"fase": "ko", "ronda": ronda, "size": size,
                             "a": CHAINS[m.a][1], "b": CHAINS[m.b][1],
                             "ga": m.ga, "gb": m.gb, "win": CHAINS[win][1]})

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
                self.champion_hold = CHAMP_HOLD
            elif self.round_size == 4:
                # semis terminadas: primero el 3er puesto, despues la final
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

    # ---------- snapshots ----------
    def snapshot(self):
        m = self.match
        a, b = CHAINS[m.a], CHAINS[m.b]
        if self.phase == "grupos":
            ronda = "Fase de grupos"
            fecha = self.gm_pos // 24 + 1
            grupo = GROUP_LETTERS[m.group]
            partido = self.gm_pos + 1
            total = len(self.schedule)
        else:
            ronda = "Tercer puesto" if self.is_third else ROUND_NAMES.get(self.round_size, "")
            fecha = None
            grupo = None
            partido = self.pos + 1
            total = self.matches_in_round()
        return {
            "type": "state", "fase": self.phase, "ronda": ronda, "fecha": fecha,
            "grupo": grupo, "partido": partido, "partidos_ronda": total,
            "minuto": m.minuto, "energia": round(self.energy),
            "activo": self.idle_ticks <= ACTIVE_WINDOW,
            "buys": self.buys_tick, "sol_max": round(self.sol_max_tick, 2), "bver": self.version,
            "local": {"short": a[1], "name": a[0], "color": a[2], "goles": m.ga, "atk": round(m.atk_a)},
            "visita": {"short": b[1], "name": b[0], "color": b[2], "goles": m.gb, "atk": round(m.atk_b)},
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
