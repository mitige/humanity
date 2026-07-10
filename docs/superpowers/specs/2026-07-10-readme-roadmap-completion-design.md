# README Roadmap Completion Design

## Goal

Replace the README's now-misleading final **Future extensions** section with a completion-oriented
checklist that makes the delivered Phase 7 scope explicit and keeps every claim tied to implemented,
tested behavior.

## Current problem

The final checklist already marks its entries as delivered, but its title still presents them as
future work. It also distributes the eight Horizon mechanisms across broader historical bullets, so
a reader cannot verify the complete Phase 7 delivery at a glance.

## Chosen structure

Rename the section to **Roadmap completed** and organize it into three compact groups:

1. **Foundations delivered — Phases 1–6**: society, deep mechanisms, learning/personality,
   scientific instrument, asymptote mechanisms, language, and the optional LLM peripheral.
2. **Phase 7 — The Horizon delivered**: one checked item for each of causal Phi, hierarchy/VFE,
   multi-step EFE planning, semantic vector memory, contextual TD(lambda), mind-wandering, living
   world dynamics, and structured tasks.
3. **Delivery quality completed**: Horizon observability/interventions, trace analysis, atomic
   persistence/checkpoints, responsive concurrency, accessible interaction, hermetic tests, locked
   dependencies, and the verified 627-test result.

The closing paragraph remains an explicit scientific boundary: completed engineering objectives do
not establish phenomenal consciousness, and full IIT 3.0/4.0 micro-substrate analysis remains out of
scope.

## Content rules

- Every item uses a checked marker and past/present-complete wording.
- Avoid duplicating the detailed Phase 7 chapter; link to it instead.
- Mention only public surfaces and guarantees present in the current code and tests.
- Preserve the project's level-2 honesty language.
- Do not change application behavior, configuration, dependencies, or test code.

## Acceptance criteria

- The README no longer contains the heading `## Future extensions`.
- The final roadmap names all eight Phase 7 mechanisms individually.
- The final roadmap includes the Observatoire, interventions, exports, checkpoint/persistence
  hardening, concurrency safety, accessibility, reproducibility, and `627/627` tests.
- Existing README contract tests remain green.
- The documentation diff passes `git diff --check` and is added to the existing Phase 7 pull request.
