import sys, numpy as np
sys.path.insert(0, "/workspace/LithoGPT-2/scripts/basinshift")
import eval_harness as H
SEQ = 512
DEV = {"kgs_dev": ("kgs", "dev"), "nlog_dev": ("nlog", "dev")}
POOLS = dict(H.POOLS)
for k, (src, sp) in DEV.items():
    POOLS[k] = H.wells_of(src, sp)
def pool_windows(pool):
    tw = 0; nw = 0; tvalid = {t: 0 for t in H.TARGETS}
    for (src, safe, wid) in POOLS[pool]:
        df = H.load_well(src, safe, wid); L = len(df)
        tw += -(-L // SEQ); nw += 1
        for t in H.TARGETS:
            y = df[t].to_numpy(); tvalid[t] += int((~np.isnan(y)).sum())
    return nw, tw, tvalid
for p in ["kgs_train", "nlog_train", "force_train", "test_kgs", "open10", "kgs_dev", "nlog_dev"]:
    nw, tw, tv = pool_windows(p)
    print("POOL %s wells=%d windows=%d validDTC=%d validRHOB=%d validNPHI=%d"
          % (p, nw, tw, tv["DTC"], tv["RHOB"], tv["NPHI"]))
print("COUNT_DONE")
