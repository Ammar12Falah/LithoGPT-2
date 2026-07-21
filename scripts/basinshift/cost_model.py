#!/usr/bin/env python3
"""TS-FM Stage 1 A40 cost estimate. Pure arithmetic from the CPU smoke timings.
Method per brief Part 3: CPU smoke per-step time -> per-window fwd+bwd -> scale by a stated
CPU->A40 speedup -> multiply by the proposed full-run window-presentation budget. Inference is a
minor additive term. Produces low / expected / high and a speedup sensitivity table."""

# --- measured CPU smoke primitives (batch=4, 8 steps, MOMENT load excluded) ---
CPU_S_PER_STEP = {"A": 17.09, "B": 29.14}      # pretrained; s/step at batch 4
BATCH_SMOKE = 4
CPU_S_PER_WINDOW = {k: v / BATCH_SMOKE for k, v in CPU_S_PER_STEP.items()}   # fwd+bwd s/window
CPU_S_PER_WINDOW_INFER = 1.5                    # fwd-only, batch 64 (from t_infer ~95s / ~63 win)

# --- A40 rate (runpod.io/pricing, A40 48GB) ---
RATE = {"community": 0.35, "secure": 0.44}
RATE_EXPECTED = RATE["secure"]                  # pod is a persistent EU/secure volume

# --- CPU->A40 per-window speedup (341M transformer; folds in tensor cores + larger A40 batch) ---
SPEEDUP = {"high_cost": 40, "expected": 75, "low_cost": 120}   # higher speedup => lower cost

# --- proposed full-run schedule (RECOMMENDED; the knob Plan locks) ---
# 12 cells per config (4 directions x 3 targets), faithful apples-to-apples with XGBoost's 12 fits.
CELLS = 12
STEPS_PER_CELL = 600
BATCH_FULL = 32
WP_PER_CONFIG = CELLS * STEPS_PER_CELL * BATCH_FULL     # window-presentations / config
# 3 trainings: pretrained-A, pretrained-B, control-on-winner (winner unknown -> bracket its config)

# inference window-presentations (bounded): 2 configs do dev-selection + all configs infer test.
INFER_WP = 2 * 55000 + 3 * 4000   # dev (kgs_dev+nlog_dev ~) x2 configs + test cells x3 configs


def train_cpu_seconds(control_cfg):
    a = WP_PER_CONFIG * CPU_S_PER_WINDOW["A"]
    b = WP_PER_CONFIG * CPU_S_PER_WINDOW["B"]
    c = WP_PER_CONFIG * CPU_S_PER_WINDOW[control_cfg]
    return a + b + c


def hours(cpu_seconds, speedup):
    return cpu_seconds / speedup / 3600.0


def scenario(name, speedup, control_cfg, rate):
    tr = hours(train_cpu_seconds(control_cfg), speedup)
    inf = hours(INFER_WP * CPU_S_PER_WINDOW_INFER, speedup)
    tot = tr + inf
    return dict(name=name, speedup=speedup, control=control_cfg, train_hr=tr, infer_hr=inf,
                total_hr=tot, dollars=tot * rate, rate=rate)


print("=== TS-FM Stage 1 A40 cost estimate (from CPU smoke) ===")
print("CPU per-window fwd+bwd: cfgA=%.2fs cfgB=%.2fs (batch %d smoke)" %
      (CPU_S_PER_WINDOW["A"], CPU_S_PER_WINDOW["B"], BATCH_SMOKE))
print("Proposed schedule: %d cells x %d steps x batch %d = %d window-presentations/config" %
      (CELLS, STEPS_PER_CELL, BATCH_FULL, WP_PER_CONFIG))
print("3 configs (pretrained-A, pretrained-B, control). A40 rate expected $%.2f/hr (secure).\n" % RATE_EXPECTED)

rows = [
    scenario("LOW  (S=120, control=A, $0.35)", SPEEDUP["low_cost"], "A", RATE["community"]),
    scenario("EXP  (S=75,  control=A, $0.44)", SPEEDUP["expected"], "A", RATE["secure"]),
    scenario("HIGH (S=40,  control=B, $0.44)", SPEEDUP["high_cost"], "B", RATE["secure"]),
]
print("%-34s %8s %8s %9s %8s" % ("scenario", "train_hr", "infer_hr", "total_hr", "USD"))
for r in rows:
    print("%-34s %8.1f %8.2f %9.1f %8.2f" %
          (r["name"], r["train_hr"], r["infer_hr"], r["total_hr"], r["dollars"]))

print("\n-- speedup sensitivity (expected schedule, control=A, $0.44/hr) --")
print("%8s %9s %8s" % ("speedup", "total_hr", "USD"))
for s in [40, 60, 75, 90, 120]:
    r = scenario("s", s, "A", RATE["secure"])
    print("%8d %9.1f %8.2f" % (s, r["total_hr"], r["dollars"]))

print("\nTwo-day (48 h) budget fit: HIGH total = %.1f h -> %s"
      % (rows[2]["total_hr"], "FITS" if rows[2]["total_hr"] < 48 else "EXCEEDS"))
