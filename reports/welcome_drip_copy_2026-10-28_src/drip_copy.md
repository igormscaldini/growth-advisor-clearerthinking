# New Subscribers drip: personalized copy

Draft for review. Source: `reports/welcome_drip_copy_2026-10-28_src/drip_copy.md` in the Growth Advisor repo.

## How to use this document

**Which field to personalize on.** Use the custom field **Last Tool Tried** (`last_tool_tried`). It is filled for 98% of new sign-ups with the tool's display name. "First Tool Tried" is empty on every sign-up since it was created, so do not use it.

**Values seen on the last 30,000 sign-ups** (daily share Oct 24 to 28, after the viral spike): Who Attracts You 45 to 70%, The Ultimate Personality Test about 80 a day, How Rational Are You, Really? about 50, Philosophical Beliefs about 35, Intrinsic Values Test about 30, Unique Traits Test about 12, The Value Of Your Time Calculator about 3, blank about 3%, everything else about 5%.

**Email 1 is branched; Emails 2 to 4 are single emails with a merge tag.** A beehiiv multi-split branch takes up to 5 paths plus "All others", so Email 1 needs two nested splits on Last Tool Tried:

1. Split A (equals): Who Attracts You / The Ultimate Personality Test / How Rational Are You, Really? / Philosophical Beliefs / Intrinsic Values Test / All others
2. Split B inside "All others" (equals): Unique Traits Test / The Value Of Your Time Calculator / All others (the generic version, which also covers blanks)

**Merge tag.** Emails 2 to 4 refer to the tool with `{{last_tool_tried | one of our tools}}` inside quotation marks, so every tool name reads naturally ("Who Attracts You", "How Rational Are You, Really?"). The text after the bar is the fallback for blanks. Field names are case-sensitive; merge tags also work in subject lines.

**Links.** Every coaching link carries `utm_source=beehiiv&utm_medium=email&utm_campaign=welcome_coaching&utm_content=<path>` so GA4 shows which variant sends people to /coaching. The session clip is https://youtu.be/oqyw8872x0E.

**Two things to fix in the live automation regardless of this copy.**

- The last link of the live "Big news" email ("give it a try") is a mangled URL that starts with `https://www.clearerthinahttps://...` and lands on a dead page. 140 people have clicked it so far.
- "Big news" is also step 2 of the live "[Drip Campaign] Tried Attraction Study" automation, and every Who Attracts You sign-up matches that segment and the New Subscribers trigger. Both automations sent about 30,000 copies in the last 7 days. Keep it in one place only.

**Why the rewrite.** "Big news" loses 1.34% of recipients to unsubscribes (0.21 to 0.26% for the other two drip emails) and sends 0.2% to /coaching. The new subject lines continue what the reader did yesterday, the opening names a problem the tool just surfaced, the price is framed as under $50 a session (the band 72% of readers said they would pay in the 2024 coaching survey), and the coach description pre-empts the "life coach selling obvious tips" image from the same survey.

---

## Email 1 (24 hours after sign-up): coaching, one version per tool

Spencer, first person. Only the subject, preview text, opening and bullet list change between paths. Button text is the same everywhere: **See how coaching works**.

### 1A. Path: Last Tool Tried equals "Who Attracts You"

**Subject:** Knowing your type is the easy part
**Preview text:** What your report can't do for you, and what can.
**Coaching link:** https://www.clearerthinking.org/coaching?utm_source=beehiiv&utm_medium=email&utm_campaign=welcome_coaching&utm_content=who_attracts_you

Hi there,

Spencer here again, from ClearerThinking.org. Thanks for taking [Who Attracts You](https://programs.clearerthinking.org/who_attracts_you_study.html) yesterday.

Your report shows which aspects of physical appearance predict who you find attractive. That is a new thing to know about yourself. But I want to be honest about what it can't do. It can't help with the part of dating and relationships that decides how things go: starting a conversation with someone you like, handling a "no" without taking it personally, the nerves before a first date, or working out what you actually want from the next relationship. Those are skills, and they are much easier to build with someone in your corner.

That gap, between knowing something about yourself and living differently because of it, is the reason we started offering one-on-one coaching. I tried the coaching myself before we partnered with Overcome, the organization that provides the coaches. They are psychology graduates trained by Overcome, and they use techniques from cognitive behavioral therapy, acceptance and commitment therapy, and motivational interviewing (well studied as therapies, less so as coaching). They are not licensed therapists, and Overcome's clinical supervisor screens every new client, so people who need therapy are directed there instead. Overcome tracks outcomes: their clients report being about 2 points happier on a 10-point scale after six sessions. That is their own measurement, not an independent study, but it is more than most coaching offers. Sessions are practical: you leave each one with something specific to try before the next.

Whether you are dating right now or in a relationship, a coach can help you:

- feel less anxious meeting new people, online or in person
- stop avoiding the situations that could lead somewhere, like asking someone out or going to the event you keep skipping
- figure out what keeps going wrong in your relationships, without blaming yourself for it
- make progress on something outside dating that has been stuck for a while

It costs $99 a month for up to two 45-minute video sessions, which works out to under $50 a session if you use both. Your first session is usually within a week of signing up. You can cancel anytime and switch coaches anytime. And if it turns out after the first session that what you need is therapy rather than coaching, we will refund you.

If you want to see what a session is like before deciding, [here is a 15-minute clip from a real one](https://youtu.be/oqyw8872x0E).

[Button: See how coaching works]

Coaching is not therapy, and it is not meant for crises or specialist mental health treatment. But if you want practical help turning what you learned into something you do differently, I hope you will take a look.

Warmly,

Spencer Greenberg
Founder, ClearerThinking.org

### 1B. Path: Last Tool Tried equals "The Ultimate Personality Test"

**Subject:** Your traits are not the whole story
**Preview text:** What to do with your report, now that you have it.
**Coaching link:** https://www.clearerthinking.org/coaching?utm_source=beehiiv&utm_medium=email&utm_campaign=welcome_coaching&utm_content=personality_test

Hi there,

This is Spencer Greenberg, founder of ClearerThinking.org. Thanks for taking the [Ultimate Personality Test](https://programs.clearerthinking.org/personality-test.html) yesterday.

Your report describes your tendencies: how much you worry, how you handle deadlines, how much structure you want, how you recharge. What it can't do is decide what you do with them. Two people with the same scores can live very different lives, depending on whether they have learned to work with their patterns or are quietly run by them. Self-knowledge helps. In my experience it is rarely enough on its own; what makes the difference is practice, and a second person to practice with.

That gap, between knowing something about yourself and living differently because of it, is the reason we started offering one-on-one coaching. I tried the coaching myself before we partnered with Overcome, the organization that provides the coaches. They are psychology graduates trained by Overcome, and they use techniques from cognitive behavioral therapy, acceptance and commitment therapy, and motivational interviewing (well studied as therapies, less so as coaching). They are not licensed therapists, and Overcome's clinical supervisor screens every new client, so people who need therapy are directed there instead. Overcome tracks outcomes: their clients report being about 2 points happier on a 10-point scale after six sessions. That is their own measurement, not an independent study, but it is more than most coaching offers. Sessions are practical: you leave each one with something specific to try before the next.

A coach can help you:

- manage worry and stress instead of being managed by them
- set standards you can actually meet, if perfectionism turns small tasks into ordeals
- say no and hold a boundary without a week of guilt afterward
- reduce the avoidance, overthinking, or procrastination your report may have put a name to
- build habits and routines that fit your personality instead of fighting it

It costs $99 a month for up to two 45-minute video sessions, which works out to under $50 a session if you use both. Your first session is usually within a week of signing up. You can cancel anytime and switch coaches anytime. And if it turns out after the first session that what you need is therapy rather than coaching, we will refund you.

If you want to see what a session is like before deciding, [here is a 15-minute clip from a real one](https://youtu.be/oqyw8872x0E).

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

That gap, between knowing what to do and doing it, is the reason we started offering one-on-one coaching. I tried the coaching myself before we partnered with Overcome, the organization that provides the coaches. They are psychology graduates trained by Overcome, and they use techniques from cognitive behavioral therapy, acceptance and commitment therapy, and motivational interviewing (well studied as therapies, less so as coaching). They are not licensed therapists, and Overcome's clinical supervisor screens every new client, so people who need therapy are directed there instead. Overcome tracks outcomes: their clients report being about 2 points happier on a 10-point scale after six sessions. That is their own measurement, not an independent study, but it is more than most coaching offers. Sessions are practical: you leave each one with something specific to try before the next.

A coach can help you:

- reduce procrastination and avoidance
- build habits and routines that survive past week two
- manage stress before it builds up
- turn a goal you keep circling into concrete weekly actions
- close the gap between what you know you should do and what you actually do

It costs $99 a month for up to two 45-minute video sessions, which works out to under $50 a session if you use both. Your first session is usually within a week of signing up. You can cancel anytime and switch coaches anytime. And if it turns out after the first session that what you need is therapy rather than coaching, we will refund you.

If you want to see what a session is like before deciding, [here is a 15-minute clip from a real one](https://youtu.be/oqyw8872x0E).

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

Here is something curious about the examined life: examining it is not the same as changing it. Most of what the quiz asked, free will included, changes nothing about how you spend a Tuesday. The questions about ethics are different: they are views about how to act, and most of us hold them more consistently than we live them. Your actual days get shaped by something else: the urgent over the important, habits you never chose, evenings that disappear without a trace. That gap doesn't close through more reflection alone.

That gap is the reason we started offering one-on-one coaching. I tried the coaching myself before we partnered with Overcome, the organization that provides the coaches. They are psychology graduates trained by Overcome, and they use techniques from cognitive behavioral therapy, acceptance and commitment therapy, and motivational interviewing (well studied as therapies, less so as coaching). They are not licensed therapists, and Overcome's clinical supervisor screens every new client, so people who need therapy are directed there instead. Overcome tracks outcomes: their clients report being about 2 points happier on a 10-point scale after six sessions. That is their own measurement, not an independent study, but it is more than most coaching offers. Sessions are practical: you leave each one with something specific to try before the next.

A coach can help you:

- turn a view about how to live into concrete weekly actions
- reduce procrastination and avoidance on the things that matter to you
- build habits and routines you would endorse on reflection
- manage stress and overthinking
- close the gap between the life you would argue for and the life you are living

It costs $99 a month for up to two 45-minute video sessions, which works out to under $50 a session if you use both. Your first session is usually within a week of signing up. You can cancel anytime and switch coaches anytime. And if it turns out after the first session that what you need is therapy rather than coaching, we will refund you.

If you want to see what a session is like before deciding, [here is a 15-minute clip from a real one](https://youtu.be/oqyw8872x0E).

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

This is Spencer Greenberg, founder of ClearerThinking.org. Thanks for taking the [Intrinsic Values Test](https://programs.clearerthinking.org/intrinsic_values_test.html) yesterday, and for stopping to work out what you care about for its own sake.

Here is the catch, though: a value trap is much easier to spot than to climb out of. You can know perfectly well that you are pursuing something because other people call it valuable rather than because you do, and still keep pursuing it. You can see clearly that your weeks are filled with things that don't serve what you care about, and still watch next week fill up the same way. Rearranging your life around your real values is a different challenge from identifying them.

That gap, between knowing what you value and living by it, is the reason we started offering one-on-one coaching. I tried the coaching myself before we partnered with Overcome, the organization that provides the coaches. They are psychology graduates trained by Overcome, and they use techniques from cognitive behavioral therapy, acceptance and commitment therapy, and motivational interviewing (well studied as therapies, less so as coaching). They are not licensed therapists, and Overcome's clinical supervisor screens every new client, so people who need therapy are directed there instead. Overcome tracks outcomes: their clients report being about 2 points happier on a 10-point scale after six sessions. That is their own measurement, not an independent study, but it is more than most coaching offers. Sessions are practical: you leave each one with something specific to try before the next.

A coach can help you:

- turn your top values into concrete goals and weekly actions
- step back from pursuits that look valuable but aren't actually yours
- let go of guilt about not wanting what others expect you to want
- reduce procrastination and avoidance on the things you care about most
- build habits and routines that create more of what you value

It costs $99 a month for up to two 45-minute video sessions, which works out to under $50 a session if you use both. Your first session is usually within a week of signing up. You can cancel anytime and switch coaches anytime. And if it turns out after the first session that what you need is therapy rather than coaching, we will refund you.

If you want to see what a session is like before deciding, [here is a 15-minute clip from a real one](https://youtu.be/oqyw8872x0E).

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

That gap, between understanding a trait and living well with it, is the reason we started offering one-on-one coaching. I tried the coaching myself before we partnered with Overcome, the organization that provides the coaches. They are psychology graduates trained by Overcome, and they use techniques from cognitive behavioral therapy, acceptance and commitment therapy, and motivational interviewing (well studied as therapies, less so as coaching). They are not licensed therapists, and Overcome's clinical supervisor screens every new client, so people who need therapy are directed there instead. Overcome tracks outcomes: their clients report being about 2 points happier on a 10-point scale after six sessions. That is their own measurement, not an independent study, but it is more than most coaching offers. Sessions are practical: you leave each one with something specific to try before the next.

A coach can help you:

- reduce worry, overthinking, or avoidance
- build habits and routines that work with your mind instead of against it
- manage stress before it builds up
- explain your differences to the people around you, at home or at work
- make progress on a goal that a stubborn pattern has been getting in the way of

It costs $99 a month for up to two 45-minute video sessions, which works out to under $50 a session if you use both. Your first session is usually within a week of signing up. You can cancel anytime and switch coaches anytime. And if it turns out after the first session that what you need is therapy rather than coaching, we will refund you.

If you want to see what a session is like before deciding, [here is a 15-minute clip from a real one](https://youtu.be/oqyw8872x0E).

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

Here is the catch with that number: knowing what your hour is worth doesn't change what happens to your hours. The biggest time losses usually aren't pricing mistakes, like waiting in the wrong line or skipping a worthwhile cab. They are patterns: the evenings that vanish into things you don't value, the commitments you couldn't say no to, the tasks you know you should hand off but keep doing yourself. A calculator can price those hours. It can't get them back.

That gap, between knowing what your time is worth and spending it that way, is the reason we started offering one-on-one coaching. I tried the coaching myself before we partnered with Overcome, the organization that provides the coaches. They are psychology graduates trained by Overcome, and they use techniques from cognitive behavioral therapy, acceptance and commitment therapy, and motivational interviewing (well studied as therapies, less so as coaching). They are not licensed therapists, and Overcome's clinical supervisor screens every new client, so people who need therapy are directed there instead. Overcome tracks outcomes: their clients report being about 2 points happier on a 10-point scale after six sessions. That is their own measurement, not an independent study, but it is more than most coaching offers. Sessions are practical: you leave each one with something specific to try before the next.

A coach can help you:

- reduce procrastination and the time lost to avoidance
- get better at saying no to commitments that aren't worth your hours
- follow through on delegating, not just know you should
- build routines that protect your highest-value time
- spend less time overthinking decisions you could make quickly

It costs $99 a month for up to two 45-minute video sessions, which works out to under $50 a session if you use both. Your first session is usually within a week of signing up. You can cancel anytime and switch coaches anytime. And if it turns out after the first session that what you need is therapy rather than coaching, we will refund you.

If you want to see what a session is like before deciding, [here is a 15-minute clip from a real one](https://youtu.be/oqyw8872x0E).

[Button: See how coaching works]

Coaching is not therapy, and it is not meant for crises or specialist mental health treatment. But if the way your hours get spent is getting in the way of your work, your goals, your relationships, or your peace of mind, I hope you will take a look.

Warmly,

Spencer Greenberg
Founder, ClearerThinking.org

### 1H. Path: All others (every other tool, and blank)

**Subject:** The part our tools can't do for you
**Preview text:** Knowing is the easy part.
**Coaching link:** https://www.clearerthinking.org/coaching?utm_source=beehiiv&utm_medium=email&utm_campaign=welcome_coaching&utm_content=other_tools

Hi there,

This is Spencer Greenberg, founder of ClearerThinking.org. Thanks for trying "{{last_tool_tried | one of our tools}}" yesterday.

Our tools are good at one thing: showing you something true about yourself or about the way you think. They are much worse at the next step, which is changing what you actually do on a Tuesday afternoon. In my experience, most people don't need more information for that. They need a plan that fits their life, someone who checks in on how it is going, and a second person to think it through with when they get stuck.

That gap, between knowing something and living differently because of it, is the reason we started offering one-on-one coaching. I tried the coaching myself before we partnered with Overcome, the organization that provides the coaches. They are psychology graduates trained by Overcome, and they use techniques from cognitive behavioral therapy, acceptance and commitment therapy, and motivational interviewing (well studied as therapies, less so as coaching). They are not licensed therapists, and Overcome's clinical supervisor screens every new client, so people who need therapy are directed there instead. Overcome tracks outcomes: their clients report being about 2 points happier on a 10-point scale after six sessions. That is their own measurement, not an independent study, but it is more than most coaching offers. Sessions are practical: you leave each one with something specific to try before the next.

A coach can help you:

- reduce procrastination and avoidance on the things that matter to you
- build habits and routines that last
- manage stress before it builds up
- make progress on a goal that has been stuck for a while

It costs $99 a month for up to two 45-minute video sessions, which works out to under $50 a session if you use both. Your first session is usually within a week of signing up. You can cancel anytime and switch coaches anytime. And if it turns out after the first session that what you need is therapy rather than coaching, we will refund you.

If you want to see what a session is like before deciding, [here is a 15-minute clip from a real one](https://youtu.be/oqyw8872x0E).

[Button: See how coaching works]

Coaching is not therapy, and it is not meant for crises or specialist mental health treatment. But if you want practical help turning what you learned into something you do differently, I hope you will take a look.

Warmly,

Spencer Greenberg
Founder, ClearerThinking.org

---

## Email 2 (day 14): the Cognitive Assessment

Single email, no branch. Replaces "Does IQ actually matter?". The four findings are the ones in the current email, unchanged in substance; what is new is the opening and closing that tie it to the reader's tool, and the price.

**Subject:** Does IQ actually matter?
**Preview text:** We ran a study with 3,691 participants to find out.
**Assessment link:** https://programs.clearerthinking.org/cognitive-test-intro.html?utm_source=beehiiv&utm_medium=email&utm_campaign=welcome_cognitive_assessment

Hi there,

When you tried "{{last_tool_tried | one of our tools}}" two weeks ago, you were looking at something about who you are: your traits, your values, the way you reason, what you are drawn to. Today I want to share something about a different question people ask us all the time: what does an IQ score really tell you about you?

To find out, [we ran a study on IQ with 3,691 participants](https://www.clearerthinking.org/post/what-s-really-true-about-intelligence-and-iq-we-empirically-tested-40-claims) and tested a wide range of claims about what IQ does and doesn't predict. Here are four findings that surprised our team.

**1) Perfectionism doesn't seem to be a sign of high IQ**

There is a familiar cultural image of the brilliant perfectionist: the genius who obsesses over every detail. In our data, IQ had essentially no meaningful relationship with perfectionism. That doesn't prove there are no genius perfectionists, of course. But it does suggest that perfectionism, by itself, is not a useful clue that someone has a high IQ.

**2) IQ was much more related to high-school GPA than college GPA**

IQ scores were moderately correlated with high-school GPA, but barely correlated with college GPA. Why would IQ matter less once school gets harder? Maybe college success depends much more on motivation, self-regulation, and time management. Maybe college GPA is a noisier measure, because students take very different classes with very different grading standards. Or selection effects may hide the relationship, since colleges admit students who resemble each other. Whatever the explanation, it is a good reminder that data often allow for more than one plausible interpretation.

**3) People with higher IQ scores were less likely to think they could solve society's problems**

You might expect people with higher IQs to be more confident in their solutions to big problems. We found a small negative correlation between IQ and believing you could figure out solutions to societal problems. One possible explanation is that people with higher scores are more likely to see how complex those problems really are: more ability, in the domains IQ tests measure, may sometimes come with more humility about how hard the problem is.

**4) IQ matters much less than many people think**

IQ scores contain real information about someone's intelligence and performance at some tasks. They give you a reason to update your expectations, at least a little, about certain traits and outcomes. But any given IQ score is compatible with a wide range of traits, skills, and life outcomes. IQ is moderately predictive of some things. It is not destiny, and it is not a verdict on anyone's worth.

If you want the details, [the full report](https://www.clearerthinking.org/post/what-s-really-true-about-intelligence-and-iq-we-empirically-tested-40-claims) is on our blog, and I also made [a YouTube video about the study](https://www.youtube.com/watch?v=BxsIyHSoQW8) if you would rather watch than read.

That last finding is partly why our [Cognitive Assessment](https://programs.clearerthinking.org/cognitive-test-intro.html?utm_source=beehiiv&utm_medium=email&utm_campaign=welcome_cognitive_assessment) reports seven cognitive abilities separately instead of one number: a single score hides more than it shows. It also includes learning and career suggestions based on your profile; given finding 4, treat those as pointers, not verdicts. If "{{last_tool_tried | one of our tools}}" told you something about who you are, this one tells you something about how you think. It costs $35. Unlike almost all of our tools it is not free, because the proceeds support everything else we make.

[Button: Take the Cognitive Assessment]

Warmly,

Spencer Greenberg
Founder, ClearerThinking.org

---

## Email 3 (day 28): should you get a life coach?

Single email, no branch. Replaces "Should you have a life coach?". The five points are the current ones; new are the opening that ties them to the reader's tool and admits this is the second coaching email, a named study in point 2, and a disclosure.

**Subject:** Should you have a life coach?
**Preview text:** A fair look at whether coaching works, and how to tell a good coach from a bad one.
**Coaching link:** https://www.clearerthinking.org/coaching?utm_source=beehiiv&utm_medium=email&utm_campaign=welcome_coaching_evidence

Hi there,

About a month ago you tried "{{last_tool_tried | one of our tools}}", and a day later I wrote to you about our coaching program. Today I want to step back and ask a fairer question than "should you sign up": does life coaching actually work? One thing first: Clearer Thinking earns money when a reader signs up for coaching, so discount what I say accordingly. Here is the evidence as I understand it.

In theory, a coach can help you solve problems, provide support, and create accountability. But do people who receive coaching actually benefit? Since we started offering coaching, I thought it was worth taking a closer look. Below are a few ideas, taken from [our article on the subject](https://www.clearerthinking.org/post/does-life-coaching-actually-work), that I think are especially worth considering.

**1) "Coaching" is an extremely broad category**

Because coaching is largely unregulated, almost anyone can call themselves a coach. The term covers everything from thoughtful guidance and accountability to shallow advice to outright grifting. Asking whether coaching "works" is a bit like asking whether "medicine works" without saying which treatment, for which condition, from whom.

**2) There is some evidence that coaching can help**

The research base is still small, most of it comes from workplace coaching, and the studies are often small and not blinded. The best-known summary is [a 2014 meta-analysis by Theeboom and colleagues](https://doi.org/10.1080/17439760.2013.837499), which pooled studies of coaching in organizations and found moderate positive effects on performance, well-being, coping, work attitudes, and goal-directed self-regulation (effect sizes from 0.43 to 0.74). A [2016 meta-analysis of 17 studies](https://doi.org/10.1111/joop.12119) found a smaller overall effect (0.36). Encouraging, not settled, and not yet much evidence about coaching for personal goals outside work. That doesn't make coaching a magic solution. It does mean there are reasonable grounds to consider it as part of a personal development plan.

**3) Coaching may be especially useful during transitions**

A new role, a major decision, or just the feeling that you are stuck and want to move forward more deliberately. When your current strategy isn't working, it helps to have someone thoughtful help you see blind spots, clarify goals, and build a better plan.

**4) Fit matters a lot**

A coach can be skilled and still be the wrong coach for you. Pay attention to whether your agendas are aligned, whether you feel understood, whether the coach listens well, and whether the conversations leave you feeling supported rather than judged or defensive. Coaching is not just about whether the coach is "good" in the abstract. It is about whether they are good for you, specifically.

**5) There are some simple green flags**

- A coach who gives you homework, or otherwise encourages action between sessions
- A coach who helps you build progress rather than dependency
- A coach who doesn't pressure you to buy expensive add-ons such as courses, retreats, or masterminds
- A coach who is willing to end the relationship once you have made the progress you came for

Here is how our own program measures against that list: the coaches come from our partner Overcome, they set work between sessions, there is nothing extra to buy, and you can switch coaches or cancel at any time. What we don't have yet is an independent measurement of results for our own readers; Overcome's own tracking shows clients about 2 points happier on a 10-point scale after six sessions. If "{{last_tool_tried | one of our tools}}" showed you something you would like to change and you want a second person on it, [here is how our coaching works](https://www.clearerthinking.org/coaching?utm_source=beehiiv&utm_medium=email&utm_campaign=welcome_coaching_evidence).

Warmly,

Spencer Greenberg
Founder, ClearerThinking.org

---

## Email 4 (day 42, engaged readers only): you can help advance psychology research

Single email. Replaces "You can help advance psychology research". Today it goes to the "yes" arm of a branch on a subscriber tag (2,672 of 54,689 subscribers took that arm). Suggested condition instead: opened at least two of the three previous drip emails, which the branch can test on engagement, so "very engaged" means engaged with this sequence.

**Subject:** You can help advance psychology research
**Preview text:** Why we started working on the research itself, not just the tools built on it.
**Plus link:** https://www.clearerthinking.org/plus?utm_source=beehiiv&utm_medium=email&utm_campaign=welcome_research

Hi there,

Spencer here, founder of ClearerThinking.org.

Tools like "{{last_tool_tried | one of our tools}}" are built on research: studies we run ourselves, and published findings we rely on. Which is why I want to tell you about a problem that has worried me for years.

Low-quality psychology research has a bigger negative impact than many people realize. In 2015, [a large project re-ran 100 published psychology studies](https://doi.org/10.1126/science.aac4716) and only about a third of the replications found the original effect. When findings are shaky, the damage doesn't look dramatic. It looks like educators using strategies based on weak evidence, therapists relying on methods that may not help, and organizations making decisions about their people using questionable psychological ideas. Because these mistakes are subtle, they can spread for years without drawing attention.

For more than a decade we have worked to help people think more clearly, make better decisions, and change their behavior using evidence-based tools. Over time we came to think there is an even deeper problem to work on: the state of psychology research itself. If the foundation is unreliable, a lot of the advice, interventions, and tools built on top of it, ours included, will be limited too.

There are fantastic psychologists doing great research. But too often, work published in journals is not as reliable or as useful as it could be. So our mission has expanded. We are not only turning existing research into practical tools; we are also working to help build a stronger foundation for psychological research, grounded in rigor, transparency, replicability, and better incentives. Two fronts of that work:

- [Independent research](https://www.clearerthinking.org/research): our own original studies, which become the free interactive tools and mini-courses that help people improve their decisions, change their habits, and reach their goals.
- [Transparent Replications](https://replications.clearerthinking.org/): we re-run recent human psychology and behavior papers from prominent journals to see how well they hold up. We have published 14 of these so far; of the first dozen, 10 held up and 2 mostly did not, and every report is public.

The projects look different, but they share one goal: figure out what is actually true about human psychology, then make that knowledge useful.

Here is how you can help. [Clearer Thinking Plus](https://www.clearerthinking.org/plus?utm_source=beehiiv&utm_medium=email&utm_campaign=welcome_research) membership starts at $9 a month; the $29 Explorer tier adds the Cognitive Assessment, the personality PDF report, ad-free podcasts, and bonus content, and the $99 Navigator tier is the one that includes the two coaching sessions a month I wrote to you about. Whichever tier, the fee funds the research, tools, and content we make available to everyone. If you happen to know someone who funds research or nonprofits, an introduction is the other thing that makes an outsized difference. [This page](https://www.clearerthinking.org/support-us) lists a few more ways to support us.

[Button: Join Clearer Thinking Plus]

If that mission resonates with you, I would be grateful for your help.

Warmly,

Spencer Greenberg
Founder, ClearerThinking.org

---

## Review notes

Three artificial readers, each built from one of the dashboard personas (survey and buyer data), read the first draft in character: the Curious Self-Improver (took the personality test), the Rigorous Rationalist (took the rationality test), and the Overwhelmed Striver (took Who Attracts You on a phone). Changes made because of them, and what was left as is:

- **Coaches.** "Trained psychology graduates" alone read as borrowing therapy's credibility. Now every variant says they are not licensed therapists and that Overcome's clinical supervisor screens new clients (both from the coaching page).
- **Price.** "Under $50 a session" now says "if you use both"; a reader who books one session pays $99 for it.
- **Who Attracts You.** "Why your relationships keep following the same pattern" diagnosed a stranger from a quiz about faces; replaced with "working out what you actually want from the next relationship", and the bullet now says "without blaming yourself for it". The sleep-and-work bullet was cut; the last bullet covers people who are not dating.
- **Personality test.** Preview text no longer talks the report down ("What to do with your report, now that you have it"); "self-knowledge helps, in my experience it is rarely enough on its own" replaces a line that sounded like the seller of a self-knowledge PDF dismissing self-knowledge.
- **Email 2.** Price added ($35; Stripe also shows $17.50 charges, so confirm which price the intro page displays before sending). The pitch now follows from finding 4 instead of contradicting it. Duration and a sample report were requested by two readers; add them if a sample report link exists.
- **Email 3.** Point 2 names two real meta-analyses with their effect sizes (both verified) and says most evidence is from workplace coaching. "The standard we held our own program to" became a plain list of facts, plus a disclosure that Clearer Thinking earns money on sign-ups, which the article itself discloses. The closing no longer says "you have not gotten around to it yet".
- **Email 4.** Readers were confused that coaching was $99 in Email 1 and a membership perk here; the tiers and prices are now spelled out. The claim that their specific tool "came out of this work" was cut (not true of every tool); the funder-introduction ask was kept but shortened, since this email goes only to engaged readers.
- **Coaching outcomes.** The rationalist reader said "we have not measured it yet" beats silence, so every variant now carries Overcome's own figure from the coaching page (about 2 points happier on a 10-point scale after six sessions), labelled as their measurement, not an independent study, and Email 3 says plainly that there is no independent result for our readers yet. The therapy methods are now described as "well studied as therapies, less so as coaching".
- **Philosophical Beliefs.** The quiz asks about free will, knowledge and ethics, not values, so the opening no longer claims it measured what you value. The rationalist reader would rather be sent to the Intrinsic Values Test with coaching as one closing line; the variant keeps the coaching pitch as asked, but that alternative is worth a test given the path is only about 35 people a day.
- **Email 4.** Now opens the problem with the 2015 replication figure (100 studies, about a third replicated) and states the Transparent Replications tally (14 reports; 10 of the first 12 held up). The rationalist reader would put this email first in the sequence, before any coaching pitch; the order is unchanged here, but it is a cheap test.
- **Kept despite pushback.** "Quietly run by them" and "put a name to" in 1B landed with the personality-test reader (the target of that variant) even though the Striver found them sharp. The four IQ findings stay because the rationalist reader finished the email and asked for more detail, not less.
- **Open items.** (1) "I tried the coaching myself" reads as a credential; one true sentence from Spencer about what he worked on would do more than any other change. (2) Two readers clicked the session clip before the button: consider testing "Watch a real session (15 min)" as the button on the Who Attracts You path. (3) The Striver counted four asks in six weeks and nothing free to do; a P.S. in Email 1 pointing to one free tool for the top blocker (for example Get Going: Overcome Procrastination) would cost little and should reduce unsubscribes.
