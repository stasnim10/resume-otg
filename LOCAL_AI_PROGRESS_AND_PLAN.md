# Resume Builder OTG
## Local AI Progress and Future Plan

Last updated: April 14, 2026

## Purpose
This document captures what has been implemented so far in Resume Builder OTG, what product and UX decisions shaped the current direction, and what future improvements should come next.

It is meant to serve as a working memory for the project so we do not lose context across iterations.

## Product Direction
The app is evolving from a collection of screens into a guided resume and application workflow with three big goals:

1. Make the experience simple enough for first-time, non-technical users.
2. Add private Local AI powered by Gemma 4 through Ollama.
3. Build a reusable career profile so future applications get faster and better over time.

The current product direction is:

- clear homepage journeys based on user intent
- profile as reusable memory, not just one-time form data
- Local AI as a product feature, not just a raw endpoint configuration
- guarded AI outputs that must validate before they affect export
- review-first workflow so users stay in control

## Major Decisions We Aligned On

### 1. User-friendly first
We agreed that the app should feel usable by a first-time user without technical knowledge. That led to:

- replacing technical language like raw provider and endpoint jargon with plain language
- emphasizing guided flows over advanced controls
- keeping expert options secondary or hidden
- making Local AI setup understandable in normal product language

### 2. Stabilize before scaling
We agreed not to bolt Local AI onto a shaky experience. The implementation path became:

1. stabilize existing upload, extraction, review, and export flow
2. add Local AI setup and task orchestration
3. polish onboarding, profile memory, and evidence-driven drafting

### 3. Profile should be a byproduct, not a burden
We aligned on the idea that users do not want a separate “data entry journey” as a primary task. So the app should:

- build profile memory while users import or create resumes
- save useful background automatically where possible
- still offer a profile dashboard for editing and reuse

### 4. RAG, guardrails, and LangGraph matter
We agreed that Local AI should not be a loose prompt runner. It should be:

- grounded by retrieved evidence
- validated before it writes anything important
- repairable when the model returns malformed outputs
- resilient enough that users see clear fallbacks rather than broken states

## What Has Been Implemented So Far

## A. Local AI foundation

### Local AI provider direction
We added a productized Local AI path built around Ollama and Gemma 4 instead of relying only on a generic custom endpoint path in the main UX.

Current Local AI direction includes:

- Ollama detection
- model readiness checks
- Gemma 4 model selection through shared config defaults
- a dedicated Local AI setup path
- a dedicated Local AI run screen

### Local AI setup behavior
The app now supports a more guided Local AI setup journey with:

- readiness checks
- model presence detection
- setup state stored in session state
- plain-language readiness messaging
- fallback to Standard mode when Local AI is not available

## B. Task-based Local AI workflows

We implemented task-oriented Local AI helpers rather than exposing raw model prompting to the user.

Current Local AI tasks include:

- `process_job_description`
- `extract_or_create_profile`
- `draft_resume_improvements`
- `draft_first_resume`

These are wired through the guarded task layer rather than handled as free-form prompt calls in the UI.

## C. Guardrails and workflow infrastructure

### Guarded workflows
The codebase includes guarded workflow runners for:

- job description processing
- profile extraction
- resume optimization
- first-resume builder generation

These workflows use:

- input validation
- output validation
- repair prompting
- schema enforcement
- retrieval hooks

### LangGraph-oriented workflow structure
The workflow layer is organized in a graph-style way and is compatible with guarded orchestration. Even where execution is sequential, the architecture is already shaped toward structured task orchestration rather than ad hoc prompting.

### JSON parsing and normalization
We improved payload parsing so the app is more resilient to mild schema drift from Local AI responses.

Implemented improvements include:

- tolerant JSON extraction
- support for wrapped outputs like `result`, `data`, and `output`
- normalization for alternate drafting shapes like `optimized_sections` and `action_items`
- hard validation after normalization

## D. RAG / retrieval groundwork

The app already contains retrieval indexing and querying infrastructure for:

- resume chunks
- job description chunks
- profile items
- prior validated optimizations

Current retrieval is used inside guarded workflows to gather supporting evidence before prompting the model.

We also improved the UI so Local AI task cards can now show lightweight evidence previews of what was retrieved and used.

This means the retrieval layer is no longer completely invisible to the user.

## E. Homepage, navigation, and app shell improvements

We revised the app shell toward intent-based navigation.

Implemented changes include:

- cleaner homepage routing
- better returning-user state
- simpler sidebar structure
- stronger distinction between immediate tasks and deeper profile tooling

Current navigation now centers around:

- Home
- Career Profile
- Applications
- History

Additional profile tools remain available through the sidebar for import and manual additions.

## F. Onboarding and profile memory

We implemented onboarding and profile memory foundations, including:

- onboarding session state fields
- profile seeding from prior saved basics
- saving onboarding answers into profile basics
- saving onboarding-derived profile items
- using first-resume builder input as profile-building context

We also added and improved:

- profile welcome screen
- profile import flow
- profile review flow
- profile dashboard
- add profile item flow

Recent routing improvements now make profile setup smarter:

- homepage actions adapt based on whether the user already has enough profile context
- sidebar profile actions route toward setup or dashboard more intentionally

## G. First-resume builder improvements

The builder flow was revised to act as a more practical first-time user intake.

Implemented behavior includes:

- merged “tell us about yourself” intake
- profile seeding into builder fields
- saving builder data back into profile memory
- Local AI builder support through `draft_first_resume`

This reduces the need for users to fill out a separate profile-first workflow before seeing value.

## H. Review flow redesign

The review experience was significantly improved so the end of the workflow tells a story instead of dumping system details.

The review page now follows a clearer structure:

- Before and After
- Why It Improved
- What Changed
- What Needs Attention
- Download or inspect exact changes

Detailed review mode still exists for deeper inspection.

## I. UX and dark mode improvements

We addressed several major UX issues reported during testing:

- frozen-feeling screens during long Local AI actions
- confusing invisible or ghost UI boxes during rerenders
- overlapping landing-card status chips
- duplicate content in review previews
- poor dark-mode readability on several screens
- broken-looking button layout and vertical text issues

Some of these were caused by Streamlit rerender behavior, and we simplified or removed problematic UI elements where needed.

## J. Draft quality protection

We added a quality gate to stop Local AI from quietly making the resume worse.

Current behavior:

- if the optimized overall fit score drops, the draft is rejected
- if keyword alignment drops, the draft is rejected
- the app preserves the safer original state rather than accepting a weaker result

This protects against low-quality AI edits.

## K. Friendlier failure handling

We improved the Local AI error experience so users see clearer guidance instead of raw parser and validation jargon.

Examples of failure types now translated into friendlier language:

- malformed JSON responses
- anchor mismatch issues
- guardrail blocks
- score degradation blocks
- Ollama connection problems

## L. Tests and verification

We verified the recent Local AI and parsing work through:

- Python compile checks
- local pytest coverage for the Local AI related test suite

Latest known status at the time of this note:

- `15 passed` in `resume_optimizer_local/tests_llm`

## Important Files We Touched Heavily

These are some of the main implementation files involved in the work so far:

- `/Users/simumtasnim/App Wizard/Resume Builder OTG/resume_optimizer_local/streamlit_app.py`
- `/Users/simumtasnim/App Wizard/Resume Builder OTG/resume_optimizer_local/local_ai_tasks.py`
- `/Users/simumtasnim/App Wizard/Resume Builder OTG/resume_optimizer_local/json_parser.py`
- `/Users/simumtasnim/App Wizard/Resume Builder OTG/resume_optimizer_local/llm_core/runner.py`
- `/Users/simumtasnim/App Wizard/Resume Builder OTG/resume_optimizer_local/llm_core/schemas.py`
- `/Users/simumtasnim/App Wizard/Resume Builder OTG/resume_optimizer_local/llm_core/workflows/profile_graph.py`
- `/Users/simumtasnim/App Wizard/Resume Builder OTG/resume_optimizer_local/llm_core/workflows/resume_optimization_graph.py`
- `/Users/simumtasnim/App Wizard/Resume Builder OTG/resume_optimizer_local/llm_core/retrieval/indexers.py`
- `/Users/simumtasnim/App Wizard/Resume Builder OTG/resume_optimizer_local/llm_core/retrieval/queries.py`
- `/Users/simumtasnim/App Wizard/Resume Builder OTG/resume_optimizer_local/optimization_history_ui.py`

## What Is Partially Done but Not Fully Finished

These areas have meaningful groundwork but still need a deeper product pass.

### 1. RAG as a true product feature
The retrieval layer exists and is used in workflows, but it is not yet fully productized.

Still needed:

- source browsing inside the UI
- clearer mapping from retrieved evidence to generated output
- better source provenance for profile suggestions and draft changes
- a stronger “why this was used” explanation path

### 2. Profile dashboard polish
The dashboard works, but it still feels more functional than delightful.

Still needed:

- stronger grouping and filtering
- better editing ergonomics
- clearer distinction between active evidence, archived evidence, and imported sources
- richer profile completeness cues

### 3. Onboarding flow consolidation
We have onboarding screens and a builder-led intake, but the product should settle on one obvious first-time path.

Still needed:

- final decision on whether separate onboarding screens remain primary, secondary, or deprecated
- more explicit “why we ask this” guidance during first-time use
- smoother resume/profile generation from onboarding answers

### 4. Local AI progress feedback
This is better than before, but still not perfect.

Still needed:

- clearer non-blocking progress states
- stronger long-running action feedback
- fewer opportunities for awkward Streamlit rerender artifacts

### 5. Dark mode QA
Dark mode is improved, but it still needs a full-screen-by-screen audit.

Still needed:

- visual QA across all routes
- contrast audit on every info, warning, and action state
- typography cleanup in dark mode edge cases

## Recommended Future Improvement Plan

## Phase 1. Finish profile and onboarding product clarity
Goal: make the first-time path feel obvious and friction-light.

Recommended tasks:

- choose one canonical first-time journey for “build my first resume”
- keep profile creation as a helpful byproduct, not a burden
- show profile completeness more clearly on Home and in Career Profile
- improve profile dashboard grouping and editing
- make profile sources easier to review and trust

## Phase 2. Productize RAG
Goal: make evidence grounding visible, useful, and trustworthy.

Recommended tasks:

- show which profile items and sources influenced a draft
- surface retrieved evidence in review and profile screens
- let users inspect why a suggestion was made
- add per-task evidence provenance where practical
- make source quality and freshness more visible

## Phase 3. Strengthen guardrails and repair loops
Goal: make Local AI more reliable under messy real-world inputs.

Recommended tasks:

- add more structured fallback handling across all Local AI tasks
- improve repair prompts for malformed outputs
- add more guardrail-specific tests for bad model behaviors
- log more useful metadata for failed runs
- create clearer in-app fallback recommendations by failure type

## Phase 4. Improve application continuity
Goal: make the app feel like a long-term application workspace, not a one-off tool.

Recommended tasks:

- reopen past application runs cleanly
- compare optimization attempts across history
- connect profile evidence to specific applications
- let users continue from prior drafts without losing context

## Phase 5. Visual and UX polish
Goal: make the experience feel premium and predictable.

Recommended tasks:

- complete dark mode QA
- tighten spacing and typography across all major screens
- reduce visual inconsistency between setup, builder, review, and profile flows
- improve loading and success feedback states
- keep every AI step understandable without exposing too much engineering detail

## Longer-term Vision

If we keep going in this direction, Resume Builder OTG can become:

- a resume optimizer
- a reusable career memory system
- a private Local AI copilot for applications
- a trustworthy, evidence-grounded drafting workflow

That is much stronger than a simple resume tool because it creates compounding value:

- the user imports once
- the profile improves over time
- each application becomes faster
- Local AI gets more context while still staying grounded and validated

## Suggested Next Build Priorities

If we continue from here, the best next build order is:

1. productize RAG visibility in the UI
2. polish the Career Profile dashboard and setup path
3. strengthen Local AI fallback and repair handling
4. improve application history continuity
5. complete full visual QA, especially dark mode

## Quick Status Summary

Current state:

- Local AI foundation: implemented
- Ollama setup flow: implemented
- Gemma 4 integration path: implemented
- Task-based Local AI orchestration: implemented
- Guarded workflows: implemented
- Retrieval groundwork: implemented
- RAG product UX: partial
- Profile dashboard: implemented, needs polish
- Onboarding/profile memory: implemented, needs consolidation
- Review flow redesign: implemented
- Draft quality gate: implemented
- Friendly Local AI failure handling: implemented
- Visual polish and dark mode audit: partial

## Notes
This file should be treated as a living document. As we make more improvements, we should keep updating:

- what changed
- what decisions were made
- what is still incomplete
- what order the next improvements should happen in
