# Phase 1: Backend Implementation Plan

**Phase:** Backend Prep  
**Duration:** 3-5 days  
**Owner:** Backend development  
**Goal:** Implement match scoring, signals extraction, improvements generation, and profile pre-fill

---

## Deliverables

- [ ] Database schema updates (applications, profiles tables)
- [ ] `calculate_match_score()` function (resume + JD → 0-100)
- [ ] `extract_key_signals()` function (resume + JD → {matches, gaps})
- [ ] `generate_improvements_summary()` function (before/after → [{type, before, after, why}])
- [ ] `create_profile_from_optimization()` function (auto-populate profile from first resume)
- [ ] Unit tests for all scoring functions
- [ ] Integration tests for full flow

---

## Task Breakdown

### **Task 1.1: Database Schema**
**File:** `profile_store.py` (update existing)

**What:** Add two new tables to SQLite schema

**Schema:**
```sql
CREATE TABLE IF NOT EXISTS applications (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    company_name TEXT NOT NULL,
    job_title TEXT NOT NULL,
    job_description TEXT,
    resume_used_id TEXT,
    match_before INTEGER,
    match_after INTEGER,
    improvements TEXT,  -- JSON
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    optimized_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS profiles (
    id TEXT PRIMARY KEY,
    user_id TEXT,
    name TEXT,
    email TEXT,
    phone TEXT,
    location TEXT,
    career_stage TEXT,
    industries TEXT,  -- JSON array
    resume_snippet TEXT,  -- Plain text extract of key experience
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Implementation:**
- Add migration function `create_applications_table()`
- Add migration function `create_profiles_table()`
- Call these in `init_profile_db()` (existing function)
- Add CRUD functions:
  - `upsert_application(user_id, company, title, jd, match_before, match_after, improvements)`
  - `get_applications(user_id)` → list of applications sorted by date DESC
  - `create_profile(user_id, data)`
  - `update_profile(user_id, data)`
  - `get_profile(user_id)`

**Testing:** Verify tables exist after `init_profile_db()` runs

---

### **Task 1.2: Match Score Calculation**
**File:** Create new file `resume_evaluator.py` (or extend existing if it exists)

**Function:** `calculate_match_score(resume_text: str, jd_text: str) -> int`

**Logic:**
```python
def calculate_match_score(resume_text, jd_text):
    """
    Calculate match score (0-100) based on:
    - Keyword overlap (40%)
    - Verb strength (30%)
    - ATS readability (20%)
    - Role relevance (10%)
    """
    # 1. Extract keywords from both
    resume_keywords = extract_keywords(resume_text)
    jd_keywords = extract_keywords(jd_text)
    
    # 2. Calculate overlap
    keyword_score = calculate_keyword_overlap(resume_keywords, jd_keywords)  # 0-100
    
    # 3. Analyze verbs
    verb_score = analyze_action_verbs(resume_text, jd_text)  # 0-100
    
    # 4. Assess ATS
    ats_score = assess_ats_readability(resume_text)  # 0-100
    
    # 5. Assess role relevance
    relevance_score = assess_role_relevance(resume_text, jd_text)  # 0-100
    
    # 6. Weighted average
    final_score = (
        keyword_score * 0.4 +
        verb_score * 0.3 +
        ats_score * 0.2 +
        relevance_score * 0.1
    )
    
    return int(final_score)
```

**Sub-functions needed:**
- `extract_keywords(text)` → set of normalized keywords
- `calculate_keyword_overlap(resume_kw, jd_kw)` → 0-100 score
- `analyze_action_verbs(resume_text, jd_text)` → 0-100 (do verbs in resume match JD context?)
- `assess_ats_readability(resume_text)` → 0-100 (formatting, structure, readability)
- `assess_role_relevance(resume_text, jd_text)` → 0-100 (does career path seem aligned?)

**Testing:**
- Test with 10 sample resume/JD pairs
- Verify scores are reasonable (65% for fair, 80% for strong, etc.)
- Edge cases: Resume too short, JD too vague

---

### **Task 1.3: Key Signals Extraction**
**File:** `profile_matcher.py` (may already exist, extend it)

**Function:** `extract_key_signals(resume_text: str, jd_text: str) -> dict`

**Returns:**
```python
{
    "matches": [
        {"signal": "Supply Chain Management", "strength": "strong"},
        {"signal": "Cross-functional Leadership", "strength": "moderate"}
    ],
    "gaps": [
        {"signal": "Advanced Analytics", "reason": "not_mentioned"},
        {"signal": "Tableau", "reason": "not_mentioned"}
    ]
}
```

**Logic:**
```python
def extract_key_signals(resume_text, jd_text):
    # 1. Extract must-have skills from JD (top 10)
    jd_signals = extract_top_signals(jd_text)  # [skill1, skill2, ...]
    
    # 2. For each JD signal, check if in resume
    matches = []
    gaps = []
    
    for signal in jd_signals:
        if signal_in_resume(signal, resume_text):
            strength = assess_strength(signal, resume_text)  # strong, moderate, weak
            matches.append({"signal": signal, "strength": strength})
        else:
            gaps.append({"signal": signal, "reason": "not_mentioned"})
    
    # 3. Return top 2-3 matches, top 2-3 gaps
    return {
        "matches": matches[:2],
        "gaps": gaps[:2]
    }
```

**Sub-functions:**
- `extract_top_signals(jd_text)` → list of key terms (use NLP or simple extraction)
- `signal_in_resume(signal, resume_text)` → bool (case-insensitive search + variations)
- `assess_strength(signal, resume_text)` → "strong" | "moderate" | "weak"

**Testing:**
- Verify signals align with actual resume/JD content
- Edge case: Acronyms (e.g., "SAP" vs "S.A.P.", "SQL" vs "sql")

---

### **Task 1.4: Improvements Extraction & Context Generation**
**File:** New file `improvements_generator.py`

**Function:** `generate_improvements_summary(before_json: dict, after_json: dict, resume_text: str, jd_text: str) -> list`

**Returns:**
```python
[
    {
        "type": "stronger_verb",
        "before": "Managed supply chain operations",
        "after": "Led supply chain operations strategy",
        "why": "This role needs demonstrated leadership. 'Led' signals you drive strategy, not just execute plans.",
        "impact": "high"
    },
    {
        "type": "quantified_impact",
        "before": "Coordinated shipments",
        "after": "Coordinated 500+ monthly shipments, reducing delays by 20%",
        "why": "Numbers make impact tangible and memorable to ATS and recruiters.",
        "impact": "high"
    },
    {
        "type": "keyword_addition",
        "before": "(not mentioned)",
        "after": "Tableau dashboards for analytics",
        "why": "The job mentions 'Tableau' twice. Your resume didn't. This addition increases keyword match.",
        "impact": "high"
    }
]
```

**Logic:**
```python
def generate_improvements_summary(before_json, after_json, resume_text, jd_text):
    improvements = []
    
    # 1. Compare before/after JSON replacements
    for replacement in after_json:
        before_text = replacement.get("match_anchor")
        after_text = replacement.get("replacement_text")
        
        # 2. Categorize the type of change
        change_type = categorize_change(before_text, after_text)
        
        # 3. Generate "why" explanation
        why_text = generate_why_context(
            change_type, before_text, after_text, jd_text
        )
        
        # 4. Assess impact
        impact = assess_impact(before_text, after_text, jd_text)
        
        improvements.append({
            "type": change_type,
            "before": before_text,
            "after": after_text,
            "why": why_text,
            "impact": impact
        })
    
    # 5. Filter: Only show improvements with impact >= "high"
    # (or adjust threshold as needed)
    important_improvements = [i for i in improvements if i["impact"] in ["high", "very_high"]]
    
    # 6. Return top 5
    return important_improvements[:5]
```

**Sub-functions:**
- `categorize_change(before, after)` → "stronger_verb" | "quantified_impact" | "keyword_addition" | "restructured" | "clarity_improved"
- `generate_why_context(type, before, after, jd_text)` → str (human-readable explanation)
- `assess_impact(before, after, jd_text)` → "low" | "medium" | "high" | "very_high"

**Example "why" generation:**
```python
def generate_why_context(change_type, before, after, jd_text):
    if change_type == "stronger_verb":
        old_verb = extract_verb(before)
        new_verb = extract_verb(after)
        return f"'{new_verb}' is stronger than '{old_verb}' and signals proactive leadership."
    elif change_type == "quantified_impact":
        return "Numbers make impact tangible and memorable to ATS and recruiters."
    elif change_type == "keyword_addition":
        new_keyword = extract_new_keyword(before, after)
        count_in_jd = count_occurrences(new_keyword, jd_text)
        return f"The job mentions '{new_keyword}' {count_in_jd} times. Adding it increases match."
    # ... etc
```

**Testing:**
- Verify "why" explanations are accurate
- Ensure only high-impact changes shown
- Test with sample optimization outputs

---

### **Task 1.5: Profile Pre-fill from First Optimization**
**File:** `profile_store.py` (extend existing)

**Function:** `create_profile_from_optimization(user_id: str, resume_text: str) -> dict`

**Logic:**
```python
def create_profile_from_optimization(user_id, resume_text):
    """
    Auto-populate profile with extracted info from resume:
    - Name (from header)
    - Email (from header)
    - Phone (from header)
    - Location (if present)
    - Career stage (infer from experience)
    - Industries (infer from resume content)
    - Key experience snippets (extract top 3-5 bullet points)
    """
    
    profile_data = {}
    
    # 1. Extract contact info
    profile_data["name"] = extract_name(resume_text)
    profile_data["email"] = extract_email(resume_text)
    profile_data["phone"] = extract_phone(resume_text)
    profile_data["location"] = extract_location(resume_text)
    
    # 2. Infer career stage
    years_exp = count_years_of_experience(resume_text)
    profile_data["career_stage"] = infer_career_stage(years_exp)
    # Logic: 0-2 years = "Student", 2-5 = "Early Career", 
    #        5-10 = "Mid-Level", 10+ = "Manager" / "Executive"
    
    # 3. Extract industries (from job companies/titles)
    profile_data["industries"] = extract_industries(resume_text)
    # Return as JSON array: ["Technology", "Consulting"]
    
    # 4. Extract key experience snippets
    profile_data["resume_snippet"] = extract_key_bullets(resume_text, max_bullets=5)
    # Return as plain text, first 5 bullet points
    
    # 5. Save to database
    upsert_profile(user_id, profile_data)
    
    return profile_data
```

**Sub-functions:**
- `extract_name(text)` → str
- `extract_email(text)` → str
- `extract_phone(text)` → str
- `extract_location(text)` → str
- `count_years_of_experience(text)` → int
- `infer_career_stage(years)` → str (from CAREER_STAGES constant)
- `extract_industries(text)` → list[str] (use company/role context)
- `extract_key_bullets(text, max_bullets)` → str (first N bullet points)

**Testing:**
- Pre-fill a profile from a sample resume
- Verify all fields are populated
- Check that extracted data is reasonable

---

### **Task 1.6: Unit Tests**
**File:** Create `tests/test_redesign_phase1.py`

**Test cases:**
```python
def test_calculate_match_score_fair():
    resume = "Program Manager with supply chain experience"
    jd = "Program Manager, supply chain operations"
    score = calculate_match_score(resume, jd)
    assert 50 <= score <= 80  # Should be fair match

def test_extract_key_signals():
    resume = "I did supply chain and analytics"
    jd = "Need Tableau, SQL, supply chain, leadership"
    signals = extract_key_signals(resume, jd)
    assert len(signals["matches"]) >= 1
    assert len(signals["gaps"]) >= 1

def test_generate_improvements():
    before = {"match_anchor": "Managed", "replacement_text": "Led"}
    after = [before]
    improvements = generate_improvements_summary(after, {}, "resume", "jd")
    assert improvements[0]["type"] in ["stronger_verb", "...]
    assert "why" in improvements[0]

def test_create_profile_from_optimization():
    resume = "John Doe\njohn@example.com\n555-1234\nManager with 8 years experience"
    profile = create_profile_from_optimization("user1", resume)
    assert profile["name"] == "John Doe"
    assert profile["career_stage"] == "Manager"
```

---

## Implementation Order

**Priority order (can be parallelized):**

1. **Task 1.1: Database Schema** (blocker for tasks 2-5)
   - Implement, test schema exists
  
2. **Task 1.2: Match Score Calculation** (can start after 1.1)
   - Implement scoring functions
   - Test with sample data
   
3. **Task 1.3: Key Signals Extraction** (can start after 1.1)
   - Extract key signals from resume/JD
   - Test signals are accurate
   
4. **Task 1.4: Improvements Extraction** (can start after 1.2)
   - Generate before/after examples
   - Test "why" explanations
   
5. **Task 1.5: Profile Pre-fill** (can start after 1.1)
   - Auto-populate profile from resume
   - Test extraction accuracy
   
6. **Task 1.6: Unit Tests** (after all tasks)
   - Write comprehensive tests
   - Achieve 80%+ coverage

---

## Success Criteria for Phase 1

- ✅ All database tables created and accessible
- ✅ Match scores calculated accurately (test with 10 resume/JD pairs)
- ✅ Key signals extracted correctly (verified manually)
- ✅ Improvements extracted with accurate "why" context
- ✅ Profile pre-filled from sample resume (all fields populated)
- ✅ Unit tests pass (>80% coverage)
- ✅ No errors when calling functions with edge cases (empty text, special chars, etc.)

---

## Next Steps (Phase 2)

After Phase 1, **Phase 2: Frontend Redesign** will:
- Wire these functions to the new Streamlit screens
- Create Screen 3 (pre-optimization match display)
- Create Screen 5 improvements dropdown
- Create Dashboard
- Update mode selection screen

---

**Estimated time:** 3-5 days
**Status:** Ready to implement
