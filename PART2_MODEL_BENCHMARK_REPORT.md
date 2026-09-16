# Part 2 Model Selection Record

## Final model

**Final model: Logistic Regression.**

I did not assume that a more complex model would automatically perform better. I benchmarked Logistic Regression, Random Forest, Extra Trees and HistGradientBoosting using the same operational evaluation. They produced identical measured results, so I retained Logistic Regression because it provides simpler interpretation and reproducibility.

## Controlled evidence

All four models used the same 8,011 gateway-week rows, 99 engineered features, persistent degradation target, chronological gateway-week split, eligible gateway universe, top-15 weekly selection, and cost function. The benchmark did not change the target, feature engineering, temporal split, leakage controls, or Part 1 files.

| Metric | Measured result for each ML model |
|---|---:|
| Validation cost | €130,200 |
| Forward cost | €270,600 |
| Precision@15 | 1.0000 |
| Recall | 0.2102 |
| Unseen-gateway cost | €28,940 |
| Unseen-gateway precision | 0.3540 |
| Unseen-gateway recall | 0.9524 |

The unchanged 3-sigma baseline forward cost was €329,400. Logistic Regression therefore had €58,800 lower historical proxy-label cost across the eight forward weeks. This is not confirmed real-world savings.

## Methodology retained

- Features use only information strictly before each Monday cutoff; future telemetry is label-only.
- The target is persistent degradation across the complete following seven-day window: at least 84 observed hours, degradation on at least 2 distinct days, and at least 6 degraded hours.
- Duplicate telemetry is handled deterministically with median aggregation and retained quality indicators.
- Exactly 15 gateways are selected per week.
- An unnecessary visit costs €380; a missed broken gateway costs €600 per week.
- The 35-gateway unseen slice is evaluated separately without fitting on those gateways.

These results are based on historical proxy labels and should not be presented as official hidden-groundtruth performance. The proxy target is telemetry-derived and is not a confirmed hardware-failure label.

## Final implementation

The runnable Part 2 path uses only the existing Logistic Regression implementation and artifact:

```powershell
.venv\Scripts\python.exe run_part2.py
```

The validated model is stored at `models/logistic_regression.joblib`. The benchmark model source, alternative model binaries, and comparison-only generated files were removed after the selection decision. The concise evidence above is retained so the final model choice remains auditable.
