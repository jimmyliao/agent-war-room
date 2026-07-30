---
name: evidence-based-debugging
description: Investigate a reproducible software incident and produce a diagnosis backed by controlled evidence.
---

# Evidence-based debugging

1. Separate observed facts from assumptions.
2. Build at least two plausible hypotheses when evidence permits.
3. Prefer read-only inspection before any mutation.
4. Change only one variable in each controlled experiment.
5. Record the command, input, output, and timestamp for every experiment.
6. Distinguish correlation from causal evidence.
7. Do not claim root cause until the visible symptom is reproduced.
8. Propose a regression test that fails before the fix and passes after it.
9. Never expose credentials, private model reasoning, or unredacted user data.
10. Never modify a deployed service without explicit approval.

The final diagnosis artifact must contain:

- observed facts
- hypotheses considered
- experiments performed
- evidence
- root cause
- proposed fix
- regression test
- remaining uncertainty

