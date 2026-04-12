# User Testing Framework

## Purpose
A repeatable template for testing each UX improvement with real users after deployment.

## Survey Template (Ask After Each Change)

**Q1: Understanding**  
"What is this screen asking you to do?"
- Success: User answers in less than 15 seconds without hesitation
- Maps to metric: Speed-to-next-step

**Q2: Confidence**  
For Student: "How anxious do you feel about using this? (1=very anxious, 10=confident)"
- Target: 7+/10
- Maps to: Anxiety reduction from `METRICS_BASELINE.md`

For Professional: "How much do you trust this vs. ChatGPT? (1-10)"
- Target: 7+/10
- Maps to: Trust score from `METRICS_BASELINE.md`

For Executive: "How confident are you this won't hurt your brand? (1-10)"
- Target: 8+/10
- Maps to: Risk credibility from `METRICS_BASELINE.md`

**Q3: Next Steps**  
"What should you do next?"
- Success: User knows without hesitation
- Failure: User guesses or asks for help

**Q4: Clarity**  
"What would make this clearer?"
- Record exact quote
- Maps to: Improvement direction

**Q5: Overall**  
"Would you use this again?"
- Yes / Maybe / No
- Maps to: Overall product-market fit

## Observation Checklist
- [ ] User hesitated before first click
- [ ] User reread instructions before acting
- [ ] User asked what a label or section meant
- [ ] User could explain the next step without help
- [ ] User clicked the expected primary action first
- [ ] User looked for proof or reassurance before proceeding
- [ ] User expressed doubt, anxiety, or skepticism
- [ ] User appeared confident after seeing the result
- [ ] User compared output to original resume
- [ ] User said they would use this in a real application

## Success Criteria Per Task

### Task 1.1: Profile Import Simplification
**Success:**
- Time to understand: Less than 60 seconds
- Confidence: 7+/10
- Quote: "I know what to do" or "I should pick what to keep"

**Failure:**
- Time to understand: More than 90 seconds
- Confidence: Less than 6/10
- Quote: "I don't know what this is asking"

### Task 1.2: Fit Report - Primary Question
**Success:**
- Time to answer "Should I apply?": Less than 30 seconds
- Confidence: 8+/10
- User made decision without exploring 5 panels first

**Failure:**
- Time: More than 60 seconds
- Confidence: Less than 6/10
- User confused by supporting data

### Task 1.3: Post-Optimize Reassurance
**Success:**
- Student anxiety drops 3+ points after seeing changes
- Professional says: "I can see this is objectively better"
- Executive expresses confidence in quality and tone
- User downloads without hesitation

**Failure:**
- Anxiety does not decrease
- Professional remains skeptical of changes
- Executive says it feels inflated or like marketing fluff
- User hesitates to download or use the output

## Failure Criteria
- User cannot explain what the screen is for
- User needs coaching to continue
- Confidence/trust score falls below target for persona
- User says they would not use the feature again
- User abandons the flow before completing the primary action

## Test Session Format

**Pre-Test:** Brief intro + no coaching (2 min)  
**During Test:** Observe + user talks aloud (5-10 min)  
**Post-Test:** Survey Q1-Q5 (3 min)  
**Total:** Approximately 15-20 min per user

## After-Test Documentation

For each user, create notes using this structure:

```markdown
### Tester: [Name or ID]
- Persona: Student / Professional / Executive
- Date:
- Feature tested:
- Time to understand:
- Confidence/trust score:
- Did they know the next step: Yes / No
- Did they complete the main action: Yes / No
- Exact quote:
- Observed hesitation points:
- What confused them:
- What gave confidence:
- Recommendation: Keep / Adjust / Re-test / Revert
```

## Deployment Testing Notes
- Test only on the deployed URL, not local-only flows
- Use the same five questions after every major UX change
- Record exact wording when users express confusion or trust concerns
- Capture screenshots before and after each tested change when possible
- Keep moderator behavior consistent: do not explain the interface unless the user is fully blocked
