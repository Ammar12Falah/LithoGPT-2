# BENCHMARK

## 2026-07-11 Architecture decision capture (advisor ruling, reviewed not absorbed silently)

Verbatim ruling:
"Method for the transfer track is a from-scratch decoder-only transformer. A LoRA-adapted open time-series foundation model runs as a two-day baseline immediately after benchmark freeze, evaluated on dev and open-leaderboard wells only. Pre-registered tripwire: if the adapted TS-FM beats the from-scratch S-model cross-basin on the dev slice by more than 10 percent relative RMSE on at least two of three target curves, a scope amendment is brought before further training spend. The FORCE blind wells are touched once, by the final scoring path, and never by selection, comparison, or tripwire evaluation."

Recorded per advisor amendment 4; pre-registration predates the post-benchmark-freeze TS-FM tripwire baseline. Attribution: advisor. Reviewed at capture.
