# Unstuck prototype: edits from Spencer's feedback

Compiled 2026-09-05 05:26PM from the Gmail thread "Unstuck prototype", Spencer Greenberg's message of 2026-09-04 (26 numbered points plus screenshots). Numbers in brackets are Spencer's. Line references are to index.html at commit 9cc568f.

## Decide first (structural changes; settle these before the copy edits)

- [ ] **Flow order [15, plus the fear commit screen].** Spencer wants "What are you procrastinating on?" to be the first page after the intro, or dropped. He also wants the fear flow to end with a commit screen ("You can start on the task even though it makes you anxious. Will you work on this task now?" with "Yes, start the 10 minute timer" / "No, I'm going to keep avoiding it") that replaces "Ready to start?". That screen can only start a timer if the task and the 10-minute action are already known, so the technique has to come after them. Recommended new order: task → action → cause → technique → commit → timer. Today it is cause → technique → task → action → confirm → timer (goToTechniqueStep at index.html:786 sends every cause to the task step afterwards).
- [ ] **Fear commit screen replaces "Ready to start?" on the anxiety path.** Build it as the last stage of the fear flow, after the breath. Keep "Ready to start?" (index.html:493) for the other causes, or make cause-specific versions later.
- [ ] **"Not sure" gets its own screen [26].** Today it jumps straight to the task step (index.html:805). Replace with a page asking "Which of these do you think would help most now?" showing the four techniques, then route to the chosen one.
- [ ] **Tiredness becomes a choice of one activity [18, 19].** Replace the fixed three-stage sequence in FATIGUE_STAGES (index.html:980) with four option cards shown before the timer: Quick stretch, Quick exercise (e.g., jumping jacks), Splash cold water on your face, Energetic breathing. The chosen activity runs one timer, then the "feeling better?" question. Energetic breathing needs an on-screen safety note: do it sitting down, never near water, it can cause lightheadedness; fast breaths with the inhale longer than the exhale (quick exhale, slower inhale, repeated). Spencer also suggested energetic music for tiredness [23]; consider it as a fifth card or swap it in.
- [ ] **Drop the "Take 5 deep breaths" stage [19].** Deep breathing can make a tired person sleepier. If a water stage survives the redesign, change "Drink some water." to "Drink some water or have some caffeine."

## Global

- [ ] **Button placement [9, 21].** Forward button toward the right edge of the card, back link on the left, on every screen. Change `.btn-row` (index.html:191) to `justify-content:space-between` and swap the button order in each row: fear 311-312 and 326-327, motivation 368-369 and 381-382, distraction 456-457, task 469-470, action 486-487, confirm 501-502.
- [ ] **Rename "← choose a different cause" to "← Back"** everywhere (index.html:312, 369, 433, 457).
- [ ] **Skip timer buttons [20].** Give them a right arrow ("Skip →") and make them jump straight to the next page. Today the fear and fatigue skips only zero the clock and reveal a Next button (fearSkipTimer at 913, fatigueSkipTimer at 1063). The main timer's skip (1247) already advances.
- [ ] **Timer digits overflow the ring [22].** "09:57" at 64px bold (`.clock`, index.html:212) spills outside the 180px ring. Use about 40px for mm:ss (or shrink when the text is 5 characters) and add `font-variant-numeric: tabular-nums`.
- [ ] **Cause names [6].** Rename the five causes in CAUSES (index.html:578-605): Anxiety, Low motivation, Tiredness, Difficulty focusing, Not sure. Update the technique headings to match (303, 356, 389, 439).

## Intro modal (index.html:275-282)

- [ ] **Replace the intro copy [1]** with Spencer's: "This is a Clearer Thinking prototype, and we're excited to have you try it! When you're procrastinating or stuck on something, this tool is here to help you move forward fast with a quick technique matched to what's holding you back. Come back when the timer's done, and do it again. An owl keeps you company and grows a little more with every round." His version drops the step-by-step description and "No account, no judgment."

## Cause screen (index.html:295-299)

- [ ] **Title [2]** (296): "What's keeping you stuck right now?" (fits on one line).
- [ ] **Subtitle [2]** (297): delete it, or cut to one line, e.g., "Pick whichever feels closest. You can pick differently next round."
- [ ] **"Not sure" label [3, 6].** Spencer first proposed "Not sure or a bit of everything", then in his full list just "Not sure". Use "Not sure" (the later, fuller suggestion).
- [ ] **Fear card becomes "Anxiety" [6, 7].** Spencer likes the shield-with-lightning icon but says the category is really general anxiety or fear, and the interventions already fit that. After renaming, swap the icon for something that reads as anxiety rather than defense.
- [ ] **Focus card icon [5].** The phone-with-dots icon for "Can't stay focused" is confusing. Replace it (a target/crosshair or scattered-dots icon would read better) alongside the rename to "Difficulty focusing".

## Anxiety (fear) technique (index.html:302-352)

- [ ] **Heading** (303): "Anxiety or fear: a one-minute technique", or whatever the card ends up saying.
- [ ] **Chip list [8]** (FEAR_PRESETS, index.html:821): replace "Fear of the unknown" with "Fear of bad news".
- [ ] **Prefill vs body location [11].** The prompt asks you to notice where in your body you feel it, but clicking a chip fills only "Fear of failing". Either prefill "Fear of failing, felt in my " with the cursor at the end, or split the instruction so the body part is think-only ("Notice where in your body you feel it. No need to write it down."). Recommend the second: less typing on a phone.
- [ ] **Fact-or-thought question [12]** (319): "Is the anxious thought that's on your mind a fact or just a subjective interpretation?" Update the chip labels to match ("It's a fact" / "It's an interpretation").
- [ ] **Reflection responses [13]** (886-888). Spencer found the response unconvincing. His screenshot shows the fact/thought chips, so this is the text that appears after choosing. The "It's a fact" reply is the weak one ("even feelings that feel like facts are usually just thoughts we haven't questioned yet"). Rewrite both. For "fact", acknowledge that the outcome might really be bad, then point out that one small step is still possible and that acting gives better information than avoiding.
- [ ] **Breath instruction [14]** (332): "Take one deep inhale and one deep exhale."
- [ ] **Commit screen** (new, see Decide first): after the breath, show "You can start on the task even though it makes you anxious. Will you work on this task now?" with "Yes, start the 10 minute timer →" and "No, I'm going to keep avoiding it". Decide what "No" does (suggest: back to the cause screen with a gentle line).

## Low motivation technique (index.html:355-385)

- [ ] **Heading** (356): "Low motivation: a one-minute technique".
- [ ] **Contradiction [9]:** delete "Picture for a few seconds how good it'll feel once this is done." (359) and make the rating question (360) about finishing: "From 1 to 10, how good will it feel once this is done?"
- [ ] **Milestone prompt [10]** (365): "What's one tiny step you could take right now that's on the path toward getting this done?" Watch out: this is the same wording Spencer proposed for the action page [16]. After the reorder (action before technique) the optional milestone field becomes redundant. Recommend dropping the field and keeping only the rating question and the "worth a small time investment?" step.

## Tiredness technique (index.html:388-435)

- [ ] **Heading** (389): "Tiredness: a one-minute technique".
- [ ] Redesign per Decide first: four option cards [18], remove deep breaths [19], water or caffeine [19], optional energetic music [23].
- [ ] Show the stretch illustrations (393-408) only for the Quick stretch option; add simple ones for jumping jacks, cold water, and breathing if time allows.

## Difficulty focusing (distraction) technique (index.html:438-459)

- [ ] **Stuck page bug [25].** Next stays disabled until all three boxes are checked (updateDistractionNextState, index.html:1073). Spencer ticked one and could not proceed. Enable Next once at least one box is checked, or always, with the boxes as suggestions.
- [ ] **Merge phone and notifications [24]:** replace items 1 and 2 (444, 448) with "Put your phone in another room or silence all notifications." and "Close all extra windows and tabs."
- [ ] **Add "Put on music with no lyrics." [23]**
- [ ] **Heading** (439): "Difficulty focusing: a one-minute technique".

## Task screen (index.html:462-472)

- [ ] Move it to be the first page after the intro [15] (see Decide first). No copy changes were requested.

## Action screen (index.html:475-490)

- [ ] **Title [16]** (477, and the first-round string in goToActionStep at 1174): "What's one tiny step you could take right now that's on the path toward getting this done?" Align the later-round variant too, e.g., "What's the next tiny step you could take in the next 10 minutes?"
- [ ] **AI button grammar [17]** (482): "Suggest me with AI" → "Suggest with AI" or "Get an AI suggestion".

## Confirm screen (index.html:493-503)

- [ ] Replaced by the fear commit screen on the anxiety path; keep it for the other causes. Apply the global button placement fix.

## No edit needed (praise)

- [4] Four-button cause format. [8] Easy-to-click chips. [23] The distraction checklist itself.

## After the edits

- [ ] Push to GitHub Pages and re-test every cause end to end, including "Not sure", at phone width.
- [ ] Reply on the "Unstuck prototype" thread and give Travis the go-ahead to review (Spencer asked him to wait for that).
