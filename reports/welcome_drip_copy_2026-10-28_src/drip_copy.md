# New Subscribers drip: personalized copy

Draft for review. Source: `reports/welcome_drip_copy_2026-10-28_src/drip_copy.md` in the Growth Advisor repo.

## How to use this document

**Which field to personalize on.** Use the custom field **Last Tool Tried** (`last_tool_tried`). It is filled for 98% of new sign-ups with the tool's display name. "First Tool Tried" is empty on every sign-up since it was created, so do not use it.

**Exact values seen on the last 30,000 sign-ups** (share of Oct 24 to 28, after the viral spike): Who Attracts You (45 to 70%), The Ultimate Personality Test (about 80 a day), How Rational Are You, Really? (about 50), Philosophical Beliefs (about 35), Intrinsic Values Test (about 30), Unique Traits Test (about 12), The Value Of Your Time Calculator (about 3), blank (about 3%), everything else (about 5%).

**Email 1 is branched; Emails 2 to 4 are single emails with a merge tag.** A beehiiv multi-split branch takes up to 5 paths plus "All others", so Email 1 needs two nested splits on Last Tool Tried:

1. Split A (equals): Who Attracts You / The Ultimate Personality Test / How Rational Are You, Really? / Philosophical Beliefs / Intrinsic Values Test / All others
2. Split B inside "All others" (equals): Unique Traits Test / The Value Of Your Time Calculator / All others (the generic version, which also covers blanks)

**Merge tag.** Emails 2 to 4 refer to the tool with the Last Tool Tried merge tag inside quotation marks, so every tool name reads naturally ("Who Attracts You", "How Rational Are You, Really?"). The exact tag is `{{last_tool_tried | one of our tools}}`: the text after the bar is the fallback for the 3% of blanks (field names are case-sensitive; merge tags also work in subject lines).

**Links.** Every coaching link carries `utm_source=beehiiv&utm_medium=email&utm_campaign=welcome_coaching&utm_content=<path>` so GA4 shows which variant sends people to /coaching. The session clip is https://youtu.be/oqyw8872x0E.

**Two things to fix in the live automation regardless of this copy.**

- The last link of the live "Big news" email ("give it a try") is a mangled URL that starts with `https://www.clearerthinahttps://...` and lands on a dead page. 140 people have clicked it so far.
- "Big news" is also step 2 of the live "[Drip Campaign] Tried Attraction Study" automation, and every Who Attracts You sign-up matches that segment and the New Subscribers trigger. Both automations sent about 30,000 copies in the last 7 days. Keep it in one place only.

**Why the rewrite.** "Big news" loses 1.34% of recipients to unsubscribes (versus 0.21 to 0.26% for the other two drip emails) and sends 0.2% to /coaching. The new subject lines promise a continuation of what the reader did yesterday, the opening names a problem the tool just surfaced, the price is framed as under $50 a session (the band 72% of readers said they would pay in the 2024 coaching survey), and the "trained psychology graduates" line pre-empts the "life coach selling obvious tips" image that came up in the same survey.

---

## Email 1 (24 hours after sign-up): coaching, one version per tool

Shared frame: Spencer, first person. Only the subject, preview text, opening and bullet list change between paths. Button text is the same everywhere: **See how coaching works**.

### 1A. Path: Last Tool Tried equals "Who Attracts You"

**Subject:** Knowing your type is the easy part
**Preview text:** The part of dating that a report can't do for you.
**Coaching link:** https://www.clearerthinking.org/coaching?utm_source=beehiiv&utm_medium=email&utm_campaign=welcome_coaching&utm_content=who_attracts_you

Hi there,

Spencer here again, from ClearerThinking.org. Thanks for taking [Who Attracts You](https://programs.clearerthinking.org/who_attracts_you_study.html) yesterday.

Your report shows which aspects of physical appearance predict who you find attractive. That is a genuinely new thing to know about yourself. But I want to be honest about what it can't do. It can't help with the part of dating and relationships that actually decides how things go: starting a conversation with someone you like, handling a "no" without taking it personally, the nerves before a first date, or noticing why your relationships keep following the same pattern. Those are skills, and they are much easier to build with someone in your corner.

That gap, between knowing something about yourself and living differently because of it, is the reason we started offering one-on-one coaching. I tried the coaching myself before we partnered with Overcome, the organization that provides the coaches. They are trained psychology graduates who use methods drawn from cognitive behavioral therapy, acceptance and commitment therapy, and motivational interviewing. Sessions are practical: you leave each one with something specific to try before the next.

Whether you are dating right now or in a relationship, a coach can help you:

- feel less anxious meeting new people, online or in person
- stop avoiding the situations that could actually lead somewhere, like asking someone out or going to the event you keep skipping
- notice the pattern that keeps repeating in your relationships, and change your part in it
- build routines around sleep, work, and stress that leave you with energy for the rest of your life

It costs $99 a month for up to two 45-minute video sessions, which works out to under $50 a session. Your first session is usually within a week of signing up. You can cancel anytime and switch coaches anytime. And if after your first session it turns out that what you need is therapy rather than coaching, we will refund you.

If you want to see what a session is actually like before deciding, [here is a 15-minute clip from a real one](https://youtu.be/oqyw8872x0E).

[Button: See how coaching works]

Coaching is not therapy, and it is not meant for crises or specialist mental health treatment. But if you want practical help turning what you learned into something you actually do differently, I hope you will take a look.

Warmly,

Spencer Greenberg
Founder, ClearerThinking.org

### 1B. Path: Last Tool Tried equals "The Ultimate Personality Test"

**Subject:** Your traits are not the whole story
**Preview text:** What a personality report can't do for you.
**Coaching link:** https://www.clearerthinking.org/coaching?utm_source=beehiiv&utm_medium=email&utm_campaign=welcome_coaching&utm_content=personality_test

Hi there,

This is Spencer Greenberg, founder of ClearerThinking.org. Thanks for taking the [Ultimate Personality Test](https://programs.clearerthinking.org/personality-test.html) yesterday.

Your report describes your tendencies: how much you worry, how you handle deadlines, how much structure you want, how you recharge. What it can't do is decide what you do with them. Two people with the same scores can live very different lives, depending on whether they have learned to work with their patterns or are quietly run by them. In my experience the difference is rarely more self-knowledge. It is practice, and a second person to practice with.

That gap, between knowing something about yourself and living differently because of it, is the reason we started offering one-on-one coaching. I tried the coaching myself before we partnered with Overcome, the organization that provides the coaches. They are trained psychology graduates who use methods drawn from cognitive behavioral therapy, acceptance and commitment therapy, and motivational interviewing. Sessions are practical: you leave each one with something specific to try before the next.

A coach can help you:

- manage worry and stress instead of being managed by them
- set standards you can actually meet, if perfectionism turns small tasks into ordeals
- say no and hold a boundary without a week of guilt afterward
- reduce the avoidance, overthinking, or procrastination your report may have put a name to
- build habits and routines that fit your personality instead of fighting it

It costs $99 a month for up to two 45-minute video sessions, which works out to under $50 a session. Your first session is usually within a week of signing up. You can cancel anytime and switch coaches anytime. And if after your first session it turns out that what you need is therapy rather than coaching, we will refund you.

If you want to see what a session is actually like before deciding, [here is a 15-minute clip from a real one](https://youtu.be/oqyw8872x0E).

[Button: See how coaching works]

Coaching is not therapy, and it is not meant for crises or specialist mental health treatment. But if one of your traits is getting in the way of your work, your goals, your relationships, or your peace of mind, I hope you will take a look.

Warmly,

Spencer Greenberg
Founder, ClearerThinking.org

### 1C. Path: Last Tool Tried equals "How Rational Are You, Really?"

**Subject:** The problems a rationality test can't solve
**Preview text:** Most of them are follow-through problems.
**Coaching link:** https://www.clearerthinking.org/coaching?utm_source=beehiiv&utm_medium=email&utm_campaign=welcome_coaching&utm_content=rationality_test

Hi there,

This is Spencer Greenberg, founder of ClearerThinking.org. Thanks for taking [How Rational Are You, Really?](https://programs.clearerthinking.org/how_rational_are_you_really_take_the_test.html) yesterday.

Here is something I have learned from working with thousands of people who care about thinking well: some problems don't yield to clear thinking alone. You can understand procrastination perfectly and still procrastinate. You can know exactly which habit is holding you back and still not change it. Stress, low motivation, routines that collapse after two weeks: these usually aren't reasoning problems. They are follow-through problems, and a better argument won't solve them.

That gap, between knowing what to do and doing it, is the reason we started offering one-on-one coaching. I tried the coaching myself before we partnered with Overcome, the organization that provides the coaches. They are trained psychology graduates who use methods drawn from cognitive behavioral therapy, acceptance and commitment therapy, and motivational interviewing. Sessions are practical: you leave each one with something specific to try before the next.

A coach can help you:

- reduce procrastination and avoidance
- build habits and routines that survive past week two
- manage stress before it builds up
- turn a goal you keep circling into concrete weekly actions
- close the gap between what you know you should do and what you actually do

It costs $99 a month for up to two 45-minute video sessions, which works out to under $50 a session. Your first session is usually within a week of signing up. You can cancel anytime and switch coaches anytime. And if after your first session it turns out that what you need is therapy rather than coaching, we will refund you.

If you want to see what a session is actually like before deciding, [here is a 15-minute clip from a real one](https://youtu.be/oqyw8872x0E).

[Button: See how coaching works]

Coaching is not therapy, and it is not meant for crises or specialist mental health treatment. But if a stubborn pattern is getting in the way of your work, your goals, your relationships, or your peace of mind, I hope you will take a look.

Warmly,

Spencer Greenberg
Founder, ClearerThinking.org

### 1D. Path: Last Tool Tried equals "Philosophical Beliefs"

**Subject:** The gap between what you believe and how you live
**Preview text:** Examining your life is not the same as changing it.
**Coaching link:** https://www.clearerthinking.org/coaching?utm_source=beehiiv&utm_medium=email&utm_campaign=welcome_coaching&utm_content=philosophical_beliefs

Hi there,

This is Spencer Greenberg, founder of ClearerThinking.org. Thanks for taking the [Philosophical Beliefs quiz](https://programs.clearerthinking.org/philosophical_beliefs.html) yesterday, and for thinking carefully about questions most people never examine directly, from free will to what makes an action right.

Here is something curious about the examined life: examining it is not the same as changing it. You can hold a considered view about what matters, how you ought to treat people, or what a good life looks like, and still find your actual days shaped by something else entirely: the urgent over the important, habits you never chose, evenings that disappear without a trace. The gap between your beliefs about how to live and how you actually live doesn't close through more reflection alone.

That gap is the reason we started offering one-on-one coaching. I tried the coaching myself before we partnered with Overcome, the organization that provides the coaches. They are trained psychology graduates who use methods drawn from cognitive behavioral therapy, acceptance and commitment therapy, and motivational interviewing. Sessions are practical: you leave each one with something specific to try before the next.

A coach can help you:

- get clear on what you value most, and turn it into concrete weekly actions
- reduce procrastination and avoidance on the things that actually matter to you
- build habits and routines you would endorse on reflection
- manage stress and overthinking
- close the gap between the life you would argue for and the life you are living

It costs $99 a month for up to two 45-minute video sessions, which works out to under $50 a session. Your first session is usually within a week of signing up. You can cancel anytime and switch coaches anytime. And if after your first session it turns out that what you need is therapy rather than coaching, we will refund you.

If you want to see what a session is actually like before deciding, [here is a 15-minute clip from a real one](https://youtu.be/oqyw8872x0E).

[Button: See how coaching works]

Coaching is not therapy, and it is not meant for crises or specialist mental health treatment. But if that gap is getting in the way of your work, your goals, your relationships, or your peace of mind, I hope you will take a look.

Warmly,

Spencer Greenberg
Founder, ClearerThinking.org

### 1E. Path: Last Tool Tried equals "Intrinsic Values Test"

**Subject:** Knowing your values is the easy part
**Preview text:** A value trap is easier to spot than to climb out of.
**Coaching link:** https://www.clearerthinking.org/coaching?utm_source=beehiiv&utm_medium=email&utm_campaign=welcome_coaching&utm_content=intrinsic_values

Hi there,

This is Spencer Greenberg, founder of ClearerThinking.org. Thanks for taking the [Intrinsic Values Test](https://programs.clearerthinking.org/intrinsic_values_test.html) yesterday, and for stopping to work out what you care about for its own sake, which most people never do.

Here is what we have noticed, though: a value trap is much easier to spot than to climb out of. You can know perfectly well that you are pursuing something because other people call it valuable rather than because you do, and still keep pursuing it. You can see clearly that your weeks are filled with things that don't serve what you truly care about, and still watch next week fill up the same way. Rearranging your life around your real values is a different challenge from identifying them.

That gap, between knowing what you value and living by it, is the reason we started offering one-on-one coaching. I tried the coaching myself before we partnered with Overcome, the organization that provides the coaches. They are trained psychology graduates who use methods drawn from cognitive behavioral therapy, acceptance and commitment therapy, and motivational interviewing. Sessions are practical: you leave each one with something specific to try before the next.

A coach can help you:

- turn your top values into concrete goals and weekly actions
- step back from pursuits that look valuable but aren't actually yours
- let go of guilt about not wanting what others expect you to want
- reduce procrastination and avoidance on the things you care about most
- build habits and routines that create more of what you value

It costs $99 a month for up to two 45-minute video sessions, which works out to under $50 a session. Your first session is usually within a week of signing up. You can cancel anytime and switch coaches anytime. And if after your first session it turns out that what you need is therapy rather than coaching, we will refund you.

If you want to see what a session is actually like before deciding, [here is a 15-minute clip from a real one](https://youtu.be/oqyw8872x0E).

[Button: See how coaching works]

Coaching is not therapy, and it is not meant for crises or specialist mental health treatment. But if the gap between your values and your day-to-day life is getting in the way of your work, your goals, your relationships, or your peace of mind, I hope you will take a look.

Warmly,

Spencer Greenberg
Founder, ClearerThinking.org

### 1F. Path: Last Tool Tried equals "Unique Traits Test"

**Subject:** What to do with what you learned about yourself
**Preview text:** A name for a trait is a relief. It is not a change.
**Coaching link:** https://www.clearerthinking.org/coaching?utm_source=beehiiv&utm_medium=email&utm_campaign=welcome_coaching&utm_content=unique_traits

Hi there,

This is Spencer Greenberg, founder of ClearerThinking.org. Thanks for taking the [Unique Traits Test](https://programs.clearerthinking.org/unique-traits-test/) yesterday, and for exploring parts of your inner experience that most people never stop to examine.

Discovering a trait can be a relief, because it finally gives a name to something you may have assumed was just you. But a name, on its own, doesn't change much. You can know exactly what to call the worry that eats your evenings, the sounds that set you off, or the tendency to avoid things that matter to you, and still find yourself living with it the same way you did before.

That gap, between understanding a trait and living well with it, is the reason we started offering one-on-one coaching. I tried the coaching myself before we partnered with Overcome, the organization that provides the coaches. They are trained psychology graduates who use methods drawn from cognitive behavioral therapy, acceptance and commitment therapy, and motivational interviewing. Sessions are practical: you leave each one with something specific to try before the next.

A coach can help you:

- reduce worry, overthinking, or avoidance
- build habits and routines that work with your mind instead of against it
- manage stress before it builds up
- explain your differences to the people around you, at home or at work
- make progress on a goal that a stubborn pattern has been getting in the way of

It costs $99 a month for up to two 45-minute video sessions, which works out to under $50 a session. Your first session is usually within a week of signing up. You can cancel anytime and switch coaches anytime. And if after your first session it turns out that what you need is therapy rather than coaching, we will refund you.

If you want to see what a session is actually like before deciding, [here is a 15-minute clip from a real one](https://youtu.be/oqyw8872x0E).

[Button: See how coaching works]

Coaching is not therapy, and it is not meant for crises or specialist mental health treatment. But if something you saw in your report is getting in the way of your work, your goals, your relationships, or your peace of mind, I hope you will take a look.

Warmly,

Spencer Greenberg
Founder, ClearerThinking.org

### 1G. Path: Last Tool Tried equals "The Value Of Your Time Calculator"

**Subject:** The hours no calculator can get back
**Preview text:** Knowing what your hour is worth doesn't change what happens to your hours.
**Coaching link:** https://www.clearerthinking.org/coaching?utm_source=beehiiv&utm_medium=email&utm_campaign=welcome_coaching&utm_content=value_of_time

Hi there,

This is Spencer Greenberg, founder of ClearerThinking.org. Thanks for using the [Value of Your Time calculator](https://programs.clearerthinking.org/what_is_your_time_really_worth_to_you.html) yesterday, and for putting a real number on something most people only ever guess at.

Here is the catch with that number: knowing what your hour is worth doesn't change what happens to your hours. The biggest time losses usually aren't pricing mistakes, like waiting in the wrong line or skipping a worthwhile cab. They are patterns: the evenings that vanish into things you don't actually value, the commitments you couldn't say no to, the tasks you know you should hand off but keep doing yourself. A calculator can price those hours. It can't get them back.

That gap, between knowing what your time is worth and spending it that way, is the reason we started offering one-on-one coaching. I tried the coaching myself before we partnered with Overcome, the organization that provides the coaches. They are trained psychology graduates who use methods drawn from cognitive behavioral therapy, acceptance and commitment therapy, and motivational interviewing. Sessions are practical: you leave each one with something specific to try before the next.

A coach can help you:

- reduce procrastination and the time lost to avoidance
- get better at saying no to commitments that aren't worth your hours
- actually follow through on delegating, not just know you should
- build routines that protect your highest-value time
- spend less time overthinking decisions you could make quickly

It costs $99 a month for up to two 45-minute video sessions, which works out to under $50 a session. Your first session is usually within a week of signing up. You can cancel anytime and switch coaches anytime. And if after your first session it turns out that what you need is therapy rather than coaching, we will refund you.

If you want to see what a session is actually like before deciding, [here is a 15-minute clip from a real one](https://youtu.be/oqyw8872x0E).

[Button: See how coaching works]

Coaching is not therapy, and it is not meant for crises or specialist mental health treatment. But if the way your hours actually get spent is getting in the way of your work, your goals, your relationships, or your peace of mind, I hope you will take a look.

Warmly,

Spencer Greenberg
Founder, ClearerThinking.org

### 1H. Path: All others (every other tool, and blank)

**Subject:** The part our tools can't do for you
**Preview text:** Knowing is the easy part.
**Coaching link:** https://www.clearerthinking.org/coaching?utm_source=beehiiv&utm_medium=email&utm_campaign=welcome_coaching&utm_content=other_tools
**Merge tag:** uses Last Tool Tried with the fallback `one of our tools`.

Hi there,

This is Spencer Greenberg, founder of ClearerThinking.org. Thanks for trying "{{last_tool_tried | one of our tools}}" yesterday.

Our tools are good at one thing: showing you something true about yourself or about the way you think. They are much worse at the next step, which is changing what you actually do on a Tuesday afternoon. In my experience, most people don't need more information for that. They need a plan that fits their life, someone to be accountable to, and a second person to think it through with when they get stuck.

That gap, between knowing something and living differently because of it, is the reason we started offering one-on-one coaching. I tried the coaching myself before we partnered with Overcome, the organization that provides the coaches. They are trained psychology graduates who use methods drawn from cognitive behavioral therapy, acceptance and commitment therapy, and motivational interviewing. Sessions are practical: you leave each one with something specific to try before the next.

A coach can help you:

- reduce procrastination and avoidance on the things that matter to you
- build habits and routines that last
- manage stress before it builds up
- make progress on a goal that has been stuck for a while

It costs $99 a month for up to two 45-minute video sessions, which works out to under $50 a session. Your first session is usually within a week of signing up. You can cancel anytime and switch coaches anytime. And if after your first session it turns out that what you need is therapy rather than coaching, we will refund you.

If you want to see what a session is actually like before deciding, [here is a 15-minute clip from a real one](https://youtu.be/oqyw8872x0E).

[Button: See how coaching works]

Coaching is not therapy, and it is not meant for crises or specialist mental health treatment. But if you want practical help turning what you learned into something you actually do differently, I hope you will take a look.

Warmly,

Spencer Greenberg
Founder, ClearerThinking.org

---

## Email 2 (day 14): the Cognitive Assessment

Single email, no branch. Replaces "Does IQ actually matter?". The four findings are the ones in the current email, unchanged in substance; what is new is the opening and closing that tie it to the reader's tool.

**Subject:** Does IQ actually matter?
**Preview text:** We ran a study with 3,691 participants to find out.
**Assessment link:** https://programs.clearerthinking.org/cognitive-test-intro.html?utm_source=beehiiv&utm_medium=email&utm_campaign=welcome_cognitive_assessment

Hi there,

Two weeks ago you tried "{{last_tool_tried | one of our tools}}". Most of our tools, that one included, are about who you are: your traits, your values, the way you reason, what you are drawn to. Today I want to share something about a different question people ask us all the time: what does an IQ score really tell you about you?

To find out, [we ran a study on IQ with 3,691 participants](https://www.clearerthinking.org/post/what-s-really-true-about-intelligence-and-iq-we-empirically-tested-40-claims) and tested a wide range of claims about what IQ does and doesn't predict. Here are four findings that surprised our team.

**1) Perfectionism doesn't seem to be a sign of high IQ**

There is a familiar cultural image of the brilliant perfectionist: the genius who obsesses over every detail. In our data, IQ had essentially no meaningful relationship with perfectionism. That doesn't prove there are no genius perfectionists, of course. But it does suggest that perfectionism, by itself, is not a useful clue that someone has a high IQ.

**2) IQ was much more related to high-school GPA than college GPA**

IQ scores were moderately correlated with high-school GPA, but barely correlated with college GPA. That may sound strange: why would IQ matter less once school gets harder? Maybe college success depends much more on motivation, self-regulation, and time management. Maybe college GPA is simply a noisier measure, because students take very different classes with very different grading standards. Or selection effects may be hiding the relationship, since colleges admit students who resemble each other. Whatever the explanation, it is a good reminder that data often allow for more than one plausible interpretation.

**3) People with higher IQ scores were less likely to think they could solve society's problems**

You might expect people with higher IQs to be more confident in their solutions to big problems. We found a small negative correlation between IQ and believing you could figure out solutions to societal problems. One possible explanation is that people with higher scores are more likely to see how complex those problems really are: more ability, in the domains IQ tests measure, may sometimes come with more humility about how hard the problem is.

**4) IQ matters much less than many people think**

IQ scores contain real information about someone's intelligence and performance at some tasks. They give you a reason to update your expectations, at least a little, about certain traits and outcomes. But any given IQ score is compatible with a wide range of traits, skills, and life outcomes. IQ is moderately predictive of some things. It is not destiny, and it is not a verdict on anyone's worth.

If you want the details, [the full report](https://www.clearerthinking.org/post/what-s-really-true-about-intelligence-and-iq-we-empirically-tested-40-claims) is on our blog, and I also made [a YouTube video about the study](https://www.youtube.com/watch?v=BxsIyHSoQW8) if you would rather watch than read.

Based on what we learned, we built a [Cognitive Assessment](https://programs.clearerthinking.org/cognitive-test-intro.html?utm_source=beehiiv&utm_medium=email&utm_campaign=welcome_cognitive_assessment) that goes beyond a single IQ score. It measures seven areas of cognitive ability and gives you learning and career suggestions tailored to your results. If "{{last_tool_tried | one of our tools}}" told you something about who you are, this one tells you something about how you think. Unlike almost all of our tools, it is not free: the proceeds support everything else we make.

[Button: Take the Cognitive Assessment]

Warmly,

Spencer Greenberg
Founder, ClearerThinking.org

---

## Email 3 (day 28): should you get a life coach?

Single email, no branch. Replaces "Should you have a life coach?". The five points are the current ones; the opening ties them to the reader's tool and is honest that this is the second time they hear about coaching from us.

**Subject:** Should you have a life coach?
**Preview text:** A fair look at whether coaching works, and how to tell a good coach from a bad one.
**Coaching link:** https://www.clearerthinking.org/coaching?utm_source=beehiiv&utm_medium=email&utm_campaign=welcome_coaching_evidence

Hi there,

About a month ago you tried "{{last_tool_tried | one of our tools}}", and a day later I wrote to you about our coaching program. Today I want to step back and ask a fairer question than "should you sign up": does life coaching actually work?

In theory, a coach can help you solve problems, provide support, and create accountability. But do people who receive coaching actually benefit? Since we started offering coaching, I thought it was worth taking a closer look. Below are a few ideas, taken from [our article on the subject](https://www.clearerthinking.org/post/does-life-coaching-actually-work), that I think are especially worth considering.

**1) "Coaching" is an extremely broad category**

Because coaching is largely unregulated, almost anyone can call themselves a coach. The term covers everything from thoughtful guidance and accountability to shallow advice to outright grifting. Asking whether coaching "works" is a bit like asking whether "medicine works" without saying which treatment, for which condition, from whom.

**2) There is some evidence that coaching can help**

The [research base](https://www.clearerthinking.org/post/does-life-coaching-actually-work) is still developing, but it does suggest that coaching can improve outcomes in areas like leadership, positive personality change, academic performance, and career development. That doesn't make coaching a magic solution. It does mean there are good reasons to consider it as part of a personal development plan.

**3) Coaching may be especially useful during transitions**

A new role, a major decision, or just the feeling that you are stuck and want to move forward more deliberately. When your current strategy isn't working, it helps to have someone thoughtful help you see blind spots, clarify goals, and build a better plan.

**4) Fit matters a lot**

A coach can be skilled and still be the wrong coach for you. Pay attention to whether your agendas are aligned, whether you feel understood, whether the coach listens well, and whether the conversations leave you feeling supported rather than judged or defensive. Coaching is not just about whether the coach is "good" in the abstract. It is about whether they are good for you, specifically.

**5) There are some simple green flags**

- A coach who gives you homework, or otherwise encourages action between sessions
- A coach who helps you build progress rather than dependency
- A coach who doesn't pressure you to buy expensive add-ons such as courses, retreats, or masterminds
- A coach who is willing to end the relationship once you have made the progress you came for

Those green flags are the standard we held our own program to. The coaches come from our partner Overcome, they set work between sessions, there are no add-ons to buy, and you can switch coaches or cancel at any time. If "{{last_tool_tried | one of our tools}}" showed you something you would like to change and you have not gotten around to it yet, [here is how our coaching works](https://www.clearerthinking.org/coaching?utm_source=beehiiv&utm_medium=email&utm_campaign=welcome_coaching_evidence).

Warmly,

Spencer Greenberg
Founder, ClearerThinking.org

---

## Email 4 (day 42, engaged readers only): you can help advance psychology research

Single email. Replaces "You can help advance psychology research". Today this email goes to the "yes" arm of a branch on a subscriber tag (2,672 of 54,689 subscribers took that arm). Suggested condition instead: opened at least two of the three previous drip emails, which beehiiv's branch can test on engagement, so "very engaged" means engaged with this sequence.

**Subject:** You can help advance psychology research
**Preview text:** Why we started working on the research itself, not just the tools built on it.

Hi there,

Spencer here, founder of ClearerThinking.org.

"{{last_tool_tried | one of our tools}}", like almost everything we make, exists because of research: studies we ran ourselves, and published findings we relied on. Which is why I want to tell you about a problem that has worried me for years.

Low-quality psychology research has a bigger negative impact than many people realize. When findings are shaky, the damage doesn't look dramatic. It looks like educators using strategies based on weak evidence, therapists relying on methods that may not help, and organizations making decisions about their people using questionable psychological ideas. Because these mistakes are subtle, they can spread for years without drawing attention.

For more than a decade we have worked to help people think more clearly, make better decisions, and change their behavior using evidence-based tools. Over time we came to think there is an even deeper problem to work on: the state of psychology research itself. If the foundation is unreliable, a lot of the advice, interventions, and tools built on top of it, ours included, will be limited too.

There are fantastic psychologists doing great research. But too often, work published in journals is not as reliable or as useful as it could be. So our mission has expanded. We are not only turning existing research into practical tools; we are also working to help build a stronger foundation for psychological research, grounded in rigor, transparency, replicability, and better incentives. Two fronts of that work:

- [Independent research](https://www.clearerthinking.org/research): our own original studies, which become the free interactive tools and mini-courses that help people improve their decisions, change their habits, and reach their goals. "{{last_tool_tried | one of our tools}}" came out of this work.
- [Transparent Replications](https://replications.clearerthinking.org/): we replicate recent human psychology and behavior papers from prominent journals to see how well they hold up.

The projects look different, but they share one goal: figure out what is actually true about human psychology, then make that knowledge useful.

Here is how you can help. If you become a member of [Clearer Thinking Plus](https://www.clearerthinking.org/plus?utm_source=beehiiv&utm_medium=email&utm_campaign=welcome_research), you get the premium offerings (our advanced cognitive assessment, coaching, ad-free podcasts, and more), and you fund the research, tools, and content we make available to everyone. Another unusually effective way to help is an introduction to someone who might provide a grant or major funding; one introduction can make an enormous difference. [This page](https://www.clearerthinking.org/support-us) lists a few other ways to support us.

If that mission resonates with you, I would be grateful for your help.

Warmly,

Spencer Greenberg
Founder, ClearerThinking.org
