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

ROUND_NAMES = {48: "Ronda preliminar", 32: "16avos de final", 16: "Octavos de final",
               8: "Cuartos de final", 4: "Semifinal", 2: "Final", 1: "Campeón"}


def round_name(size):
    return ROUND_NAMES.get(size, "Ronda")


MATCH_LEN = 90
CLOCK_STEP = 2
ACTIVE_WINDOW = 3
CHAMP_HOLD = 8
ENERGY_DECAY = 0.90
DEMO = True


def buy_energy(sol):
    return min(35.0, 9.0 * (max(0.0, sol) ** 0.5))


def buy_attack(sol):
    return min(60.0, 6.0 + sol * 9.0)


class Match:
    def __init__(self, a, b):
        self.a = a
        self.b = b
        self.ga = 0
        self.gb = 0
        self.minuto = 0
        self.atk_a = 0.0
        self.atk_b = 0.0
        self.vol_a = 0.0
        self.vol_b = 0.0


class Tournament:
    def __init__(self):
        self.energy = 0.0
        self.idle_ticks = 999
        self._demo_mood = 0.5
        self._buy_accum = 0
        self._sol_max_accum = 0.0
        self.buys_tick = 0
        self.sol_max_tick = 0.0
        self.version = 0           # cambia cuando cambia el cuadro
        self.reset()

    def reset(self):
        order = list(range(len(CHAINS)))
        random.shuffle(order)
        self.results = []
        self.champion = None
        self.champion_hold = 0
        self.energy = 0.0
        self.idle_ticks = 999
        self._demo_mood = 0.5
        self._buy_accum = 0
        self._sol_max_accum = 0.0
        self.buys_tick = 0
        self.sol_max_tick = 0.0
        self.version += 1
        self._start_round(order[16:], order[:16], 48)

    def _start_round(self, teams, carry, size):
        self.teams = teams
        self.carry = carry
        self.round_size = size
        self.pos = 0
        self.winners = []
        self._start_match()

    def _start_match(self):
        a = self.teams[self.pos * 2]
        b = self.teams[self.pos * 2 + 1]
        self.match = Match(a, b)

    def matches_this_round(self):
        return len(self.teams) // 2

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
                sol = round(random.random() * random.random() * 4 + 0.05, 2)
                self.ingest_buy(sol)

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

    def _end_match(self):
        m = self.match
        self.version += 1
        if m.ga != m.gb:
            wi = m.a if m.ga > m.gb else m.b
        else:
            wi = m.a if m.vol_a >= m.vol_b else m.b
        self.results.append({
            "ronda": self.round_size,
            "a": CHAINS[m.a][1], "b": CHAINS[m.b][1],
            "ga": m.ga, "gb": m.gb, "win": CHAINS[wi][1],
        })
        self.winners.append(wi)
        self.pos += 1
        if self.pos * 2 >= len(self.teams):
            pool = self.winners + self.carry
            if len(pool) <= 1:
                self.champion = pool[0] if pool else None
                self.champion_hold = CHAMP_HOLD
            else:
                self._start_round(pool, [], len(pool))
        else:
            self._start_match()

    def bracket_state(self):
        by_round = {}
        for r in self.results:
            by_round.setdefault(r["ronda"], []).append(r)
        rounds = []
        for size in (48, 32, 16, 8, 4, 2):
            done = by_round.get(size, [])
            is_current = (size == self.round_size and self.champion is None)
            if not done and not is_current:
                continue
            matches = []
            for r in done:
                matches.append({"a": r["a"], "b": r["b"], "ga": r["ga"], "gb": r["gb"],
                                "win": r["win"], "st": "done"})
            if is_current:
                total = self.matches_this_round()
                for i in range(self.pos, total):
                    ca = CHAINS[self.teams[i * 2]][1]
                    cb = CHAINS[self.teams[i * 2 + 1]][1]
                    if i == self.pos:
                        mm = self.match
                        matches.append({"a": ca, "b": cb, "ga": mm.ga, "gb": mm.gb,
                                        "win": None, "st": "live"})
                    else:
                        matches.append({"a": ca, "b": cb, "ga": 0, "gb": 0,
                                        "win": None, "st": "next"})
            rounds.append({"size": size, "name": round_name(size), "matches": matches})
        return {"type": "bracket", "rounds": rounds,
                "campeon": (CHAINS[self.champion][1] if self.champion is not None else None)}

    def snapshot(self):
        m = self.match
        a = CHAINS[m.a]
        b = CHAINS[m.b]
        return {
            "type": "state",
            "ronda": round_name(self.round_size),
            "ronda_size": self.round_size,
            "partido": self.pos + 1,
            "partidos_ronda": self.matches_this_round(),
            "minuto": m.minuto,
            "energia": round(self.energy),
            "activo": self.idle_ticks <= ACTIVE_WINDOW,
            "buys": self.buys_tick,
            "sol_max": round(self.sol_max_tick, 2),
            "bver": self.version,
            "local": {"short": a[1], "name": a[0], "color": a[2], "goles": m.ga, "atk": round(m.atk_a)},
            "visita": {"short": b[1], "name": b[0], "color": b[2], "goles": m.gb, "atk": round(m.atk_b)},
            "campeon": (CHAINS[self.champion][1] if self.champion is not None else None),
        }
