# GuidedTrack Reference

Every Clearer Thinking tool is built on **GuidedTrack** (GT) — a no-code/low-code platform for quizzes, surveys, experiments, and self-help apps. This file is a working reference for debugging existing tools and understanding how things hang together.

**Canonical docs**: https://docs.guidedtrack.com/ — three main sections:
- **Manual** (https://docs.guidedtrack.com/manual/) — conceptual walkthrough
- **Function & Keyword API** (https://docs.guidedtrack.com/api/) — full syntax reference
- **Research Guide** — survey/experiment design advice

Always link out for definitive syntax. This file is a compact map.

---

## Source code for any CT tool

Every tool's edit URL is in the Airtable record under the field `GT Edit Program Code URL` (format: `https://www.guidedtrack.com/programs/{id}/edit`). See [CT_TOOLS.md](CT_TOOLS.md) for the index. Preview URLs use the format `https://www.guidedtrack.com/programs/{id}/preview`.

---

## Language basics

GT programs are plain text files with line-prefixed commands:

| Prefix | Meaning |
|---|---|
| `*command` | A GT command (`*question`, `*if`, `*goto`, etc.) |
| `>> variable = value` | Variable assignment |
| `(plain text)` | Displayed to the user as-is |
| Indentation | Defines blocks (like Python — children of `*if`/`*for` etc. are indented) |
| `{{variable}}` | Interpolates a variable into displayed text |

Variables are dynamically typed: text, number, collection (list), association (dict/map), date/time.

---

## Asking questions (most common task)

```
*question: How are you feeling today?
  *type: choice
  *save: mood
  *answers
    Great
    Okay
    Bad
```

Key sub-keywords:
- `*type:` — `text`, `number`, `choice`, `checkbox`, `calendar`, `slider`, `ranking`, `paragraph`, `captcha`
- `*save: varName` — store the answer
- `*answers: someList` — inject options from a variable
- `*shuffle` — randomize option order
- `*confirm` — require explicit "Next" click
- `*blank` — let user skip
- `*throwaway` — don't write to the CSV output
- `*tip:` — hint below the question
- `*placeholder:` — input placeholder
- `*before:` / `*after:` — prepend/append to input (currency `$`, units, etc.)
- `*min:` / `*max:` — for sliders / number inputs
- `*other` — allow "Other" with free text on choice questions
- `*countdown: 30.seconds` — timed responses
- `*searchable` — autocomplete-style choice picker
- `*multiple` — multi-text answers
- `*time: yes` / `*date: yes` — for calendar questions

---

## Control flow

```
*if: mood = "Great"
  Great to hear!
*if: mood = "Bad"
  Sorry to hear that.
```

| Command | Use |
|---|---|
| `*if: condition` | Conditional block |
| `*while: condition` | Loop while true |
| `*for: i, v in collection` | Loop over a collection/association/text |
| `*repeat: n` | Loop n times |
| `*label: name` + `*goto: name` | Jump to a labeled section |
| `*return` | Exit current subprogram, resume parent |
| `*quit` | End entire program immediately |

---

## Randomization & experiments

```
*experiment: ButtonColor
  *group: red
    *button: Continue
      *classes: red-button
  *group: blue
    *button: Continue
      *classes: blue-button
```

- `*randomize` / `*randomize: n` / `*randomize: all` — randomly pick blocks
- `*experiment: name` — same but guarantees equal group distribution
- `*group: name` — block inside randomize/experiment
- `*everytime` — re-randomize on each visit

---

## Scoring & tagging

```
*question: ...
  *tags: anxiety
  *answers
    Never
      *points: 0 anxiety
    Sometimes
      *points: 1 anxiety
    Always
      *points: 3 anxiety
```

- `*points: n` — award points
- `*points: n tagName` — tagged points (sum per tag, used for sub-scales)
- `*tags: tagList` — group related questions
- `*summary: tagName` — display aggregated responses for that tag

---

## Page layout & components

| Command | Use |
|---|---|
| `*page` | Group content onto a single page |
| `*button: text` | Clickable button |
| `*maintain: text` / `*clear` | Keep text in gray box across pages |
| `*component` | Bordered content box (combine with `*classes`, `*click`) |
| `*classes: cls1, cls2` | Apply CSS classes |
| `*list` / `*list: ordered` / `*list: expandable` | Lists |
| `*html` | Raw HTML escape hatch |
| `*image: url` (+ `*caption`, `*description`) | Image |
| `*video: youtubeUrl` | YouTube embed |
| `*audio: url` (+ `*start`, `*hide`) | Audio embed |
| `*chart` (+ `*type`, `*data`, `*xaxis`, `*yaxis`, `*trendline`) | Bar/line/scatter charts |
| `*progress: 75` | Progress bar |
| `*navigation` (+ `*name`, `*icon`) | Nav bar |

---

## Multi-program / subprograms

| Command | Use |
|---|---|
| `*program: name` | Include subprogram, resume parent after |
| `*switch: name` | Permanently switch to another program |
| `*reset` (with `*switch`) | Restart target from beginning |
| `*settings` | Configure program (e.g., `*back: yes`, `*menu: no`) |

---

## Email & scheduled messages

```
*email
  *to: {{user_email}}
  *subject: Your results
  *body
    Here is your report...
  *when: calendar::now + 1.day
```

- `*every: 1.week`, `*until: ...`, `*identifier: name`, `*cancel: name` — recurring emails

---

## API integrations

```
*service: mailchimp
  *path: /lists/abc/members
  *method: POST
  *send
    email_address = {{user_email}}
    status = "subscribed"
  *success
    *set: subscribed
  *error
    Could not subscribe.
```

Services are configured per-program in GT settings. Use `*service:` to call them.

---

## Events & triggers

```
*events
  emailed_report_strong_subscribe
    >> ct_strong_subscriber = true
    *trigger: another_event
*startup
  >> session_start = calendar::now
```

- `*events` — define named handlers
- `*startup` — fires on program load
- `*trigger: eventName` — invoke asynchronously
- `*send: someAssociation` — payload (available as `it` inside handler)

⚠️ **CT-specific**: per the Airtable schema, the trigger `emailed_report_strong_subscribe` is meaningful in our funnel — it indicates a user who received a report and opted in. The Airtable field "Includes change page trigger" tracks which tools fire this.

---

## Data functions cheat sheet

**Text**: `.clean`, `.count(x)`, `.find(x)`, `.size`, `.split(d)`, `.lowercase`, `.uppercase`, `.encode("URL"|"JSON")`, `.decode(...)`

**Number**: `.round`, `.round(n)`, `n.seconds`/`n.days`/etc. for durations

**Collection**: `.add(x)`, `.combine(c)`, `.count(x)`, `.find(x)`, `.insert(x, pos)`, `.remove(pos)`, `.erase(x)`, `.max`, `.min`, `.mean`, `.median`, `.size`, `.sort("increasing"|"decreasing")`, `.shuffle`, `.unique`

**Association** (dict): `.keys`, `.remove(key)`, `.erase(value)`, `.encode("JSON")`

**Date/time**: `calendar::date`, `calendar::now`, `calendar::time`, `duration.to("days"|"hours"|...)`

**Type**: `any.text` (coerce to text), `any.type` (introspect)

**CSV output**: `data::store(columnName, value)`

---

## Common patterns in CT tools

All our tools follow roughly the same shape (the funnel mirrored in [GA4_EVENTS.md](GA4_EVENTS.md)):

1. **Privacy notice page** — first page shown → fires `Viewed Privacy Policy` in GA4
2. **CTA / "Start" button** — clicking it fires `Accepted Privacy Policy`
3. **Quiz body** — `*question` blocks, often with `*tags` and `*points` for scoring
4. **Email gate** — fires `Reached Email Ask`, then `Submitted Email` on submission
5. **Report page** — typically built from `*summary: tag` and scored variables
6. **End cards** — final upsell/share screen, fires `Finished Exercise`

When debugging a tool, the GA4 event funnel + the GT preview URL + the edit URL are usually all you need.

---

## Debugging tips

- **Preview a tool** before editing: `https://www.guidedtrack.com/programs/{id}/preview`
- **Edit URL** is in the Airtable record (`GT Edit Program Code URL`)
- **CSV export** of responses is available from the GT program admin — use this to verify which fields are being saved
- **`*throwaway`** on a question means responses **won't** appear in CSV exports — don't be surprised when they're missing
- **Indentation matters** — most syntax bugs in GT are accidentally wrong indent levels under `*if`, `*for`, `*question`, etc.
- **Variables are case-sensitive** and don't need declaration — typos silently create new empty vars
- **`{{var}}` in plain text** is the interpolation syntax — bare `var` won't render
- **`*if: var = "x"`** uses single `=` (not `==`) for comparison
- **Date math** — durations like `5.days` are first-class; use `calendar::now + 1.day`
- **GA4 events** are fired by tool-side instrumentation; if an event isn't firing, check whether the tool actually reached that step (preview it through)
- **API/service failures** — wrap with `*success` / `*error` blocks; without them, errors fail silently
