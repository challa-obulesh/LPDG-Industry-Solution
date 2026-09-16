# Part 2 Final Model Decision

## Decision

**Final model: Logistic Regression.**

## Evidence

- Forward historical proxy-label cost: €270,600.
- Forward precision@15: 1.0000.
- Forward recall: 0.2102.
- Unseen-gateway proxy cost: €28,940.
- Unseen-gateway precision@15: 0.3540.
- Unseen-gateway recall: 0.9524.

All tested ML candidates matched these operational results on the validation period, forward weeks, and unseen-gateway slice. No alternative model demonstrated a lower cost or better supported robustness, so Logistic Regression is final because of its simpler interpretation and reproducibility.

I did not assume that a more complex model would automatically perform better. I benchmarked Logistic Regression, Random Forest, Extra Trees and HistGradientBoosting using the same operational evaluation. They produced identical measured results, so I retained Logistic Regression because it provides simpler interpretation and reproducibility.

These results are based on historical proxy labels and should not be presented as official hidden-groundtruth performance. The target is telemetry-derived, the gateway population changes over time, and field visits are selected operational evidence rather than complete ground truth. The €58,800 figure is lower historical proxy-label cost, not confirmed real-world savings.

## Protection and next step

The benchmark did not modify Part 1, `baseline_3sigma.py`, `validate_submission.py`, `predictions.csv`, the target definition, or original challenge data. Keep the final model frozen and seek independently observed outcomes before claiming official improvement.
