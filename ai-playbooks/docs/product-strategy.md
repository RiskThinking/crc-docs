# Product strategy: open foundation, enterprise lift

## Positioning

CRC supplies an inspectable open computation and data workflow; VELO/CDT supplies
additional enterprise evidence. Pair them only when the business question needs
both. See the [problem map](../../README.md#choose-a-problem) for entry points and
[capability matrix](capability-matrix.md) for the verified package boundary.
Do not claim that every VELO/CDT component runs on CRC or that unlike metrics are
equivalent.

## Demonstration pattern

Every demo follows one narrative:

1. Frame the problem: collateral review, underwriting triage, or investment diligence.
2. Run the CRC baseline on user-supplied assets or clearly labelled Overture candidate locations with JRC or another canonical hazard dataset.
3. Show the baseline's provenance, assumptions, coverage, unresolved assets, and extrapolation.
4. Run the VELO/CDT twin on the aligned asset/company/index and scenario.
5. Reconcile only comparable dimensions; label the rest as capability lift.
6. End with a decision memo and a next-data recommendation, not an opaque score.

## Domain prioritization

### 1. Mortgage and commercial real estate

Best first demo. A single property is intuitive, JRC flood depth is explainable, and VELO can add proprietary asset identity, broader hazards, scenarios, and tail metrics. The open baseline can support screening; the enterprise twin is positioned for underwriting and portfolio governance.

### 2. Property insurance

Strong second demo. CRC makes the vulnerability assumption explicit through depth-damage functions and event-aligned impacts. VELO adds portfolio-level insurability/stranding triage and multi-factor attribution. Keep pricing and capital claims out of scope unless actuarial calibration is supplied.

### 3. Corporate and investment climate diligence

Strongest proprietary differentiation. CRC can assess a supplied asset book or AI-selected Overture candidate locations, but Overture does not prove company ownership or materiality. VELO adds companies, subsidiaries/assets, market indexes, country/type aggregation, and company/index risk metrics.

### 4. Compliance and disclosure evidence

Treat this as an output layer across the three domains rather than a standalone hazard calculation. CRC's self-describing canonical Parquet contract is well suited to reproducibility. VELO needs an exportable methodology/version/evidence bundle so enterprise results can enter model-risk and disclosure workflows.

## Future open CDT hazard dataset

Design now for a source adapter that produces the existing CRC canonical hazard Parquet contract. Do not fork the downstream workflow. For any future release, validate its canonical output before reusing the portfolio, impact and comparison workflows. This is an integration proposal, not a claim that a release is available.

The release-ready integration contract should include:

- stable dataset and release identifiers;
- hazard name, value unit, and semantics;
- pathway and horizon conventions;
- non-exceedance probability convention and source return-period support;
- source resolution, H3 resolution, and geometry precision;
- license and redistribution terms;
- checksums, producer version, and creation time;
- an adapter conformance fixture with expected canonical rows and quantiles.
