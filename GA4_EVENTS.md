# GA4 Events Reference

What each custom GA4 event means and how Igor uses them in analysis. Always interpret event names per the definitions below — the GA4 event names don't always match what they functionally measure.

## The tool funnel

Every Clearer Thinking tool follows roughly this user path. Each step has its own GA4 event:

| Step | GA4 event | What it actually means |
|---|---|---|
| 1. Land on tool | `Viewed Privacy Policy` | Triggered every time someone lands on a tool page (the privacy notice is shown by default). **Use this as "tool landings", not "tool starts".** |
| 2. Start the tool | `Accepted Privacy Policy` | Triggered when the user clicks the CTA on the first page to begin. **This is the canonical "started a tool" metric.** When Igor says "how many people started a tool", he means this event. |
| 3. Reach the email gate | `Reached Email Ask` | The user got far enough into the tool to be asked for their email. Self-explanatory. |
| 4. Submit email (functional "finished") | `Submitted Email` | The user submitted their email after going through all the questions. **Used as the "finished tool" metric** — even though there's a separate `Finished Exercise` event — because reaching this point means the user got through the whole quiz. This is what `Modules Finished` in the dashboard maps to. |
| 5. Reach the very end | `Finished Exercise` | Fires when the user reaches the actual final screen of the tool (after the email submit). Rarely used in analysis. |

## How these map to the dashboard

In [data_layer.py](data_layer.py) (`ga4_audience_metrics`):

| Dashboard metric | GA4 event | Notes |
|---|---|---|
| `modules_started` | `Viewed Privacy Policy` | ⚠️ **Mislabeled** — this is actually tool *landings*, not starts. Real "started" events are `Accepted Privacy Policy`. Worth renaming. |
| `modules_finished` | `Submitted Email` | Correct (per Igor's definition that submit = functional finish). |

## Common funnel ratios worth tracking

- **Landings → Starts**: `Accepted Privacy Policy` / `Viewed Privacy Policy` — measures how compelling the tool's intro/CTA is.
- **Starts → Email reach**: `Reached Email Ask` / `Accepted Privacy Policy` — measures drop-off mid-quiz.
- **Email reach → Submit**: `Submitted Email` / `Reached Email Ask` — measures email-gate friction (this is where the actual conversion happens).
- **Starts → Finish**: `Submitted Email` / `Accepted Privacy Policy` — overall tool completion rate.
