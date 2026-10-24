"""Event exports for the perf item: seeded, with the quirks the original report tolerates."""
import random

ACTIONS = ["login", "view", "search", "cart", "checkout", "refund", "Export", "export"]


def events(seed, rows, users, quirks=True):
    """CSV text with `rows` data lines over about `users` user names."""
    rng = random.Random(seed)
    names = [f"u{index:05d}" for index in range(users)]
    lines = ["ts,user,action,amount"]
    for index in range(rows):
        day, second = rng.randrange(1, 29), rng.randrange(86400)
        ts = f"2026-09-{day:02d}T{second // 3600:02d}:{second // 60 % 60:02d}:{second % 60:02d}"
        user = rng.choice(names)
        action = rng.choice(ACTIONS)
        amount = f"{rng.randrange(0, 50000) / 100:.2f}"
        if quirks:
            roll = rng.random()
            if roll < 0.02:
                user = user.upper()
            elif roll < 0.04:
                amount = rng.choice(["n/a", "", "12,5", "-"])
            elif roll < 0.05:
                amount = rng.choice(["1e3", "2.5e1", "-7.25", "0", "100"])
            elif roll < 0.06:
                lines.append(rng.choice(["# export resumed", "", "   ", "ts,user,action,amount", "ts, user, action, amount"]))
            elif roll < 0.07:
                lines.append(f"{ts},{user},{action}")
                continue
            elif roll < 0.08:
                lines.append(f"  {ts} , {user} ,{action}, {amount}  ")
                continue
        lines.append(f"{ts},{user},{action},{amount}")
    return "\n".join(lines) + "\n"


# The workspace export: slow enough under the original that it barely finishes within a 10-second command.
WORKSPACE = ("perf-workspace", 40000, 10000, True)
# Hidden inputs: name -> (seed, rows, users, quirks). The large one is the speed test.
HIDDEN = {
    "quirks-a": ("perf-a", 3000, 400, True),
    "quirks-b": ("perf-b", 2500, 60, True),
    "ties": None,
    "empty": None,
    "large": ("perf-large", 60000, 12000, True),
}

# Hand-made inputs for exact ties, negative and exponent amounts, and an export with no valid row.
TIES = """ts,user,action,amount
2026-09-01T00:00:01,bob,view,10
2026-09-01T00:00:02,amy,view,10
2026-09-01T00:00:03,Cid,view,5
2026-09-01T00:00:04,cid,view,5
2026-09-02T00:00:00,dee,refund,-2.25
2026-09-02T00:00:01,dee,refund,1e1
2026-09-02T00:00:02,eve,view,0.05
2026-09-02T00:00:03,eve,view,0.15
# trailing comment
"""
EMPTY = """ts,user,action,amount
# nothing exported
ts,user,action,amount
2026-09-01T00:00:01,bob,view
"""
