# EllipticZero Report Specification

## 1. Scope

This document defines the required structure and tone of the final research report. Its job is to communicate:

- what was investigated
- what was observed
- what the evidence supports
- what remains uncertain
- where manual review is required

The report is not a marketing artifact, not a conversational summary, and not a venue for impressionistic speculation.

## 2. Required Structure

Every `ResearchReport` must contain these sections in a clear and stable order:

1. Session overview
   Must identify the session, scope, original seed summary, and objective.
2. Original research seed
   Must preserve the initiating idea and distinguish it from system normalization or restatement.
3. Formalized problem statement
   Must state the mathematical or implementation problem actually investigated, including assumptions, constraints, and scope boundaries.
4. Hypotheses and branches
   Must record the material branches, their expected evidence, and their status.
5. Method and local compute summary
   Must explain the reasoning workflow, local computation path, tool usage, and important limitations.
6. Evidence summary
   Must distinguish raw observations, derived interpretations, contradictory observations, and missing evidence.
7. Validation outcome
   Must separate supported findings, unsupported hypotheses, inconclusive branches, deferred items, and manual review items.
8. Confidence assessment
   Must assign bounded confidence categories and briefly justify them.
   When useful, it should also preserve a short evidence profile, evidence-coverage summary, compact validation posture, shared bounded follow-up, dominant calibration blockers, reproducibility summary, toolchain fingerprint, secret-redaction summary, quality gates, and a hardening summary so the reader can see what shaped the assigned confidence level.
9. Limitations and risks
   Must record evidence gaps, unresolved contradictions, assumption sensitivity, and methodological risks.
10. Recommended next actions
   Must remain bounded and should not exaggerate what the evidence supports.

For smart-contract sessions, the report should also preserve contract-specific detail when it materially informed the session:

- contract overview
- contract inventory and scoped repository context
- first-party vs dependency scope when repository inventory materially affected review order
- a short protocol map when the report can show which entrypoints, authority paths, accounting modules, and pricing/collateral modules form the bounded repository review contour
- short protocol invariants when the report can state which protocol assumptions should remain true across the strongest bounded review families and lanes
- short signal-consensus summaries when the report can show where compile, surface, static, casebook, or invariant paths converge or still leave important gaps
- a short validation-matrix block when the report can show the current posture, support, and replay gaps for the strongest repository lanes
- a short benchmark-posture block when the report can state how much bounded repo-casebook support backs the strongest repository lanes
- a short benchmark-pack summary when a bounded smart-contract benchmark pack materially structured the local review path
- bounded confidence-calibration notes when the report can explain which support vectors, replay anchors, or unresolved gaps kept the assigned confidence level narrow
- repo-scale strongest priorities when cross-file evidence materially shaped review order
- repo triage for the first bounded review pass when repository lanes, function families, and casebook alignment materially shaped review order
- bounded repo-casebook coverage when repository case-study paths materially informed review order
- a short casebook-coverage matrix when the report can compare the current posture, dominant issues, validation support, and matched risk families across the strongest bounded repo-casebooks
- compact case-study summaries when bounded repo-casebook paths materially shaped the audit narrative
- short archetype labels when the report can tie matched repo-casebook paths to bounded governance/timelock, rewards/distribution, stablecoin/collateral, AMM/liquidity, bridge/custody, staking/rebase, keeper/auction, treasury/vesting, insurance/recovery, or similar protocol-style scenarios
- short benchmark-case summaries when a bounded smart-contract benchmark pack materially shaped which anomaly-bearing or control cases mattered first
- short priority-case lines naming the strongest matched repo-casebook cases when those examples materially shaped review order
- a short casebook-gap block naming which repo review lanes or function-family priorities remain unmatched by the current bounded casebook run
- benchmark-support summaries when the report can responsibly state which local compile, static, invariant, or structural paths supported the current repo-casebook review
- a short casebook triage block highlighting the strongest bounded repo-casebook match and its current validation posture
- a short toolchain-alignment block showing which local compile, surface, static, invariant, structural, or casebook paths support the strongest repo lanes, including lanes that span more than one matched family, and where replay gaps remain
- a short review-queue block naming which repo lane to inspect first, which matched case anchors that lane, and which bounded replay path should follow
- compact finding cards when the report can connect a bounded potential finding to local evidence, why it matters, a defensive fix direction, and a recheck path
- short residual-risk lines when the report can state which strongest repo lanes remain open, why they remain open, and which matched casebook or toolchain signals still anchor them
- a short exit-criteria block naming what should weaken, disappear, or remain unresolved before the strongest repo lane can be treated as meaningfully narrowed
- more specific bounded benchmark-pack summaries when upgrade/control, governance/timelock, rewards/distribution, stablecoin/collateral, AMM/liquidity, bridge/custody, staking/rebase, keeper/auction, treasury/vesting, insurance/recovery, vault/permission, or lending-style benchmark packs materially structured the current review path
- a short before/after comparison block when a saved baseline session is attached and the report can cautiously state which bounded signals narrowed, widened, or stayed stable across the two runs
- short regression flags when a saved baseline session is attached and the report can name which bounded tool paths, review counts, or casebook gaps widened or disappeared relative to the baseline
- entrypoint and risk-family review lanes when repo-scale audit paths were used
- entrypoint function-family priorities when repo-scale audit paths materially shaped review order
- bounded repo-casebook findings when repository case-study paths materially informed review order
- bounded remediation-validation notes when control variants materially weakened the strongest local signal
- remediation follow-up priorities when the report can responsibly name which review lanes and local tool paths should be re-checked after defensive hardening
- cautious defensive remediation guidance when bounded evidence justifies concrete hardening directions
- compile status
- contract surface summary
- static findings
- contract testbed findings
- manual review items tied to concrete contract functions, flows, or protocol-style collateral/liquidation/liquidation-fee/reserve and protocol-fee/reserve-buffer/debt/bad-debt-socialization paths when those signals materially shaped the session

For ECC-focused sessions, the report should preserve ECC-specific detail when it materially informed the session:

- a short ECC benchmark summary when bounded ECC testbed packs materially shaped review order
- a short ECC benchmark-posture block when the report can state how much bounded support backs the strongest ECC families
- a short ECC family-coverage block when the report can summarize which ECC review families are covered broadly, partially, or narrowly
- a short ECC coverage-matrix block when the report can summarize the current support, baseline state, and residual-risk posture for the strongest ECC review families
- short ECC benchmark-case summaries when bounded ECC packs materially shaped which local family-specific cases mattered first
- a short ECC review-focus block when local encoding, family-transition, domain, subgroup, cofactor, or twist-style signals narrowed the next defensive checks
- short residual-risk lines when bounded ECC review still leaves family-specific encoding, subgroup, cofactor, twist, family-transition, or domain-completeness assumptions unresolved
- short ECC signal-consensus lines when the report can show where curve-metadata, point-format, consistency, and testbed paths already converge or still remain narrow
- a short ECC validation-matrix block when the report can state the current posture, support labels, and baseline delta for the strongest ECC review families
- a short ECC comparison-focus block when a saved baseline session is attached and the report can cautiously name which ECC review families narrowed, widened, or stayed stable across the two runs
- a short ECC benchmark-delta block when a saved baseline session is attached and the report can cautiously describe how the current ECC benchmark support moved relative to the bounded baseline
- a short ECC regression-summary block when a saved baseline session is attached and the report can state which ECC families stayed stable, narrowed, or still show regression risk
- a short ECC review-queue block when the report can name which ECC family to re-check first and what current support still anchors it
- a short ECC exit-criteria block when the report can state what should narrow, disappear, or remain explicitly manual-review-only before the strongest ECC family can be treated as meaningfully bounded

## 3. Language Rules

The report must be:

- precise
- professional
- restrained
- explicit about uncertainty
- faithful to evidence
- clear about limitations

When the report contains many specialist sections, the first screenful should
still let a careful reader identify the strongest bounded takeaway, the primary
blocker, and the next bounded follow-up action.

The report must not be:

- conversational
- theatrical
- promotional
- speculative for effect
- written as advocacy for a preferred conclusion

Allowed patterns include:

- "The evidence supports..."
- "The current session observed..."
- "The result is inconclusive because..."
- "Manual review is required due to..."
- "Within the tested conditions..."
- "No supporting evidence was found for..."

## 4. Forbidden Claims

The report must not exceed the evidence.

Forbidden claim styles include:

- certainty without evidence
- proof claims when only experimental support exists
- broad cryptographic claims derived from narrow tests
- claims of discovery without validation
- claims of safety, insecurity, vulnerability, or anomaly without adequate support
- global generalization from limited conditions
- rhetorical inflation of weak signals

If the evidence does not justify a strong statement, the report must use weaker and more accurate wording.

## 5. Confidence Categories

EllipticZero uses bounded confidence categories for material findings:

- `Confirmed Observation`
  Use for a directly produced and validated observation, not for a broad interpretation built on top of it.
- `Strongly Supported`
  Use when evidence is reproducible, internally consistent, and has survived critique within the tested scope.
- `Provisionally Supported`
  Use when evidence is meaningful but limited by scope, rerun depth, assumption sensitivity, or unresolved alternatives.
- `Inconclusive`
  Use when the session cannot responsibly distinguish between competing explanations.
- `Unsupported`
  Use when the tested evidence does not support the branch under the investigated conditions.
- `Manual Review Required`
  Use when the system cannot safely issue a bounded conclusion without human judgment.

Every confidence category must include a short justification.

## 6. Evidence And Negative Results

The report must clearly separate:

- what was asked
- what was tested
- what was observed
- what was inferred
- what remains unresolved

Negative or null results must be preserved when they materially affect the investigation. The report must not hide:

- failed support for a favored hypothesis
- branches terminated by critique
- contradictory evidence
- unexpected negative controls

## 7. Manual Review And Final Standard

When manual review is required, the report must state:

- why review is needed
- what the system could not resolve
- which branch or finding is affected
- what follow-up would reduce the ambiguity

An EllipticZero report is acceptable only if a careful reader can determine:

- what the original idea was
- how the system formalized it
- what hypotheses were considered
- what local computation was performed
- what evidence was produced
- which findings are supported, unsupported, or unresolved
- how confidence was assigned
- where manual review is required

If the report is persuasive but not traceable, it fails the standard.
