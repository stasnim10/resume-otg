# Phase 2: Frontend Redesign - Test Plan

**Status:** Ready for Testing  
**Date:** 2026-04-12  
**Condition:** Code compiles successfully, all imports verified

---

##Test Objectives

✅ Verify all 5 screens render without errors  
✅ Backend functions integrate correctly (no API errors)  
✅ Match scores calculate and display properly (0-100, correct bands)  
✅ Key signals extraction shows accurate matches/gaps  
✅ Improvements dropdown populated with high-impact changes  
✅ Profile prompt appears only on FIRST optimization  
✅ Dashboard displays optimization history correctly  
✅ "Optimize Again" button re-opens jobs for re-optimization  
✅ No UI elements broken (desktop focus)  
✅ Full end-to-end flow completes successfully  

---

## Test Environment Setup

### Prerequisites
```bash
cd "/Users/simumtasnim/App Wizard/Resume Builder OTG/resume_optimizer_local"
python3 -m streamlit run streamlit_app.py
```

### Test Assets Needed
- Sample resume (.docx file) - can be any resume
- Sample job description - copy-paste from LinkedIn/Indeed/etc.

---

## Test Flow: Screens 1-5 + Dashboard

### Screen 1: Landing Page ✓
**What to test:**
- [ ] Landing page loads without errors
- [ ] "Start Optimizing" button visible
- [ ] Sidebar shows correctly with buttons
- [ ] All navigation buttons appear

**Expected result:** Homepage displays with all CTA buttons functional

---

### Screen 2: Upload & Job Description Input ✓

**What to test:**
- [ ] Resume upload button works
- [ ] Job description paste field available
- [ ] "Process Job Description" button processes correctly
- [ ] After upload: shows "Loaded [filename]"
- [ ] "Continue" button available when both inputs filled
- [ ] No leftover URL display from legacy code
- [ ] Copy is clear and concise

**Test data:**
- Upload: Any .docx resume
- Job description: Paste sample JD

**Expected result:** Clean input screen with both fields ready, Continue button enabled

---

### Screen 3: Pre-Optimization Match Score ✅ **[NEW]**

**What to test:**
- [ ] Large circular match % indicator displays
- [ ] Match % value shows correctly (0-100)
- [ ] Color-coded band displays (Poor | Fair | Strong | Excellent)
- [ ] "What Matches" section shows top matches with strength indicators
- [ ] "What's Missing" section shows key gaps
- [ ] Both sections have ~3 items each
- [ ] Buttons present: Back, Try Another, Optimize Now
- [ ] Clicking "Optimize Now" leads to Screen 4 (Mode)

**Backend integration check:**
- `calculate_match_score()` working (match % displayed)
- `extract_key_signals()` working (matches/gaps shown)

**Test data:**
- Use resume from Screen 2
- Use JD from Screen 2

**Expected result:** Match % displays immediately, signals show meaningful signals, OK to proceed to Screen 4

---

### Screen 4: Mode Selection ✅

**What to test:**
- [ ] API mode appears LARGER and marked as "🚀 Recommended"
- [ ] Manual mode appears SMALLER as secondary option
- [ ] API mode has primary button styling
- [ ] Manual mode has secondary button styling
- [ ] Copy is clear about value (API: "30 seconds", Manual: "You want control")
- [ ] Back button returns to Screen 3

**Expected result:** API mode is obviously the default choice, Manual still available

---

### Screen 5: Results & Improvements ✅

**Subtest 5a: Optimization Success Message**
- [ ] "Optimization complete" message displays
- [ ] Match progression shows: "BEFORE 65% → AFTER 78% (+13%)"
- [ ] Green color for positive improvement
- [ ] Delta clearly visible

**Subtest 5b: Improvements Dropdown**
- [ ] First improvement is expanded by default
- [ ] Shows: type, before text, after text, "why it matters", impact level
- [ ] Can expand/collapse other improvements
- [ ] 3-5 improvements shown (if available)
- [ ] Quality of "why" context is compelling

**Subtest 5c: Summary Stats**
- [ ] Shows changes by section: Summary Section, Bullet Points, Skills
- [ ] Numbers look reasonable

**Subtest 5d: Download & Navigation**
- [ ] "Download Optimized Resume" button works
- [ ] File downloads as .docx
- [ ] "Review Full Changes" leads to detailed view
- [ ] "Try Another Job" clears state and goes to Screen 2
- [ ] Back button available

**Backend integration check:**
- `generate_improvements_summary()` returns valid improvements
- `save_optimization_result()` silently saves (no error messages)

**Expected result:** Beautiful display of improvements, download works, can start new job

---

### Screen 5 (Subtest): Profile Prompt Conditional Logic ✅

**On FIRST optimization:**
- [ ] Profile building prompt appears with "Build Profile" + "Skip for now" buttons
- [ ] Prompt text: "Save your experiences... Let the app personalize..."
- [ ] Clicking "Build Profile" navigates to profile welcome screen

**On SUBSEQUENT optimizations:**
- [ ] Profile prompt should NOT appear again (session flag set)

**Test procedure:**
1. Complete first optimization (Screens 1-5)
2. Note if profile prompt appears
3. Click "Skip for now"
4. Click "Try Another Job"
5. Complete second optimization with same/different job
6. Verify profile prompt is GONE

**Expected result:** Prompt appears once, then is suppressed for rest of session

---

### New: Dashboard - Optimization History ✅ **[PHASE 2.5 NEW]**

**Navigation:**
- [ ] Click "📊 Your Optimizations" in sidebar
- [ ] Dashboard loads without errors
- [ ] Shows title: "Past Optimizations"

**Subtest: After First Optimization**
- [ ] Dashboard shows 1 entry
- [ ] Entry displays:
  - Job title + company
  - Date (formatted: "Apr 12, 2026")
  - Match progression: "65% → 78% (+13%)" with colors
  - "✨ X improvements captured"
- [ ] Improvement count matches what was shown in Screen 5

**Subtest: Summary Metrics**
- [ ] Total Optimizations: 1
- [ ] Average Improvement: +X%
- [ ] Best Improvement: +X%

**Subtest: "Optimize Again" Button**
- [ ] Button labeled "Optimize Again" for the entry
- [ ] Clicking loads Screen 2 with ready-to-upload state
- [ ] Can re-upload resume and paste same JD
- [ ] Creates second optimization entry in history

**Subtest: After Multiple Optimizations**
- [ ] Dashboard shows all previous entries (sorted newest first)
- [ ] Summary metrics update correctly
  - Total count increases
  - Average recalculates
  - Best improvement updates if new one is higher
- [ ] Each entry has working "Optimize Again" button

**Backend integration check:**
- `get_optimization_history()` returns all entries
- `save_optimization_result()` persists each optimization
- Match scores stored correctly (before/after values visible)

**Expected result:** Dashboard shows complete history, "Optimize Again" works, metrics calculate correctly

---

## Critical Path Checklist

Before moving to Phase 3 (QA):

- [ ] Screen 2: Both inputs required, Continue only enabled when ready
- [ ] Screen 3: Match % displays 0-100 in correct band
- [ ] Screen 3: Matches/gaps are relevant and non-empty
- [ ] Screen 4: API marked as default, Manual available
- [ ] Screen 5: Match progression shows with delta
- [ ] Screen 5: Improvements show with "why" context
- [ ] Screen 5: Profile prompt appears ONLY on first optimization
- [ ] Dashboard: History displays with company+title+progression
- [ ] Dashboard: "Optimize Again" button works and re-opens flow
- [ ] No Python errors in console
- [ ] No broken UI elements
- [ ] Full flow: Upload → JD → Match % → Mode → Results → Try Again → History

---

## Testing Output Format

For each test, record:

```
SCREEN [number]: [name]
Status: ✅ PASS / ⚠️ PARTIAL / ❌ FAIL
Issues found:
- [issue 1]
Notes:
- [observation 1]
```

---

## Next Steps After Testing

1. **If all tests pass:** → Proceed to Phase 3 (Accuracy Validation)
2. **If UI issues found:** → Create GitHub issues, assign to frontend
3. **If backend errors:** Update function signatures/error handling
4. **If data not persisting:** Debug save_optimization_result() in profile_store.py

---

## Useful Debugging Commands

**Check if backend functions exist:**
```bash
python3 -c "from profile_store import save_optimization_result; print('✓')"
python3 -c "from optimization_history_ui import render_optimization_history_screen; print('✓')"
```

**Check for Python errors:**
```bash
python3 -m py_compile streamlit_app.py
```

**Check database:**
```bash
sqlite3 resume_profile.db "SELECT COUNT(*) FROM applications;"
```

---

**Ready to test!** Start with Screen 2 and work through Screens 3-5, then test the Dashboard.
