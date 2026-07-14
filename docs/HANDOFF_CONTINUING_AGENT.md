# LithoGPT-2: Handoff to a Continuing Agent

Date 9 July 2026. This hands an in-progress build to a new agent with zero prior
context. With repo access (github.com/Ammar12Falah/LithoGPT-2, branch main) and
this document you can continue without other context. Owner: Ammar Falah. Read
Section 0 first, then 1, then 6 which is where the live work is.

Repo HEAD at handoff: 7c8d1f2 (pushed). Everything in git is safe. The one
expensive artifact not in git is called out in Section 7.

For full technical background read docs/PROJECT_DOSSIER.md (complete project
record) and docs/HANDOFF.md (design authority). This file is the operational
"what to do next." The dossier is the "what this all is."

---

## 0. First actions on a fresh pod

The pod environment never persists across restarts, and the data lives on a
network volume, not in git. Before anything else:

1. Confirm the volume mounted and the repo is present:
