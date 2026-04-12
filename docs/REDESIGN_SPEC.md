# Resume Optimizer: Complete Redesign Specification

**Version:** 1.0  
**Date:** 2026-04-12  
**Status:** Ready for Implementation  
**Scope:** UX/Flow redesign for repeated-use optimization model

---

## 1. Overview & Design Principles

### Problem Statement
Current flow has **7-12 screens** with high cognitive load, unclear value proposition, and manual mode as equal option. Users drop off because they don't understand:
- Whether optimization is worth their time
- What changes will be made
- How this helps them get the job

### Solution Vision
- **Streamlined flow:** 4-5 screens for first optimization
- **Match % transparency:** Show user "65% match → 78% match" BEFORE asking them to download
- **Manual mode as funnel, not equal path:** Make API mode obvious default
- **Profile integration:** Build after first success, pre-filled with first resume data
- **Repeated use ready:** Dashboard shows past optimizations, enables quick re-use

### Design Principles
1. **Show value before asking for work** — Display match % before optimization, so user knows if 5 minutes is worth it
2. **One flow for 95% of users** — Manual mode available but not highlighted; API is the obvious path
3. **Progressive disclosure** — Don't show all options; guide users through one clear journey
4. **Repeated-use first mentality** — Treat each screen as "how will this feel on job #3?"
5. **Match % is the north star metric** — All messaging aligned to "how well does your resume match this job?"

---

## 2. User Personas & Journeys

### Primary Persona: Alex (Recent Grad)
- **Goal:** Get hired for first PM role
- **Motivation:** Anxious about resume quality; wants a guarantee it matches job requirements
- **Pain point:** Doesn't know if my resume is good enough
- **First optimization:** eBay PM role (65% match) → uses app → 78% match → downloads → applies

### Secondary Persona: Jordan (Career Pivot)
- **Goal:** Switch to tech after 10 years in finance
- **Motivation:** Resume has transferable skills but not framed for tech
- **Pain point:** Doesn't know how to translate my background
- **First optimization:** Google Data Analyst role (52% match) → uses app → 71% match → considers if worth it → downloads

### Tertiary Persona: Sam (Unemployed, Repeat User)
- **Goal:** Optimize resume for 5+ jobs over 2 months
- **Motivation:** Maximize chances across multiple roles
- **Pain point:** Don't want to upload resume every single time
- **Journey:** Job 1 → Build profile → Job 2 (re-use profile) → Job 3 (re-use profile)

---

## 3. Complete Flow Redesign

### FLOW A: First-Time User (No Profile)

#### **Screen 1: Landing Page (Simplified)**
**Status:** Already done (Option C implementation)

**What's shown:**
- Hero headline: "Make resume tailoring feel beautifully simple."
- Two primary buttons:
  - "Start Optimizing" (existing resume)
  - "Build your first resume" (from scratch)
- Sidebar menu with "Career Profile" (not visible on landing, only in sidebar)

**User action:** Click "Start Optimizing"

**Copy notes:**
- Keep current copy; it's good
- No "Build Career Profile" button here (moved to flow-end)

---

#### **Screen 2: Upload & Job Description (REDESIGNED)**

**Current problems:**
- Random loaded URL shown
- Job description defaults to long pasted text
- No clarity on which input method to use
- "Process Job Description" button unclear

**Wireframe:**
```
┌─────────────────────────────────────────────────┐
│ STEP 1 OF 4: Upload & Target                    │
├─────────────────────────────────────────────────┤
│                                                   │
│ Bring in your resume. Point it at the role.    │
│                                                   │
│ ┌──────────────────┐  ┌──────────────────┐     │
│ │ UPLOAD RESUME    │  │ PASTE JOB DESC   │     │
│ │                  │  │                  │     │
│ │ .docx file       │  │ Full job posting │     │
│ │ Drag & drop      │  │ or LinkedIn URL  │     │
│ │                  │  │                  │     │
│ │ [S: Choose File] │  │ [S: Paste here] │     │
│ │ filename.docx ✓  │  │ [S: Process]    │     │
│ │                  │  │                  │     │
│ └──────────────────┘  └──────────────────┘     │
│                                                   │
│ ┌──────────────────────────────────────────┐   │
│ │ [S: Back]         [Primary: Continue]    │   │
│ └──────────────────────────────────────────┘   │
│                                                   │
└─────────────────────────────────────────────────┘
```

**Key changes:**
1. **No default URL shown** — User inputs resume + JD fresh
2. **Job description input is clean** — Empty text area with placeholder
3. **"Process Job Description" renamed to "Continue"** — Clearer action
4. **Two-column layout remains** — Resume on left, JD on right
5. **Status indicator** — "STEP 1 OF 4" tells user what to expect

**Copy:**

**Headline:** "Bring in your resume. Point it at the role."

**Left section (Resume):**
- Kicker: "Your Resume"
- Instruction: "Upload a .docx file. We'll preserve the formatting while optimizing the content."
- Button: "Choose File"
- Status: "filename.docx ready to optimize ✓"

**Right section (Job Description):**
- Kicker: "Target Role"
- Instruction: "Paste the full job posting or LinkedIn URL. We'll extract the signals that matter."
- Textarea placeholder: "Paste job description here... or paste LinkedIn job URL"
- Button: "Process Job Description"

**Logic:**
- User uploads .docx resume
- User pastes JD or URL
- Click "Continue" → App processes JD in background → moves to Screen 3
- If JD has errors → Show inline error "We couldn't parse this JD. Try pasting the full job posting." → Stay on screen

**Implementation notes:**
- Validate resume is .docx (existing)
- Validate JD has at least 50 words (new)
- Show inline success states (✓ ready)
- No progress spinner; just "Continue" button

---

#### **Screen 3: Pre-Optimization Match Score (NEW SCREEN)**

**Current problem:** Users don't know if optimization is worth their time

**Wireframe:**
```
┌──────────────────────────────────────────────┐
│ STEP 2 OF 4: Assess Your Match              │
├──────────────────────────────────────────────┤
│                                               │
│ Program Manager, Worldwide Logistics Ops    │
│ @ Apple                                      │
│                                               │
│                    ┌─────────────┐            │
│                    │     65%     │            │
│                    │ FAIR MATCH  │            │
│                    └─────────────┘            │
│                                               │
│ Your resume aligns with 65% of this role's   │
│ core requirements. We can improve this.      │
│                                               │
│ Key signals we found:                        │
│ ✓ Supply Chain Management (strong)           │
│ ✓ Cross-functional Leadership (strong)       │
│ ✗ Advanced Analytics (missing)               │
│ ✗ Tableau (missing)                          │
│                                               │
│ Ready? We'll optimize for these gaps.        │
│                                               │
│ ┌──────────────────────────────────────┐     │
│ │ [Secondary: Back] [Primary: Optimize]│     │
│ └──────────────────────────────────────┘     │
│                                               │
└──────────────────────────────────────────────┘
```

**Key features:**
1. **Match % circle (large, prominent)** — Visual, immediate, understandable
2. **Match band label** — "Fair Match" tells user what 65% means
3. **Key signals breakdown** — What's strong, what's missing
4. **Expectation setting** — "We can improve this" primes user for next step
5. **Two buttons** — Back or Optimize (no other distractions)

**Copy:**

**Headline:** "Assess Your Match"

**Subheading:** "Program Manager, Worldwide Logistics Ops @ Apple"

**Match display:**
- Circular progress indicator: "65%"
- Band label: "FAIR MATCH"
- Supporting text: "Your resume aligns with 65% of this role's core requirements. We can improve this."

**Signals section:**
- Kicker: "Key Signals (based on job description)"
- List format:
  - `✓ Supply Chain Management (strong match)`
  - `✓ Cross-functional Leadership (strong match)`
  - `✗ Advanced Analytics (not mentioned in your resume)`
  - `✗ Tableau (not mentioned in your resume)`

**CTA:** "Ready? We'll optimize your resume to match these requirements better."

**Buttons:**
- Secondary: "Back to Upload"
- Primary: "Optimize Now"

**Logic:**
- Calculate match % based on:
  - Keyword overlap between resume and JD
  - Verb strength (action verbs present)
  - ATS score
  - Overall fit assessment
- Extract 4-6 key signals (2-3 strengths, 2-3 gaps)
- Show only if match is between 20-90% (if <20%, warn user; if >90%, show confidence)
- User can go back or proceed

**Implementation notes:**
- Match % = (keyword_alignment + verb_strength + ats_score) / 3
- Only show signals, not raw scores
- Use visual indicators (✓/✗) not percentages
- Pre-cache this while processing the JD on Screen 2

---

#### **Screen 4: Execution Mode Selection (REDESIGNED)**

**Current problems:**
- Manual mode feels equal to Automatic
- Vague descriptions
- Three options confusing
- Advanced option is noise for first-timers

**Wireframe:**
```
┌──────────────────────────────────────────────┐
│ STEP 3 OF 4: Choose Your Path               │
├──────────────────────────────────────────────┤
│                                               │
│ How hands-on do you want to be?             │
│                                               │
│ ┌────────────────────────────────────────┐   │
│ │ 🚀 LET THE APP RUN IT (Recommended)    │   │
│ │                                        │   │
│ │ We'll optimize your resume and have   │   │
│ │ the results ready in 30 seconds.      │   │
│ │ No copy-paste needed.                 │   │
│ │                                        │   │
│ │         [Primary: Use API Mode]       │   │
│ └────────────────────────────────────────┘   │
│                                               │
│ ─────────────────────────────────────────    │
│ OR                                            │
│ ─────────────────────────────────────────    │
│                                               │
│ ┌────────────────────────────────────────┐   │
│ │ ✏️ MANUAL: I WANT CONTROL              │   │
│ │                                        │   │
│ │ Copy the prompt, paste into ChatGPT,  │   │
│ │ and bring back the result. Best if    │   │
│ │ you want to compare outputs or use    │   │
│ │ your own API key.                     │   │
│ │                                        │   │
│ │       [Secondary: Use Manual Mode]    │   │
│ └────────────────────────────────────────┘   │
│                                               │
│ ┌──────────────────────────────────────┐     │
│ │ [Tertiary: Back]                     │     │
│ └──────────────────────────────────────┘     │
│                                               │
└──────────────────────────────────────────────┘
```

**Key changes:**
1. **API mode is obvious default** — Highlighted as "Recommended", larger, prominent button
2. **Manual mode is secondary** — Still available, but not equal
3. **Removed "Advanced" option** — Too confusing for first-timers, hide in settings
4. **Clearer descriptions:**
   - API: "30 seconds, no copy-paste"
   - Manual: "You want control or use your own API key"
5. **Removed "Every option uses same prompt logic"** — Noise; users don't care

**Copy:**

**Headline:** "Choose Your Path"

**Subheading:** "How hands-on do you want to be?"

**Option 1 (Primary):**
- Badge: "🚀 Recommended"
- Title: "Let the app run it"
- Description: "We'll optimize your resume and have the results ready in 30 seconds. No copy-paste needed."
- Button: "Use API Mode → "

**Option 2 (Secondary):**
- Title: "✏️ I want control"
- Description: "Copy the prompt, paste into ChatGPT/Claude, and bring back the result. Best if you want to compare outputs or use your own API key."
- Button: "Use Manual Mode →"

**Footnote (below both):**
"Note: Both paths use the same optimization logic. Choose based on your preference."

**Logic:**
- User selects mode → proceeds accordingly
- API Mode → Screen 5 (Results) after prompt runs
- Manual Mode → Screen 4b (Manual copy-paste workflow)

**Implementation notes:**
- Default selection should be API Mode
- Manual Mode flows to existing manual screen
- No "Advanced" for now; hide in Settings for power users
- Show loading spinner for API mode with message: "Optimizing your resume... (this usually takes 20-30 seconds)"

---

#### **Screen 4b: Manual Mode Workflow (KEEP EXISTING)**

**Note:** Don't change this; it already exists. Just ensure it clearly states:
- "This is a more hands-on path"
- "You control the prompts and outputs"
- "Once comfortable, try API mode for faster results"

**Funnel copy addition:** After user completes Manual mode successfully:
**"Great! Got a result? Next time, try API mode to skip the copy-paste."**

---

#### **Screen 5: Results & Before/After (REDESIGNED)**

**Current problems:**
- "Optimization complete" but there's more work
- Before/After previews unavailable
- Metrics hard to understand (75→76)
- Profile prompt feels tacked on
- No clear next action

**Wireframe:**
```
┌─────────────────────────────────────────────┐
│ STEP 4 OF 4: Review & Export               │
├─────────────────────────────────────────────┤
│                                               │
│ Program Manager, Worldwide Logistics Ops   │
│ @ Apple                                     │
│                                               │
│           BEFORE      AFTER    CHANGE       │
│          ┌─────┐    ┌─────┐   ┌─────┐      │
│          │ 65% │ →  │ 78% │   │+13% │      │
│          │FAIR │    │STRONG│  │ ✓   │      │
│          └─────┘    └─────┘   └─────┘      │
│                                               │
│   ✨ 3 Key Improvements Found               │
│   [Expand to see what changed ▼]           │
│                                               │
│   When expanded:                             │
│   ─────────────────────────────────────     │
│   Added stronger action verb:               │
│   ✗ "Managed supply chain operations"      │
│   ✓ "Led supply chain operations strategy" │
│   Why: You manage, but role needs leader   │
│                                               │
│   Added impact metric:                      │
│   ✗ "Coordinated shipments"                │
│   ✓ "Coordinated 500+ monthly shipments"   │
│   Why: Quantified impact is stronger       │
│                                               │
│   Added missing keyword:                    │
│   ✗ (no mention of Tableau)                │
│   ✓ "Tableau dashboards for analytics"     │
│   Why: Job description mentions Tableau    │
│   ─────────────────────────────────────    │
│                                               │
│ You're ready to apply! Download below.     │
│                                               │
│ ┌──────────────────────────────────────┐   │
│ │ [Primary: Download .docx]            │   │
│ │ [Secondary: Review All Changes]      │   │
│ │ [Tertiary: Try Another Job]          │   │
│ └──────────────────────────────────────┘   │
│                                               │
│ ╔══════════════════════════════════════╗   │
│ ║ 💡 WORKING TOWARDS YOUR NEXT STEP?  ║   │
│ ║                                      ║   │
│ ║ Build your profile so you don't      ║   │
│ ║ upload a resume next time. We'll     ║   │
│ ║ pre-fill it with your experience.   ║   │
│ ║                                      ║   │
│ ║ [Button: Build Profile] [Skip]      ║   │
│ ╚══════════════════════════════════════╝   │
│                                               │
└─────────────────────────────────────────────┘
```

**Key changes:**
1. **Match % is the hero** — Large, visual, before/after, with change indicator
2. **Concrete improvements** — Dropdown shows real before/after examples
3. **"Why" context** — Explains why each change was made
4. **Only show improvements ≥ threshold** — Don't show trivial changes
5. **Clear CTAs:**
   - Primary: Download (immediate action)
   - Secondary: Review all changes (if they want details)
   - Tertiary: Try another job (funnel to repeated use)
6. **Profile prompt is contextual** — After success, asking to build profile makes sense

**Copy:**

**Headline:** "Your resume is optimized and ready."

**Match display:**
```
BEFORE      AFTER     CHANGE
  65%         78%       +13%
FAIR MATCH  STRONG    ↑ Significant
            MATCH      improvement
```

**Improvements section:**
- Kicker: "✨ 3 Key Improvements Found"
- Call-to-action: "Expand to see what changed ▼"
- When expanded, show 3-5 concrete examples

**Example format:**
```
✓ Added stronger action verb
  Before: "Managed supply chain operations"
  After: "Led supply chain operations strategy"
  Why: This role needs demonstrated leadership. "Led" signals you drive strategy, not just execute plans.

✓ Added quantified impact
  Before: "Coordinated shipments"
  After: "Coordinated 500+ monthly shipments"
  Why: Numbers make impact tangible and memorable to ATS and recruiters.

✓ Added missing keyword
  Before: (not mentioned)
  After: "Tableau dashboards for analytics"
  Why: The job mentions "Tableau" twice. Your resume didn't. This addition increases keyword match.
```

**Decision point:**
- Headline: "Ready to apply?"
- Subtext: "You're now optimized for this role. Here's what to do next."

**Buttons:**
- Primary: "Download Optimized Resume (.docx)"
- Secondary: "Review All Changes"
- Tertiary: "Try Another Job" (funnel to repeated use)

**Profile prompt (contextual, not tacked on):**
- Box treatment (highlighted)
- Icon: "💡"
- Headline: "Working towards your next step?"
- Copy: "Build your profile so you don't upload a resume next time. We'll pre-fill it with your experience from this optimization."
- Buttons: "Build Profile Now" (primary) | "Skip for now" (secondary)
- **Key:** Only show if `is_first_optimization == True` AND user downloaded successfully

**Logic:**
- Calculate improvements (before/after delta) on backend
- Only show improvements ≥ 5 point threshold
- Generate "Why" context for each improvement using prompt summarization
- If match improves <5 points, show different messaging:
  - "Your resume already matches this role well (79% → 82%). We found 1 small improvement."
  - Suggest: "This is a strong match. You're ready to apply."
- If match improves >15 points, show celebration:
  - "Wow! You've gone from Fair to Strong Match. Big improvement."

**Implementation notes:**
- Before/After is NOT the text from user's resume; it's the optimized paragraphs only
- Show top 3-5 changes, not all
- Include timestamp on download (so user can track which version they used)
- Profile prompt triggers `is_first_optimization = False` when shown (not when clicked)

---

### FLOW B: Repeated Use (Existing User, From Profile)

#### **Screen A: Landing → Job Description (Simplified)**

**Wireframe:**
```
┌─────────────────────────────────────────────┐
│ STEP 1 OF 3: Point at a new role           │
├─────────────────────────────────────────────┤
│                                               │
│ Using your saved resume from:               │
│ "Program Manager role @ Apple" (Apr 12)    │
│                                               │
│ ────────────────────────────────────────    │
│ Don't want to use this? [Upload new]       │
│                                               │
│ ┌──────────────────────────────────────┐    │
│ │ TARGET A NEW ROLE                   │    │
│ │ Paste job description or URL        │    │
│ │                                     │    │
│ │ [S: Paste here]                    │    │
│ │ [S: Process Job Description]       │    │
│ └──────────────────────────────────────┘    │
│                                               │
│ ┌──────────────────────────────────────┐    │
│ │ [Back] [Primary: Continue]          │    │
│ └──────────────────────────────────────┘    │
│                                               │
└─────────────────────────────────────────────┘
```

**Key changes:**
1. **Resume is pre-filled** — Show which resume is being used + option to change
2. **Workflow is now 3 steps, not 4** — Skip upload step (already saved)
3. **Reduced friction** — User goes straight to job description

**Copy:**

**Headline:** "Point at a new role"

**Resume status:**
- "Using your saved resume from: Program Manager role @ Apple (Apr 12)"
- Link: "[Upload a different resume]" (secondary action)

**Job description input:**
- Instruction: "Paste the full job posting or LinkedIn URL"
- Textarea placeholder: "Paste job description here..."
- Button: "Process Job Description"

---

#### **Screen B: Pre-Optimization Match (Same as Screen 3)**

**No changes** — Show match % same as first-time users

---

#### **Screen C: Mode Selection (Same as Screen 4)**

**No changes** — Same two options

---

#### **Screen D: Results (Same as Screen 5, but different profile prompt)**

**Changes to profile prompt:**
- User already has profile, so show different message:
  - "💡 Profile Updated"
  - "We've added your improvements to your profile for next time."
  - No "Build Profile" button; just "Got it" or "Close"

---

### FLOW C: Application History Dashboard

#### **Screen: Job Application History**

**Access point:** Via sidebar "Application Workspace" (existing) OR new "Job Applications" menu

**Wireframe:**
```
┌─────────────────────────────────────────────┐
│ Your Job Applications                       │
├─────────────────────────────────────────────┤
│                                               │
│ You've optimized 5 resumes. Applying now.  │
│                                               │
│ Sort: [Newest ▼] Filter: [All ▼]           │
│                                               │
│ ┌─────────────────────────────────────────┐ │
│ │ Program Manager, Worldwide Logistics    │ │
│ │ @ Apple                                 │ │
│ │ Apr 12, 2026 | 65% → 78% ✓             │ │
│ │ [Optimize Again] [View Changes]        │ │
│ └─────────────────────────────────────────┘ │
│                                               │
│ ┌─────────────────────────────────────────┐ │
│ │ Senior Operations Manager               │ │
│ │ @ Google                                │ │
│ │ Apr 10, 2026 | 71% → 85% ✓             │ │
│ │ [Optimize Again] [View Changes]        │ │
│ └─────────────────────────────────────────┘ │
│                                               │
│ ┌─────────────────────────────────────────┐ │
│ │ Data Analyst, Entry-Level               │ │
│ │ @ Amazon                                │ │
│ │ Apr 8, 2026 | 52% → 64%                │ │
│ │ [Optimize Again] [View Changes]        │ │
│ └─────────────────────────────────────────┘ │
│                                               │
└─────────────────────────────────────────────┘
```

**List item format:**
```
[Job Title]
@ [Company]
[Date] | [Before %] → [After %] [Status badge]
[Action buttons: Optimize Again, View Changes]
```

**Key features:**
1. **Simple list format** (user requested)
2. **Show match progression** (before → after)
3. **Quick access to re-optimize** ("Optimize Again" button)
4. **View previous improvements** ("View Changes")
5. **Sort/filter options** (Newest, Best match, etc.)

**Logic:**
- Click "Optimize Again" → uses same resume, asks for new JD → goes to job description screen
- Click "View Changes" → shows the improvements dropdown from that optimization
- Auto-save application data (company, title, date, match scores)
- Don't store full resume unless user pays for cloud storage

---

## 4. Technical Implementation Notes

### Database Schema Updates
```
applications table (new):
- id (primary key)
- user_id
- company_name
- job_title
- job_description (store raw JD for reference)
- resume_used_id (reference to which resume)
- match_before (int: 0-100)
- match_after (int: 0-100)
- improvements (json: array of {before, after, why, type})
- created_at
- optimized_at

profiles table (new):
- id (primary key)
- user_id
- name
- email
- phone
- location
- career_stage
- industries (json array)
- resume_snippet (plain text extraction of key experience)
- created_at
- updated_at
```

### Backend Changes Required

**1. Match Score Calculation (Screen 3/B)**
```python
def calculate_match_score(resume_text, jd_text):
    """
    Returns: int (0-100)
    Factors:
    - Keyword overlap (40%)
    - Verb strength (30%)
    - ATS readability (20%)
    - Role relevance (10%)
    """
    keyword_score = compare_keywords(resume_text, jd_text)  # 0-100
    verb_score = analyze_action_verbs(resume_text, jd_text)  # 0-100
    ats_score = assess_ats_readability(resume_text)  # 0-100
    relevance_score = assess_role_match(resume_text, jd_text)  # 0-100
    
    final_score = (
        keyword_score * 0.4 +
        verb_score * 0.3 +
        ats_score * 0.2 +
        relevance_score * 0.1
    )
    return int(final_score)
```

**2. Key Signals Extraction (Screen 3/B)**
```python
def extract_key_signals(resume_text, jd_text):
    """
    Returns: dict with structure:
    {
        "matches": [
            {"signal": "Supply Chain Management", "strength": "strong"},
            {"signal": "Cross-functional Leadership", "strength": "strong"}
        ],
        "gaps": [
            {"signal": "Advanced Analytics", "reason": "not_mentioned"},
            {"signal": "Tableau", "reason": "not_mentioned"}
        ]
    }
    """
    # Extract key terms from JD
    # Cross-reference with resume
    # Classify as match or gap
    # Return top 4-6 signals (2-3 matches, 2-3 gaps)
```

**3. Improvement Extraction & Context (Screen 5/D)**
```python
def generate_improvements_summary(before_text, after_text):
    """
    Returns: list of dicts
    [
        {
            "type": "stronger_verb",
            "before": "Managed supply chain operations",
            "after": "Led supply chain operations strategy",
            "why": "This role needs demonstrated leadership. 'Led' signals...",
            "impact": "high"
        },
        ...
    ]
    Filter: Only include improvements where impact >= threshold
    """
    # Compare before/after paragraphs
    # Categorize changes (verb, keyword, impact metric, etc.)
    # Generate "why" using prompt summarization
    # Filter by impact threshold (>= 5 points)
```

**4. Profile Pre-fill (After Screen 5/D)**
```python
def create_profile_from_optimization(user_id, resume_text, improvements):
    """
    Auto-populate profile with extracted info:
    - Name, email, phone (extract from resume)
    - Career stage (infer from resume)
    - Industries (infer from resume + JD)
    - Key experience snippets (extract top 3-5 bullet points)
    User then can refine in profile dashboard
    """
```

### Frontend Changes Required

1. **Consolidate Screen 2** (Upload)
   - Remove random URL display
   - Clean up default JD text
   - Add inline validation

2. **Create Screen 3** (Pre-optimization match)
   - New component: Match % circle (visual)
   - New component: Key signals breakdown
   - Wire to `calculate_match_score()` and `extract_key_signals()`

3. **Redesign Screen 4** (Mode selection)
   - Hide "Advanced" option
   - Make API mode obvious default
   - Update copy for clarity

4. **Redesign Screen 5** (Results)
   - Replace "10 exact matches, 0 issues" with before/after examples
   - Add dropdown component for improvements
   - Update profile prompt copy (contextual)
   - Add "Try Another Job" button → Dashboard

5. **Create Dashboard** (Application history)
   - New screen: List of past optimizations
   - Sort/filter by date, match improvement
   - Action buttons: "Optimize Again", "View Changes"

6. **Update Sidebar**
   - Add "Job Applications" link (optional, or integrate into "Application Workspace")
   - Keep "Career Profile" accessible

---

## 5. Copy Guidelines

### Tone & Voice
- **Confident, not salesy** — "Your resume is optimized" not "Your resume is now amazing!"
- **User-focused** — "You're now ready to apply" not "We've completed the optimization"
- **Clear** — No jargon. "65% match" not "keyword alignment score"
- **Reassuring** — Reduce anxiety. "Strong match means you should apply."

### Key Messaging Pillars
1. **Match % is the north star** — Every screen emphasizes how well resume matches role
2. **Concrete improvements** — Show real examples, not counts
3. **Progressive journey** — "Step X of Y" orients user
4. **Profile as convenience** — "Don't upload next time" not "Build your data store"
5. **One flow is clear** — API is default; manual available but not equal

---

## 6. Success Metrics & KPIs

### Conversion Funnels
```
Landing → First Job Optimization
- Target: 60% of users complete first optimization
- Current est: 30-40% (too many drop-off points)

First Optimization → Download
- Target: 80% of users who see results download resume
- Current est: 50% (unclear value, "before/after not available")

First Optimization → Profile Build
- Target: 40% of users build profile after first optimization
- Current est: 10% (prompt tacked on at end)

Repeated Use
- Target: User optimizes 3+ additional roles within 30 days
- Current est: Unknown (no history tracking)
```

### User Experience Metrics
- **Time to first download:** Target <5 min (vs current ~10 min)
- **Drop-off by screen:** Track where users abandon
- **Match improvement avg:** Track if users see meaningful improvement (avg +10 points)
- **Profile completion rate:** Track if context-aware profile prompt works better

### Product Health
- **Manual mode adoption:** Track % of users choosing Manual (goal: <15%)
- **Funnel from Manual → API:** Track if users retry with API mode
- **Re-optimization rate:** Track % of users optimizing 2nd, 3rd resume
- **Support requests:** Track common issues (e.g., "Before/after not showing")

---

## 7. Rollout Plan

### Phase 1: Backend Prep (Week 1)
- [ ] Add database schema for applications, profiles
- [ ] Implement `calculate_match_score()`
- [ ] Implement `extract_key_signals()`
- [ ] Implement `generate_improvements_summary()`

### Phase 2: Frontend Redesign (Week 2)
- [ ] Redesign Screen 2 (cleaner upload/JD input)
- [ ] Create Screen 3 (pre-optimization match)
- [ ] Redesign Screen 4 (mode selection, API default)
- [ ] Redesign Screen 5 (results with improvements)
- [ ] Create Dashboard (application history)
- [ ] Update sidebar navigation

### Phase 3: Testing & QA (Week 3)
- [ ] Manual QA: All 5 flows (first-time, repeated-use including manual mode)
- [ ] Match scoring accuracy (test with 10+ real resume/JD pairs)
- [ ] Improvements extraction accuracy
- [ ] Profile pre-fill logic
- [ ] Mobile responsiveness

### Phase 4: Soft Launch (Week 4)
- [ ] Deploy to internal/beta users
- [ ] Collect feedback on new flows
- [ ] Track funnel metrics
- [ ] Iterate based on feedback

### Phase 5: Full Launch (Week 5)
- [ ] Public release
- [ ] Monitor KPIs
- [ ] Support optimization questions

---

## 8. Success Criteria

**The redesign is successful if:**

1. ✅ First-time drop-off rate **decreases from 60% to 30%** (more users finish first optimization)
2. ✅ **60% of first-time users** see match improvements ≥5 points (users feel value)
3. ✅ **50% of first-timers** build a profile (context-aware prompt works)
4. ✅ **Manual mode < 15%** of users (API is clear default)
5. ✅ **Average time to download < 5 minutes** (streamlined flow)
6. ✅ **30% of users** attempt 2nd optimization within 7 days (repeated use)
7. ✅ **Zero support requests** about "before/after previews not available" (solved)
8. ✅ **User feedback**: "I understand exactly how much better my resume is now" (clarity achieved)

---

## Appendix: Messaging Examples

### Screen 3 Variations by Match %

**If match is <50% (Poor Match):**
```
Headline: "This is a stretch—but we can help."
Subtext: "Your resume currently matches 32% of this role's signals. 
We'll focus on bridging those gaps."
CTA: "Let's optimize for a better match."
```

**If match is 50-70% (Fair Match):**
```
Headline: "Good foundation—let's strengthen it."
Subtext: "Your resume matches 65% of this role. 
We can push you toward Strong Match territory."
CTA: "Optimize now."
```

**If match is 70-85% (Strong Match):**
```
Headline: "Strong match—let's get you over the top."
Subtext: "Your resume is 78% aligned. We found a few key improvements 
that could tip the scales in your favor."
CTA: "Make these changes."
```

**If match is 85%+ (Excellent Match):**
```
Headline: "Excellent match—you're ready."
Subtext: "Your resume is 92% aligned with this role. 
We found minor tweaks to ensure ATS and recruiter both see your fit."
CTA: "Optimize for perfection."
```

---

**End of Spec Document**

*Last updated: 2026-04-12*  
*Next review: After Phase 3 QA*
