# Resume Builder OTG
## Executive Summary

Last updated: April 14, 2026

## Vision
Resume Builder OTG is evolving from a resume editing tool into a guided application platform with private Local AI, reusable career memory, and a much simpler first-time user experience.

The long-term goal is to help users:

- build or optimize resumes faster
- save their career information once and reuse it across applications
- use Local AI privately on their own device
- get grounded, reviewable AI help instead of black-box outputs

## What We Have Built So Far

### 1. Local AI foundation
We added the first real Local AI path into the app using Gemma 4 through Ollama.

This includes:

- Local AI setup flow
- Ollama readiness detection
- model readiness checks
- Local AI task routing inside the app
- fallback to Standard mode when Local AI is unavailable

### 2. Task-based AI workflows
Instead of exposing raw prompting, the app now supports user-goal-based Local AI tasks:

- job description processing
- profile extraction and creation
- resume improvement drafting
- first-resume draft generation

### 3. Guardrails and validation
We added a guarded workflow layer so Local AI is safer and more reliable.

This means:

- inputs are validated
- outputs must match schema
- malformed outputs can be repaired and retried
- AI-generated content is blocked if it fails validation

### 4. Profile memory foundation
We added the foundation for a reusable career profile so users do not have to start from scratch every time.

This includes:

- profile basics
- imported evidence
- extracted profile items
- editable profile dashboard
- manual add-item flow

### 5. Better homepage and navigation
The app now feels more like a product and less like a collection of tools.

We improved:

- homepage intent-based routing
- sidebar structure
- returning-user state
- profile-focused navigation

### 6. Review flow redesign
The review step now tells a clearer story instead of showing a confusing technical output.

The experience now emphasizes:

- before vs after
- why the draft improved
- what changed
- what still needs attention
- when it is safe to download

### 7. Better Local AI UX
We improved several frustrating parts of the experience:

- friendlier Local AI error messages
- fewer confusing ghost boxes and overlapping UI states
- better long-step messaging
- more stable review behavior
- improved dark-mode progress, though this still needs a full pass

## Why This Matters

These changes shift the product from a resume editor into something more valuable:

- a guided resume workflow
- a reusable career memory system
- a private Local AI assistant for applications
- a safer AI experience with validation and review built in

That creates stronger long-term product value because the app gets smarter as the user continues using it.

## What Is Still In Progress

The biggest things still worth improving are:

### 1. RAG productization
The retrieval layer exists, but it still needs to become a stronger user-facing feature.

We should make it easier for users to understand:

- what evidence was used
- why it was used
- which profile items or sources influenced a draft

### 2. Profile flow polish
The profile dashboard works, but it still needs refinement so it feels more intuitive and premium.

### 3. Onboarding consolidation
We now have strong onboarding ingredients, but we should settle on one obvious first-time path instead of maintaining overlapping flows.

### 4. Guardrail hardening
The guardrails are in place, but we can still improve retries, repair loops, and fallback behavior.

### 5. Visual QA
The app still needs a full visual cleanup pass, especially in dark mode and across edge-case screens.

## Recommended Next Priorities

If we continue building from here, the best next sequence is:

1. make RAG visible and trustworthy in the UI
2. polish the Career Profile dashboard and setup flow
3. harden Local AI fallback and repair behavior
4. improve application history and continuity
5. complete dark mode and visual QA

## Current Overall Status

### Strongly implemented

- Local AI setup foundation
- Gemma 4 integration path
- task-based Local AI execution
- guarded workflow structure
- profile memory foundation
- review flow redesign
- draft quality protection

### Partially complete

- RAG as a visible product feature
- profile polish
- onboarding consolidation
- dark mode and full UX QA
- long-term application continuity

## Bottom Line
Resume Builder OTG now has the foundation of something much bigger than a resume editor.

The product is moving toward a system where:

- the user imports once
- the app builds memory over time
- Local AI helps privately and safely
- every future application becomes faster and more personalized

The remaining work is no longer “build the foundation.”
The remaining work is “turn a strong foundation into a polished, trustworthy product.”
