# disputes data refactor

*untangling the big nasty*

---

## The problem

Disputes reporting at Cash App ran on a pair of versioned tables the team called the big nasty: `bignasty` and `bignasty_ii`. Between them, 50+ columns covered cases, transaction details, and customer information in one place. The stack was Snowflake, Prefect, and Google Sheets, in 2022–2023.

It had three problems:

- **Competing identifiers.** Several versions of the customer and transaction IDs lived side by side, so joining out for metadata meant guessing which ID was the right one.
- **Dirty legacy data.** Legacy records weren't clean, and joining them in produced results that were hard to interpret.
- **Duplicated logic.** Multiple analysts were rebuilding the same joins on top of the table, so the same logic lived in many queries and drifted apart.

Disputes data is financial. A wrong join here isn't a cosmetic issue. It's misreporting.

---

## My role

I led the refactor with a team of five: a subject-matter expert and data analyst, plus four engineers.

---

## The approach

We broke the big nasty apart into separate tables for cases, transactions, and customers, each with one canonical identifier. We cleaned the legacy data, then built a data mart table that carried the transaction information analysts actually needed, already joined, so nobody had to rebuild it.

---

## Decisions

**Rebuild instead of leaving it alone.** Leaving the table as it was would have been the cheapest option in the short term. We rejected it because multiple analysts were writing the same joins against it, and every one of those queries was another chance to pick the wrong identifier.

**Validate against the source, not the old table.** The usual way to prove a refactor is to reconcile it against what it replaces. That wasn't possible here: the old table had known gaps, so matching it would have meant reproducing its errors. We validated against the source system's counts instead.

---

## The risk

The main risk was misreporting: a refactored model that quietly disagreed with the old one.

Validating against source system counts covered the cutover. To cover everything after it, we added data quality checks in Anomalo, so the model's health was tracked over time instead of being proven once and then assumed.

---

## After

- **Faster queries.** The mart carried the required transaction information, so analysts stopped rebuilding the same joins.
- **Clean, reliable legacy data.**
- **Fewer pipeline incidents** from schema drift.
- **Simpler maintenance:** one table to change instead of several.
- **Documentation** explaining why the model is shaped the way it is.

---

## What I'd do differently

**Treat the cutover as part of the build.** The model was ready before the people using it were. The change wasn't communicated broadly or in enough depth, so adoption slowed and turned into a long series of ad hoc one-on-ones. Next time, I'd plan the rollout with the same care as the model: announce it early, publish a migration guide that maps old columns to new tables, and set a clear deprecation date for the old ones.

---

The table had a nickname for a reason. The goal was a model nobody needed a nickname for.
