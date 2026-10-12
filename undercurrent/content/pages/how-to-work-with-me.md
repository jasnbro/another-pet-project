# How to work with me

> **Short version:** I'm a data systems engineer. I turn fuzzy, repetitive, or fragile problems into systems people can trust, and then I try to make those systems boring. I do my best work when I understand the *why*, have room to shape the *how*, and work with people who say what they actually think.

---

## <i data-lucide="workflow"></i> What I'm good at

I work in the space between building and architecture: close enough to the code to ship it, far enough out to notice when the real problem is the system around it.

- data pipelines and ingestion
- workflow orchestration
- data quality and operational reliability
- Python, SQL, and PySpark backend work
- turning one-off processes into reusable patterns
- making legacy or under-documented systems easier to reason about

When a task lands, I'm also looking at what surrounds it: where the data comes from, who depends on it, what breaks in six months, and whether anyone should be doing this by hand at all.

**In practice:** I built PipelineTools, a shared Python library that consolidated the code every ETL process on my team kept rewriting: database connectors, project scaffolding, credential generation and rotation, and environment variable management. Any pipeline running in the team's managed environment can use the same library instead of carrying its own copy, so a Python package or library change means one update instead of one per pipeline. It's in production behind a YAML-configured batch process and a Qualys API integration, where it handles credential rotation and endpoint ingestion. Centralizing it also concentrated the risk, since a breaking change now reaches every pipeline at once, so I paired it with active management of the team's Python environment to keep that contained.

---

## <i data-lucide="wrench"></i> What I believe about systems

Good systems reduce the attention people have to spend on them. The best infrastructure is quiet. It doesn't ask anyone to remember seven steps, doesn't depend on one person knowing the magic incantation, and doesn't create a hero every time it runs.

That's the idea behind **undercurrent**, the name of this site: systems that sit underneath work and life and carry some of the load.

A few opinions I hold:

- **Tables and pipelines are interfaces for people.** If someone has to ask the author what a table's grain is, what a column means, or how a pipeline behaves, the design isn't finished.
- **Documentation is part of the system, not cleanup after it.** It gives the next engineer, human or agent, enough context to understand what exists, why it exists, and what's already been tried.
- **If a pipeline can't be explained on one page,** it's either too complicated or nobody understands it well enough yet.
- **A failed pipeline should explain itself:** what happened, where, and which data was affected. If someone has to rerun it or open the code to find out, the logging is incomplete.
- **If a team can't explain the what, why, and how of a standard,** it needs either better teaching or a better standard.

---

## <i data-lucide="message-square-text"></i> Communication and feedback

I'm direct, but I'm not trying to win. I like conversations where people say what they think, show their reasoning, and change their minds when the evidence changes. That includes me.

I work best when the goal is explicit, context is shared rather than rationed, tradeoffs are named, and every decision has an owner.

If I'm asking a lot of questions, I'm building the model. Questions are how I learn a system.

On feedback, specific beats softened. Instead of:

> "Maybe think about communicating differently."

I'd rather hear:

> "In that meeting, you went three levels deeper than the decision required. The group lost the thread."

"I disagree, and here's why" is one of my favorite sentences.

---

## <i data-lucide="target"></i> Bringing me a problem

I don't need perfect requirements. Bring me in early enough to help shape the solution, and we'll work toward:

1. **What are we trying to change?**
2. **Who is this for?**
3. **What do we know so far?**
4. **What are we still trying to learn?**
5. **What constraints are real?**
6. **Who makes the final call when there's a tradeoff?**
7. **What would make us confident enough to move forward?**

We don't need all of these on day one. Sometimes finding them is the work.

I like meetings with a job: a decision, a messy cross-team problem, or nuance that's faster to talk through than type. Three bullets beforehand make me much more useful. I'm sharpest in the morning.

---

## <i data-lucide="sparkles"></i> What brings out my best work

- a real problem, even a messy one
- room to question the default
- ownership with accountability
- peers who care about craft without worshipping complexity
- honest technical disagreement
- decisions made in the open, with a clear owner

In return, you get structure, persistence, strong technical instincts, and more care than the ticket asked for.

---

## <i data-lucide="handshake"></i> What I'm looking for

Roles where senior engineers are expected to exercise technical judgment, shape systems, and stay close enough to the work to build. I'm a good fit if you need someone to own a data problem past the ticket boundary, improve systems while still shipping, and build with the next engineer in mind.

I'm happy to coordinate when it helps the engineering move, but I want my primary contribution to stay technical.

---

## <i data-lucide="coffee"></i> Outside the code

I garden, cook, write, ride bikes, and run a small home server because apparently I needed another computer to be responsible for. I like understanding how things work well enough to make them work better, whether that's a pipeline, a garden bed, or a recipe.

---

## <i data-lucide="circle-help"></i> Not sure how to approach me?

Bring me the messy version: what you know, what you don't, and what you're trying to decide. We'll find the structure from there.

---

*Last updated: October 2026*
