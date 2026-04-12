# Phase 2: Frontend Redesign Implementation Plan

**Duration:** 3-4 days  
**Status:** Starting now  
**Goal:** Implement all 5 frontend screens + dashboard

---

## Phase 2 Task Breakdown

### **Task 2.1: Redesign Screen 2 (Upload/JD)**
**Current issue:** Random URL shown, cluttered default text, unclear instructions  
**New behavior:** Clean two-column layout, empty inputs, better copy

**Wireframe location:** REDESIGN_SPEC.md, Section 3, Screen 2

**Changes needed:**
- Remove URL display logic
- Clear default JD text (use placeholder instead)
- Better copy: "Upload a .docx file. We'll preserve formatting..."
- Clean validation (show ✓ when ready)
- Two buttons: "Continue" or "Back"

**Files to modify:**
- `streamlit_app.py`: Update `render_input_screen()` function
- OR create new Screen 2.5 between upload and job description

**Dependencies:**
- None (no backend functions needed yet)

---

### **Task 2.2: Create Screen 3 (Pre-Optimization Match) - NEW**
**Purpose:** Show user "65% match → FAIR MATCH" BEFORE asking them to wait for optimization

**Wireframe location:** REDESIGN_SPEC.md, Section 3, Screen 3

**What to display:**
- Job title + company
- Large circular match % indicator
- Match band label (Poor / Fair / Strong / Excellent)
- Key signals list (3 matches, 3 gaps with ✓/✗)
- Two buttons: "Back" or "Optimize Now"

**Backend functions to call:**
- `calculate_match_score(resume_text, jd_text)` → match %
- `extract_key_signals(resume_text, jd_text)` → {matches, gaps}

**New Streamlit elements:**
- HTML circle for % display
- Match band classification logic
- Conditional rendering for different match ranges

**Files to modify:**
- `streamlit_app.py`: Add new `render_fit_report_screen()` OR `render_pre_optimization_screen()`

---

### **Task 2.3: Redesign Screen 4 (Mode Selection)**
**Current problem:** Manual and API are equal options, confusing descriptions

**New behavior:** API is prominent ("Recommended"), Manual is secondary

**Wireframe location:** REDESIGN_SPEC.md, Section 3, Screen 4

**Changes:**
- API box is larger, "🚀 Recommended" badge
- Manual box is smaller, secondary style
- Remove "Advanced" option (hide in settings)
- Better copy: "30 seconds, no copy-paste" vs "You want control"
- One primary button (API), one secondary (Manual)

**Files to modify:**
- `streamlit_app.py`: Update `render_mode_screen()` function
- No backend changes needed

---

### **Task 2.4: Redesign Screen 5 (Results & Export)**
**Current problem:** "Before/after previews not available", unclear improvements, profile prompt tacked on

**New behavior:**
- Hero match display: "65% → 78% (+13%)"
- Improvements dropdown (not collapsed)
- "Why" context for each improvement
- Contextual profile prompt (not tacked on)

**Wireframe location:** REDESIGN_SPEC.md, Section 3, Screen 5

**What to display:**
1. Match progression (before → after with delta)
2. Improvements section (expandable, showing 3-5 concrete examples)
3. Three action buttons (Download, Review Changes, Try Another Job)
4. Profile prompt (contextual, only if first optimization)

**Backend functions to call:**
- `save_optimization_result()` → save data after successful optimization
- `create_or_update_profile_from_optimization()` → called if user clicks "Build Profile"
- Already calling improvements from prompt output

**Files to modify:**
- `streamlit_app.py`: Update `render_review_screen()` function
- Add session state for profile prompt tracking (already done in Phase 1 code changes)

---

### **Task 2.5: Create Dashboard (Application History) - NEW**
**Purpose:** Show past optimizations, enable repeated use

**Wireframe:** Simple list format showing:
- Company + Job Title
- Date
- Match progression (65% → 78%)
- Action buttons: "Optimize Again", "View Changes"

**Format:** List display, sorted newest first

**Backend functions to call:**
- `get_optimization_history(user_id)` → fetch past applications

**New screen name:** "profile_dashboard" OR "application_workspace" (update sidebar nav)

**Files to modify:**
- `streamlit_app.py`: Add new `render_job_applications_screen()` function
- Update sidebar to link to this screen

---

## Implementation Order

**Recommended sequence:**
1. **Task 2.1** - Screen 2 (foundation, unblocks 2.2)
2. **Task 2.2** - Screen 3 (NEW screen)
3. **Task 2.3** - Screen 4 (simple update)
4. **Task 2.4** - Screen 5 (complex update)
5. **Task 2.5** - Dashboard (NEW screen)

**Rationale:** Complete the first optimization flow end-to-end, then add dashboard.

---

## Session State Updates Needed

Add to `init_session_state()`:
```python
"pre_opt_match_score": 0,  # Screen 3
"pre_opt_signals": {},  # Screen 3
"post_opt_match_score": 0,  # Screen 5
"show_improvements_dropdown": True,  # Screen 5 (default expanded)
```

---

## HTML/CSS Components to Create

### Screen 3: Match % Circle
```html
<div style="display: flex; justify-content: center; margin: 2rem 0;">
  <div style="width: 200px; height: 200px; border-radius: 50%; 
              background: conic-gradient(from 0deg, #2ecc71 0%, #2ecc71 65%, #e0e0e0 65%);
              display: flex; align-items: center; justify-content: center;">
    <div style="text-align: center; background: white; border-radius: 50%;
                width: 180px; height: 180px; display: flex; flex-direction: column;
                align-items: center; justify-content: center;">
      <div style="font-size: 48px; font-weight: bold;">65%</div>
      <div style="font-size: 14px; color: #666;">FAIR MATCH</div>
    </div>
  </div>
</div>
```

### Screen 5: Before/After Badge
```html
<div style="display: flex; align-items: center; justify-content: center; gap: 1rem;">
  <div style="text-align: center;">
    <div style="font-size: 12px; color: #999;">BEFORE</div>
    <div style="font-size: 32px; font-weight: bold;">65%</div>
  </div>
  <div style="font-size: 24px;">→</div>
  <div style="text-align: center;">
    <div style="font-size: 12px; color: #999;">AFTER</div>
    <div style="font-size: 32px; font-weight: bold; color: #2ecc71;">78%</div>
  </div>
  <div style="margin-left: 1rem; padding: 0.5rem 1rem; background: #2ecc71; color: white; border-radius: 0.25rem;">
    <strong>+13%</strong>
  </div>
</div>
```

---

## API Integration Points

### Screen 3 (Pre-Optimization):
```python
# When user clicks "Optimize Now"
match_before = calculate_match_score(
    st.session_state.resume_text,
    st.session_state.job_description
)
signals = extract_key_signals(
    st.session_state.resume_text,
    st.session_state.job_description
)
st.session_state.pre_opt_match_score = match_before
st.session_state.pre_opt_signals = signals
st.session_state.screen = "mode"  # Go to mode selection
st.rerun()
```

### Screen 5 (Results):
```python
# After successful optimization
match_after = calculate_match_score(
    st.session_state.resume_text,
    st.session_state.output_docx_bytes (or extract text)
)
improvements = generate_improvements_summary(
    st.session_state.validated_payload.get("replacements", []),
    st.session_state.job_description
)
save_optimization_result(
    user_id="local-user",
    company_name=company,
    job_title=job_title,
    job_description=jd_text,
    match_before=st.session_state.pre_opt_match_score,
    match_after=match_after,
    improvements=improvements
)
st.session_state.post_opt_match_score = match_after
st.session_state.optimization_improvements = improvements
```

---

## Testing Checklist

- [ ] Screen 2: No URL shown, clean inputs, validation works
- [ ] Screen 3: Match % displays correctly, signals are accurate
- [ ] Screen 4: API is default, clear descriptions
- [ ] Screen 5: Match progression shows, improvements dropdown works
- [ ] Screen 5: Profile prompt shows only on first optimization
- [ ] Dashboard: Lists past applications, sorted by date
- [ ] Dashboard: "Optimize Again" button works
- [ ] End-to-end: Complete one full optimization flow

---

## Success Criteria for Phase 2

✅ All 5 screens render without errors  
✅ Backend functions wire correctly (no API errors)  
✅ Match scores display 0-100 in proper band (Poor/Fair/Strong/Excellent)  
✅ Improvements dropdown shows 3-5 high-impact changes with "why" context  
✅ Profile prompt appears only once per session  
✅ Dashboard shows optimization history correctly  
✅ No broken UI elements on desktop or mobile  

---

## Next: Phase 3 (QA & Testing)

After Phase 2:
- Manual browser testing of all flows
- Accuracy validation of match scores
- Improvements categorization accuracy
- Dashboard data persistence check

---

**Ready to implement Phase 2.1: Screen 2 Redesign**
