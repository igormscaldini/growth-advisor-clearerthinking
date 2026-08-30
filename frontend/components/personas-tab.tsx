"use client";

/*
 * Three audience personas for Clearer Thinking, synthesized from:
 *  - the March 2026 audience survey (~540 respondents; 160 to 190 answers per question)
 *  - the coaching-interest survey (276 respondents, Aug 2026)
 *  - the Paths quiz export (20,201 runs, 2023 to 2026)
 *  - the cross-source buyer/engagement profile (Stripe + beehiiv + GA4, Jun 2026)
 *  - the Communication and Content Writing Guidelines
 * Static content: edit this file to update the personas.
 */

interface Persona {
  name: string;
  tagline: string;
  share: string;
  color: string;
  who: string[];
  wants: string[];
  blockers: string[];
  path: string[];
  money: string[];
  voice: string[];
  evidence: string[];
}

const PERSONAS: Persona[] = [
  {
    name: "The Curious Self-Improver",
    tagline: "Wants to understand themselves and get better at life, with evidence, not vibes.",
    share: "Largest group, roughly half of the engaged audience and most buyers",
    color: "border-t-green-600 dark:border-t-green-400",
    who: [
      "Lifelong learner (80% of survey respondents pick this identity), self-improvement and science enthusiast, often a writer or health enthusiast on the side.",
      "Mid-career professional or retiree, college-educated, mostly in the US, Canada, UK and Australia.",
      "Politically mixed: about six in ten lean progressive, but a real conservative minority reads too, so neutrality is not optional.",
    ],
    wants: [
      "Top goals: become a better version of myself (55%), get better at figuring out the truth on complex issues (45%), improve mental health (41%), become a better decision maker (34%).",
      "Favourite formats: personal assessments (68%) and thinking-skill developers (66%), then topic quizzes and interpersonal-skill tools.",
      "Weekly email cadence (48%), short practical insights; One Helpful Idea and the interactive tools tie as the most valued products.",
    ],
    blockers: [
      "Procrastination (51%), lack of motivation (40%), poor focus (38%), time management (38%). Ambition is not the problem; follow-through is.",
      "Trust wobbles when sourcing is thin or a tool feels like a slow, dated flow next to modern AI products.",
    ],
    path: [
      "Arrives through self-insight tools: Ultimate Personality Test, Intrinsic Values Test, How Rational Are You. These feed the most engaged subscribers (Intrinsic Values readers open at 41%).",
      "Finds CT via organic search (about 20% of tool finishers), referrals and the newsletter itself.",
    ],
    money: [
      "The buyer. The $9 Personality PDF is the entry purchase (50% of buyers); 14% buy again; median order $9, mean $44.",
      "Engaged subscribers (opens above 40%) buy at 2.2x the rate of unengaged ones, yet only 25% of buyers are on the newsletter: the biggest untapped conversion lever.",
    ],
    voice: [
      "Talk directly to them (\"you can...\"), lead with the benefit, deliver value inside the email before any click.",
      "Give a checklist, framework or reflection questions they can apply the same day; explain, do not persuade.",
    ],
    evidence: ["Audience survey Mar 2026", "Buyer profile Jun 2026", "Paths quiz (n=20,201)"],
  },
  {
    name: "The Rigorous Rationalist",
    tagline: "Reads CT the way they read LessWrong or 80,000 Hours: for careful thinking, and they will notice if it slips.",
    share: "A vocal minority, about a quarter to a third of respondents, over-represented among CT+ members, podcast listeners and sharers",
    color: "border-t-blue-600 dark:border-t-blue-400",
    who: [
      "Rationalist or aspiring to be one (34%), Effective Altruist (25%), philosopher (20%), academic, researcher or technologist.",
      "Compares CT to 80,000 Hours, LessWrong, Astral Codex Ten and Hidden Brain; often already in those communities.",
      "Skeptical by default: questions small effect sizes, wants citations, methods and transparency about expertise.",
    ],
    wants: [
      "Content they asked for by name: how to actually change people's minds (52%), developing a scout mindset (47%), forecasting skills, rationally assessing risk, what is true about intelligence and IQ.",
      "Rigor plus application: real-world examples that show a technique works, deeper resources to follow, primary-source literacy.",
      "Diverse expert voices beyond Spencer, transcripts instead of video, and open or privacy-respecting tools.",
    ],
    blockers: [
      "Paywalls read as off-mission; anything that looks like a generic wellness startup erodes credibility.",
      "Finds CT hard to share: friends \"don't like having their irrationalities pointed out\", and the content feels too niche or academic for wider circles.",
      "Most likely to be a detractor when quality dips: the audience NPS is minus 6, polarized between promoters (30%) and detractors (36%).",
    ],
    path: [
      "Arrives through argument-and-reasoning tools (Faulty Reasoning Quiz, Nuanced Thinking Techniques), the podcast and Spencer's essays.",
      "Abstract tools such as Predict Correlations bring them in but produce low-engagement subscribers (17% opens), so they are better as retention content than as front doors.",
    ],
    money: [
      "Buys the Cognitive Assessment ($17.50 / $35, 27% of buyers) and is the natural Clearer Thinking Plus member, if membership feels like supporting the mission rather than a paywall.",
      "Only 30% of survey respondents knew CT+ existed: awareness, not willingness, is the first gap.",
    ],
    voice: [
      "Show the evidence and the uncertainty; never talk down or claim to be the better thinker.",
      "Balance any politically loaded example with one from the other side; explain what you believe and why, then let them decide.",
    ],
    evidence: ["Audience survey Mar 2026", "Buyer profile Jun 2026", "Communication guidelines"],
  },
  {
    name: "The Overwhelmed Striver",
    tagline: "Arrives stressed, stuck or between chapters, looking for something that helps this week.",
    share: "A large share of new sign-ups and Paths quiz takers; smallest share of revenue today",
    color: "border-t-amber-500 dark:border-t-amber-400",
    who: [
      "Students, early-career and not-currently-employed readers (31% of survey respondents are not employed; 20% are students), plus anyone in a rough patch.",
      "Global: India is about 25% of tool sign-ups but close to 0% of revenue; many use a personal address and a phone.",
      "Reports anxiety (37%), low mood (30%), career uncertainty (40%) and low self-discipline alongside procrastination.",
    ],
    wants: [
      "Therapeutic tools and wellbeing improvers, bite-sized content, and tools that name the problem: increase focus (47%), avoid emotional overwhelm (43%), reduce self-criticism (38%), a daily-intention program.",
      "Human help: 88% of coaching-survey respondents were likely or very likely to try CT coaching, favouring problem-solving (30%), values (27%) and behavioral (26%) coaching, every two weeks, at $50 to $99 per session.",
      "Paths quiz priorities put better decisions (3.2 of 4), effective plans (3.1) and understanding yourself (3.1) first.",
    ],
    blockers: [
      "Execution, not insight: procrastination is the number one problem in every dataset, so \"more to read\" backfires.",
      "Low disposable income and passive consumption: reads when the email arrives, rarely seeks CT out, unsubscribes when volume feels like pressure.",
    ],
    path: [
      "Arrives through paid and cross-network campaigns (24% of tool finishers) and mood or productivity tools; many hit the email gate and stop.",
      "Converts to a subscriber but engages below the 30% baseline unless the first tool was about self-insight.",
    ],
    money: [
      "Rarely buys today. The realistic offers are coaching, a low-price accountability product, or CT+ once they have felt a win.",
      "Optimize for their engagement and outcomes rather than counting them as growth: raw sign-ups from this group inflate the funnel without moving revenue goals.",
    ],
    voice: [
      "Nuanced and optimistic, with encouragement and practicality; a meaningful slice arrives in distress, so tone carries duty of care.",
      "Add value in under three minutes, one concrete next step at a time; avoid anything prescriptive or that sounds like a lecture.",
    ],
    evidence: ["Audience survey Mar 2026", "Coaching survey Aug 2026 (n=276)", "Paths quiz (n=20,201)", "Buyer profile Jun 2026"],
  },
];

function Section({ title, items }: { title: string; items: string[] }) {
  return (
    <div>
      <h4 className="text-[11px] font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-400 mb-1.5">{title}</h4>
      <ul className="space-y-1.5 text-sm text-zinc-700 dark:text-zinc-300 leading-snug">
        {items.map((t, i) => (
          <li key={i} className="pl-3 relative before:content-[''] before:absolute before:left-0 before:top-2 before:w-1.5 before:h-1.5 before:rounded-full before:bg-zinc-300 dark:before:bg-zinc-600">
            {t}
          </li>
        ))}
      </ul>
    </div>
  );
}

export function PersonasTab() {
  return (
    <div className="space-y-6">
      <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-950 p-5 shadow-sm">
        <h2 className="text-lg font-bold">Who we are talking to</h2>
        <p className="mt-2 text-sm text-zinc-600 dark:text-zinc-400 max-w-3xl">
          Three personas that cover most of the Clearer Thinking audience. They share a core (curious, introspective,
          evidence-driven, college-educated) but differ in what they want from us, what blocks them, and whether they pay.
          Use them to sanity-check a tool, a campaign or an email: which persona is it for, what does that persona
          need to hear, and does it move a goal? Shares are estimates from self-reported survey data, not measurements.
        </p>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        {PERSONAS.map((p) => (
          <article
            key={p.name}
            className={`rounded-xl border border-zinc-200 dark:border-zinc-800 border-t-4 ${p.color} bg-white dark:bg-zinc-950 p-5 shadow-sm flex flex-col gap-4`}
          >
            <header>
              <h3 className="text-base font-bold">{p.name}</h3>
              <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400 italic">{p.tagline}</p>
              <p className="mt-2 text-xs text-zinc-500 dark:text-zinc-400">{p.share}</p>
            </header>
            <Section title="Who they are" items={p.who} />
            <Section title="What they want" items={p.wants} />
            <Section title="What blocks them" items={p.blockers} />
            <Section title="How they find us" items={p.path} />
            <Section title="How they pay (or don't)" items={p.money} />
            <Section title="How to talk to them" items={p.voice} />
            <footer className="mt-auto pt-2 border-t border-zinc-100 dark:border-zinc-900 text-[11px] text-zinc-400 dark:text-zinc-500">
              Sources: {p.evidence.join(" · ")}
            </footer>
          </article>
        ))}
      </div>

      <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-950 p-5 shadow-sm text-sm text-zinc-600 dark:text-zinc-400">
        <h3 className="text-sm font-semibold text-zinc-700 dark:text-zinc-300 mb-2">What this means for the goals</h3>
        <ul className="space-y-1.5 leading-snug">
          <li>Revenue and subscribers come from the Curious Self-Improver first: lead acquisition with Personality and Intrinsic Values tools, and get the 75% of buyers who never subscribe onto the newsletter.</li>
          <li>The Rigorous Rationalist is the Clearer Thinking Plus and Cognitive Assessment upside, and the loudest critic: sourcing, transparency and neutrality protect the NPS.</li>
          <li>The Overwhelmed Striver is where coaching and follow-through products fit; count them by engagement and outcomes, not by sign-ups, so the funnel does not flatter itself.</li>
        </ul>
      </div>
    </div>
  );
}
