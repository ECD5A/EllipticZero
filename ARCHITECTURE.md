# EllipticZero Architecture

## 1. Scope

This document defines the internal structure, operating priorities, and bounded research pipeline used to turn a free-form research idea into a controlled local investigation with recorded evidence and a cautious report.

The current architecture covers two bounded research domains through the same orchestrator and sandbox model:

- smart-contract audit research
- ECC / defensive cryptography research

EllipticZero is governed by the following operating priorities:

- Preserve alignment with the user's original research seed.
- Separate reasoning from computation.
- Keep substantive experimentation sandboxed, reversible, and locally auditable.
- Prefer explicit uncertainty over unsupported certainty.
- Treat evidence as mandatory for all substantive conclusions.
- Keep every investigation reproducible, reviewable, and extensible.

The system does not exist to generate speculative claims, to improvise computational behavior, or to present unverified results as findings.

## 2. Operating Principles

- Free-form input only. Users are not required to fit their idea into a rigid template.
- Agents reason, critique, and plan. They do not perform unrestricted computation.
- All heavy computation is local and controlled.
- Exploratory research is allowed only through bounded local tools, runners, or equivalent controlled sandboxes.
- Agent roles may be routed to different configured providers and models, but that routing remains declarative and orchestrator-governed.
- Tool access is mediated through a registry, not direct agent execution.
- All meaningful outputs must be grounded in recorded evidence.
- Manual review is preferred whenever evidence is weak, contradictory, or incomplete.
- The architecture must remain modular so additional agents, tools, and domains can be introduced without destabilizing the system.

## 3. End-to-End Research Pipeline

The EllipticZero pipeline is a constrained research workflow:

1. User Idea Submission  
   A user provides a free-form research seed describing an intuition, suspected anomaly, implementation concern, mathematical question, or exploratory hypothesis.

2. Seed Interpretation  
   The Orchestrator converts the raw seed into a bounded research session, extracts scope, identifies ambiguity, and defines the initial investigation frame.

3. Mathematical Formalization  
   The Math Agent converts informal statements into mathematical objects, assumptions, invariants, constraints, and testable formulations.

4. Smart-Contract / Cryptographic Surface Profiling
   The Cryptography Agent maps the seed and formalization to bounded smart-contract audit, ECC, or cryptographic surfaces, preferred local tool families, and defensive research questions.

5. Strategy Shaping  
   The Strategy Agent defines conservative local checks, null controls, and stop conditions so the investigation stays bounded and evidence-first.

6. Hypothesis Construction  
   The Hypothesis Agent expands the formalized problem into candidate hypotheses, experimental directions, null hypotheses, and expected observations.

7. Critical Review  
   The Critic Agent challenges unsupported jumps, ambiguous definitions, invalid inference chains, and directions that are not testable or not aligned with the seed.

8. Compute Planning  
   The Orchestrator selects approved tasks and converts them into controlled compute jobs through the Tool Registry.

9. Local Computation  
   The Local Compute Layer executes approved jobs on local resources using predefined tools and recorded parameters.

10. Evidence Collection  
   Outputs from computation are stored as evidence artifacts linked to the originating hypotheses, jobs, assumptions, and session state.

11. Validation  
   The Validation / Report Agent checks whether the evidence is internally consistent, sufficient for any stated conclusion, and appropriately bounded in confidence.

12. Report Production  
   The system produces a structured research report that distinguishes confirmed observations, partial support, negative results, unresolved questions, and items requiring manual review.

## 4. System Layers

EllipticZero is organized into explicit layers to prevent architectural drift and uncontrolled behavior.

### 4.1 Interface Layer

This layer receives the free-form research seed and session-level directives. Its responsibility is capture, not interpretation. It must preserve the original language of the user input so downstream outputs can remain traceable to the original intent.

### 4.2 Orchestration Layer

This layer governs workflow progression, state transitions, routing between agents, hypothesis lifecycle management, and compute authorization. It is the control center for alignment, discipline, and bounded execution.

### 4.3 Reasoning Layer

This layer contains the research agents. Agents interpret, formalize, critique, and assess. They operate on text, structured state, and evidence summaries. They do not run arbitrary code or bypass the tooling boundaries.

### 4.4 Tool Registry Layer

This layer is the single approved interface between reasoning and computation. It exposes only named, reviewed, parameterized tools. Each tool must declare its purpose, inputs, output contract, and operational constraints.

### 4.5 Local Compute Layer

This layer performs deterministic or controlled local computation. It is responsible for actual mathematical evaluation, implementation checks, anomaly scans, sampling procedures, bounded smart-contract parsing/compile/surface/pattern checks, repo-scale contract inventory and import/dependency scoping, entrypoint and risk-family review lane extraction, bounded repo-casebook comparisons for repository-style contract review, optional external static or invariant adapters, and other experimental work that cannot be delegated to LLM reasoning.

### 4.6 Evidence Layer

This layer stores compute outputs, derivations, observations, metadata, and provenance links. Evidence must be attributable to exact jobs, inputs, tools, and session context.

### 4.7 Validation and Reporting Layer

This layer converts evidence into bounded conclusions. It ensures that the final report reflects what the system actually observed, not what an agent expected to observe.

## 5. LLM Separation and Compute Discipline

EllipticZero enforces a strict separation between reasoning and execution.

LLM-based agents are responsible for:

- interpreting the research seed
- formalizing concepts
- proposing and pruning hypotheses
- identifying flaws or ambiguity
- planning evidence needs
- synthesizing findings into a report

LLM-based agents are not responsible for:

- executing arbitrary programs
- invoking shell commands directly
- editing tool behavior during a session
- claiming computational results that were not produced locally
- substituting intuition for measured evidence

The Local Compute Layer is responsible for:

- running approved computational tasks
- recording exact parameters and environment details
- returning raw outputs and summary metrics
- supporting reruns and consistency checks

This separation exists to keep the system auditable. The reasoning layer may decide what should be tested. It may not fabricate the outcome of a test.

## 6. Local Compute Reasoning

EllipticZero treats local computation as the source of empirical evidence within the research workflow.

The rationale is as follows:

- Mathematical and cryptographic claims often require evaluation beyond natural-language reasoning.
- Reproducibility requires control over tools, inputs, and environment.
- Security-sensitive or research-sensitive investigations should not depend on opaque remote execution.
- Experimental hypotheses must be testable under a disciplined runtime boundary.

Local computation in EllipticZero is therefore not an implementation detail. It is a core epistemic boundary. If a conclusion depends on computation, that computation must be locally executable, logged, and rerunnable.

## 7. Core Entities

EllipticZero is built around a small set of explicit domain entities.

### 7.1 ResearchSeed

The original free-form user idea, preserved with minimal normalization. It is the source anchor for all subsequent reasoning.

Core purpose:

- capture the exact initiating intent
- preserve wording and context
- provide the alignment reference for the entire session

### 7.2 Hypothesis

A candidate claim, question, or testable direction derived from the seed and formalization process.

Core purpose:

- express a bounded proposition or investigative direction
- define assumptions and expected evidence
- support branching, criticism, acceptance, rejection, or deferral

### 7.3 ComputeJob

A controlled request for local computation issued through the Tool Registry.

Core purpose:

- define the exact task to run
- bind inputs, parameters, and tool identity
- produce traceable outputs for evidence evaluation

### 7.4 Evidence

Any recorded artifact that informs validation, including raw outputs, derived metrics, anomaly observations, error states, and comparison results.

Core purpose:

- support or weaken hypotheses
- document what was actually observed
- preserve provenance and reproducibility

### 7.5 ResearchReport

The structured written outcome of a session.

Core purpose:

- summarize scope, process, findings, limitations, and confidence
- distinguish confirmed observations from open questions
- communicate what requires manual review

### 7.6 ResearchSession

The top-level container for a single investigation lifecycle.

Core purpose:

- link one seed to all downstream state
- track agent outputs, hypotheses, compute jobs, evidence, and report versions
- preserve chronology, provenance, and reproducibility boundaries

## 8. Research Session Concept

A ResearchSession is the governing unit of work in EllipticZero. It exists to prevent fragmented reasoning and to keep all artifacts tied to a single investigative thread.

Each session should capture:

- the original research seed
- the interpreted scope and constraints
- agent reasoning outputs
- the hypothesis graph
- approved compute jobs
- produced evidence artifacts
- validation outcomes
- the final report and any revisions

The session model serves four purposes:

- alignment: it keeps every downstream action anchored to the original idea
- traceability: it records how conclusions were reached
- reproducibility: it enables reruns under the same or updated conditions
- containment: it prevents unrelated exploratory branches from contaminating one another

Sessions may contain multiple branches, but every branch must remain attributable to the same originating seed unless an explicit new session is created.

## 9. Hypothesis Lifecycle

Hypotheses are not treated as informal suggestions. They are managed objects with explicit states.

Typical lifecycle states include:

- proposed
- formalized
- challenged
- approved for testing
- tested
- supported
- unsupported
- inconclusive
- deferred
- rejected

Transitions between these states must be justified by reasoning or evidence. A hypothesis cannot move to supported status through rhetorical confidence alone.

## 10. Modularity and Extension Model

EllipticZero must support future growth without weakening control boundaries.

The architecture is intentionally modular in the following dimensions:

- new agents may be added if they have a clearly bounded role
- new tools may be added through the registry if they declare strict contracts
- new evidence types may be introduced if they preserve provenance
- new report sections may be introduced if they do not blur confidence boundaries
- new domains of elliptic-curve research may be supported if they reuse the same session, hypothesis, and evidence discipline

Extension must not break three invariants:

- agents remain separate from direct execution
- evidence remains necessary for substantive claims
- reports remain traceable to seed, hypothesis, and compute provenance

## 11. Alignment and Anti-Chaos Measures

EllipticZero is explicitly designed to prevent research chaos. The architecture enforces this through:

- a single orchestrated session lifecycle
- role-bounded agents
- a registry-mediated tool boundary
- formal hypothesis management
- explicit validation before reporting
- confidence categories tied to evidence quality
- mandatory manual review when certainty is not justified

The system should fail conservatively. When ambiguity, contradiction, or insufficient evidence is present, EllipticZero should narrow claims, downgrade confidence, or halt with a manual review requirement rather than manufacture closure.
