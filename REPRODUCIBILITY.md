# EllipticZero Reproducibility Policy

## 1. Scope

This document defines the minimum reproducibility requirements for session state, local computation, recorded evidence, and replayable research artifacts. Any result that materially influences a hypothesis decision, validation outcome, or report conclusion must be reproducible; otherwise it cannot be treated as stable evidence.

## 2. Local Computation Requirement

All substantive computation must run locally through approved tools in the Local Compute Layer.

This requirement exists to ensure:

- control over execution environment
- stable provenance for evidence
- repeatability of experiments
- bounded trust assumptions
- independence from opaque remote execution

LLM reasoning may propose what should be tested, but it is not itself a computational authority. Computational claims require locally produced outputs.

## 3. Compute Job Structure

Every ComputeJob must be represented as a structured research artifact with enough information to rerun and interpret it.

Each job must include:

- unique job identity
- linked ResearchSession identity
- linked hypothesis or branch identity
- tool identity
- tool version or equivalent immutable tool descriptor
- purpose statement
- full input specification
- runtime parameters
- execution timestamp
- environment descriptor
- output artifact references
- completion status
- error state when applicable

If a job depends on an external local adapter such as a compiler, static analyzer, or invariant runner, the recorded environment must also preserve the resolved binary path and version actually used for that run.

The purpose statement is mandatory. A job without a clearly stated purpose is an uncontrolled computation and should not run.

## 4. Logging Requirements

EllipticZero must log both reasoning provenance and computational provenance.

### 4.1 Session-Level Logging

The session log must capture:

- original ResearchSeed
- scope interpretation
- agent outputs
- hypothesis state changes
- critique events
- job approvals
- validation outcomes
- report generation events

### 4.2 Compute-Level Logging

Each compute execution must capture:

- exact job identity
- tool identity and version
- resolved inputs
- parameter values
- execution start and end times
- environment metadata needed for reruns
- raw output references
- summary metrics
- warnings, exceptions, and failure conditions

### 4.3 Evidence Logging

Evidence records must capture:

- producing job identity
- derivation chain if transformed from raw outputs
- relevant hypothesis linkage
- interpretation notes when needed
- confidence limitations

Logs must be append-only in spirit. Corrections may be recorded, but prior states must remain traceable.

### 4.4 Bundle Export Logging

When EllipticZero exports a reproducibility bundle, the bundle should preserve:

- the session snapshot
- the execution trace when available
- the run manifest
- the comparative report snapshot when available
- a concise overview file with focus summary, comparison readiness, export-level counts, and quality/hardening summaries
- copied local artifacts when available

Artifact references that resolve outside the approved local storage roots should be filtered from exported manifests and bundles instead of being copied implicitly.

## 5. Rerun Rules

Reruns are required in any situation where evidence affects a meaningful conclusion and stability has not yet been established.

Reruns should be triggered when:

- a result is surprising or unusually strong
- evidence appears inconsistent with prior observations
- a tool version changes
- an environment change may affect computation
- a branch is about to move from inconclusive to supported
- a final report would rely on a single fragile run

Each rerun must state whether it is:

- a strict reproduction run
- a consistency check
- an environment comparison run
- a parameter sensitivity run

If rerun behavior diverges materially from the original run, the result must be downgraded until the divergence is understood.

## 6. Consistency Checks

EllipticZero must apply consistency checks before elevating evidence into findings.

Consistency checks should include, where applicable:

- rerun stability under identical inputs
- agreement between related metrics
- compatibility between mathematical expectations and observed outputs
- absence of unexplained output corruption
- branch-level coherence across supporting evidence
- negative control or null-branch behavior

Consistency is not defined as perfect agreement in all contexts. It is defined as the absence of unexplained contradiction significant enough to undermine the claimed interpretation.

## 7. Confidence Rules

Confidence in EllipticZero is assigned to findings, not to the system as a whole. Confidence must reflect evidence quality, not narrative polish.

Confidence should be determined by:

- reproducibility of the relevant computation
- quality and completeness of evidence
- strength of critique survival
- clarity of mathematical formulation
- number and seriousness of unresolved contradictions
- sensitivity to assumptions or environment changes

Confidence must be reduced when:

- results depend on a single run
- assumptions are poorly constrained
- output interpretation is indirect
- competing explanations remain viable
- rerun behavior is unstable
- manual review conditions are present

The system must never assign high confidence solely because multiple agents appear to agree.

## 8. Manual Review Conditions

Manual review is required whenever the system cannot responsibly close the epistemic gap on its own.

Manual review must be triggered when:

- evidence is incomplete but conclusions would matter materially
- results are contradictory and the source of contradiction is unresolved
- a hypothesis depends on ambiguous or underdefined mathematics
- computation behaves unexpectedly without a satisfactory explanation
- a tool error may have affected interpretation
- confidence cannot be assigned cleanly
- the report would otherwise require speculative language to appear complete

When manual review is triggered, the report must say so explicitly and identify the reason.

## 9. Negative and Inconclusive Results

Reproducibility policy applies equally to null, negative, and inconclusive outcomes.

The system must preserve:

- failed attempts
- unsupported hypotheses
- contradictory runs
- incomplete evidence chains
- branches terminated for methodological reasons

Research integrity requires showing where the system did not find support, not only where it did.

## 10. Versioning and Traceability

The research record must support comparison across time.

Changes that affect interpretation should be traceable, including:

- tool version changes
- environment changes
- hypothesis reformulations
- report revisions
- evidence reinterpretations

The system should be able to answer the following questions for any meaningful claim:

- Which session produced it?
- Which hypothesis branch did it belong to?
- Which compute jobs informed it?
- Which evidence artifacts supported it?
- Which critiques survived into the final interpretation?
- Under what environment and assumptions was it produced?

If these questions cannot be answered, the claim is not sufficiently traceable.

## 11. Failure and Recovery Rules

A failed job is not silent noise. It is a research event.

When jobs fail, the system must record:

- what was attempted
- what failed
- whether the failure affects any downstream interpretation
- whether rerun is required
- whether manual review is required

Recovery actions should not overwrite the evidentiary meaning of the original failure. If a rerun succeeds later, both events remain part of the session history.
