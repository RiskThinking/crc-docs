# Product strategy: open foundation, enterprise lift

## Positioning

Lead with an auditable open baseline, then demonstrate the decision lift from VELO/CDT on the same business question. The message is not “open is a teaser.” It is:

1. CRC is the transparent computation and workflow foundation.
2. The community can bring open or owned hazard data and inspect every modelling choice.
3. VELO/CDT industrializes that foundation with broader and finer hazard coverage, proprietary physical-asset and ownership data, multi-factor scenarios, and enterprise-ready scores.
4. A paired assessment shows which decisions can be made with the baseline and which need the enterprise lift.

Avoid claiming that every current VELO/CDT component already runs on CRC. Use the accurate formulation: “CRC is the target open foundation and an increasing share of the VELO/CDT pipeline is being materialized on that stack.”

## Demonstration pattern

Every demo follows one narrative:

1. Frame the decision: collateral review, underwriting triage, or investment diligence.
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

Design now for a source adapter that produces the existing CRC canonical hazard Parquet contract. Do not fork the downstream workflow. When the dataset is released, the same portfolio, impact, and comparison skills should work by changing only the dataset acquisition step.

The release-ready integration contract should include:

- stable dataset and release identifiers;
- hazard name, value unit, and semantics;
- pathway and horizon conventions;
- non-exceedance probability convention and source return-period support;
- source resolution, H3 resolution, and geometry precision;
- license and redistribution terms;
- checksums, producer version, and creation time;
- an adapter conformance fixture with expected canonical rows and quantiles.
