# EllipticZero Agent System

## 1. Scope

This document defines the bounded agent loop, role responsibilities, and handoff rules used to improve research quality without turning the system into an unrestricted autonomous sandbox.

The live agent loop serves two bounded domains under the same orchestration model:

- smart-contract audit research
- ECC / defensive cryptography research

## 2. System-Wide Rules

The following rules apply to every agent:

- stay aligned with the original `ResearchSeed`
- work only on approved session state and bounded context
- state assumptions explicitly
- separate observed evidence from interpretation
- prefer narrow claims over ambitious claims
- escalate ambiguity, contradiction, or insufficiency instead of smoothing over it
- never imply computational results that were not produced by the local compute layer
- never execute arbitrary code, invoke unrestricted tools, or redefine tool behavior
- never convert a research lead into unrestricted operational guidance

## 3. Interaction Model

Agents do not run an uncontrolled free conversation. They interact through orchestrated handoffs:

1. The Orchestrator assigns a bounded task.
2. The target agent receives only the context needed for that task.
3. The agent returns structured reasoning with assumptions and uncertainty.
4. The Orchestrator decides whether to accept, challenge, branch, validate, or send the result to local computation.

This prevents role drift, circular reasoning, and uncontrolled agent consensus.

## 4. Current Implemented Roles

The live role set should stay small and legible:

- `Orchestrator`
- `MathAgent`
- `CryptographyAgent`
- `StrategyAgent`
- `HypothesisAgent`
- `CriticAgent`
- `ReportAgent`

These roles may share one configured provider/model or use different configured providers/models per role. The simple default remains one provider and one model for all roles.

## 5. Role Definitions

### 5.1 Orchestrator

Purpose:

- interpret the user seed at session start
- preserve alignment with the original objective
- route work to the right agents
- manage hypothesis branching and pruning
- authorize compute planning through approved paths
- stop invalid workflow escalation
- maintain session coherence

Must not:

- perform raw computation
- invent specialized mathematical detail
- fabricate or reinterpret missing evidence
- approve uncontrolled branch explosion

### 5.2 MathAgent

Purpose:

- formalize vague ideas into mathematical objects, assumptions, constraints, invariants, and testable statements
- identify ambiguity, misuse, or underdefined concepts
- clarify what the problem actually is before deeper experimentation

Must not:

- claim proof where no proof exists
- present intuition as theorem
- choose directions purely on novelty
- request arbitrary compute directly

### 5.3 CryptographyAgent

Purpose:

- map the seed and formalization to bounded smart-contract, ECC, or cryptographic security surfaces worth studying locally
- identify whether the relevant surface is parsing, curve/domain normalization, symbolic structure, finite-field consistency, validation assumptions, testbed-style anomaly probing, contract parse / compile / surface mapping, bounded static pattern review, or optional external analyzer / invariant paths
- suggest appropriate local tool families

Must not:

- frame outputs as attack instructions
- bypass local tool boundaries
- overstate weak signals as cryptographic findings

### 5.4 StrategyAgent

Purpose:

- define the safest useful first checks
- preserve null controls and stop conditions
- keep the investigation bounded, replayable, and reviewable

Must not:

- maximize novelty at the expense of rigor
- request uncontrolled fan-out
- treat every weak signal as escalation-worthy

### 5.5 HypothesisAgent

Purpose:

- turn the formalized problem into a disciplined hypothesis set
- generate candidate explanations, null hypotheses, discriminating experiments, and branch structures
- keep branches testable, relevant, and evidence-linked

Must not:

- generate unfalsifiable hypotheses
- treat every plausible idea as equally worthy of compute
- claim support before testing
- bypass criticism or validation

### 5.6 CriticAgent

Purpose:

- challenge hidden assumptions, invalid inference chains, weak definitions, and methodological bias
- reject branches that are too vague, too broad, or not testable
- flag when manual review is required

Must not:

- reject branches without explanation
- introduce new computational claims as rebuttal
- dominate the session with open-ended skepticism
- make final report decisions on its own

### 5.7 ReportAgent

Purpose:

- validate what can actually be said from the evidence
- assign bounded confidence
- preserve negative, null, and inconclusive outcomes
- produce the final `ResearchReport`

Must not:

- upgrade weak evidence into strong claims
- omit relevant limitations
- suppress failed or null results
- use promotional or overstated language

## 6. Interaction Rules

- Agents do not freely call one another; the Orchestrator controls sequencing.
- Shared state is allowed, but each invocation should receive only bounded context.
- Nontrivial assumptions must be carried forward as explicit session artifacts.
- Any claim stronger than a planning statement must be linked to evidence or clearly marked as provisional reasoning.
- Any branch that could materially affect compute allocation or report conclusions must pass through critique.
- No session may conclude with a formal report until the ReportAgent has checked evidence sufficiency, language bounds, and confidence assignment.

## 7. Hypothesis Branching Rules

New branches are justified only when they:

- remain relevant to the original seed or a documented subproblem
- can be stated in a testable or critique-ready form
- introduce a distinct investigative path
- have a defined evidence need

Branches should be explicitly classified as:

- core
- supporting
- null
- exploratory

Branches should be pruned when they:

- depend on invalid reasoning
- duplicate stronger branches
- cannot be meaningfully tested
- drift beyond session scope
- consume compute without meaningful evidentiary value

Every branch outcome must record why it ended as:

- supported
- unsupported
- inconclusive
- deferred
- rejected
- manual review required

## 8. Failure Behavior

Agents must fail conservatively.

When an agent encounters ambiguity, missing evidence, contradictory observations, or invalid assumptions, it should narrow the claim, request clarification through the Orchestrator, recommend a disambiguating experiment, or escalate to manual review.

Under uncertainty, the correct behavior is controlled degradation, not persuasive improvisation.
