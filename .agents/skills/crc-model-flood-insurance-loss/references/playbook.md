# Flood loss playbook

Install `crc-sdk[geometry]==0.3.0` for point-asset evaluation.

## Native crc-docs examples

- `notebooks/portfolio_impact.ipynb` / `pipelines/portfolio_impact_pipeline.py`: event-aligned flood depth, damage ratio, and derived replacement loss.
- `notebooks/portfolio_risk_metrics.ipynb` / `pipelines/portfolio_risk_pipeline.py`: microscores, binary outcomes, portfolio VaR/CVaR, and attribution.

The checked-in curve is intentionally hypothetical. Replace it with an approved, cited curve for a decision-facing assessment.

Select exactly one canonical `pathway` and `horizon` before return-period
evaluation. A Parquet may contain several scenarios; evaluating it without both
filters can produce multiple rows per asset and an ambiguous loss result.

## Event-aligned semantics

CRC portfolio impact evaluation samples the hazard at each source-event return period and then evaluates the impact function. Therefore `value_rp100` means damage ratio for the hazard's 100-year event. It is not necessarily the 99th percentile of a transformed loss distribution when a transform is decreasing or non-monotonic.

Use `crc-framework` distribution transformation and risk metrics only when the requested decision requires the distribution interpretation, and state the change explicitly.

## Curve quality checklist

- Citation and version.
- Asset/building class.
- Geography and construction assumptions.
- Depth datum and units.
- Contents/building/business-interruption scope.
- Monotonicity and clipping.
- Calibration period and observed claims evidence.
- Uncertainty bounds.

The bundled script accepts comma-separated depth and ratio knots and constructs `PiecewiseLinearImpact`. It is reproducible but not actuarially calibrated by itself.
