# hot parts

*from one person's PC to the production floor*

---

## The problem

At Mercedes-Benz U.S. International, line management and "hot parts" staff used a Microsoft Access database to coordinate which parts the production line needed, and to track when those parts were requested and delivered.

That database lived on one person's PC. When that person left the company, they emailed it to a colleague along with instructions. The colleague didn't know how to maintain it. A system the production line depended on had a bus factor of one, and then effectively zero.

---

## My role

I was part of a team. The web application was built by a development team supporting the company's South Africa plant. My job was everything that had to happen before they could build: understand what existed, design the data the new system needed, and confirm that design with the people who used it every day.

---

## The approach

There was no documentation and no original author to ask. I reverse-engineered the requirements from the Access tables themselves, then designed a data model compatible with the .NET web application the development team would build.

I worked with line and hot-parts staff to walk through their actual processes and confirm the model covered what they did, column by column.

---

## Decisions

**Mirror the existing model, but make its relationships explicit.** The new data model kept the shape of the Access tables staff already worked with, so they recognized the structure and could check it against what they knew. What changed was underneath: every table got explicit primary keys, and every relationship got explicit foreign keys. In Access, the links between rows held up only as long as the person maintaining the database kept them consistent. In the new model, the database enforced them.

---

## The risk

The production line depended on this system, so there was no hard cutover. The Access database and the new application ran side by side until staff trusted the new one. I took part in validating the development team's application against the data model and against how staff actually worked before the switch.

---

## After

- **Near real-time display** of hot parts on the production floor, updated automatically.
- **Reliable and maintainable:** no single PC, no single person.
- **More accurate:** nobody hand-managing every change.
- **Self-service** for the staff who depended on it.

---

## What I'd do differently

- **Design for more than hot parts.** Mirroring the old model made the switch safer, but it also inherited the old model's scope: one workflow. With more flexibility built in, the same model could have supported other parts processes or services.
- **Write onboarding documentation** for new managers and staff. The original failure was knowledge living in one person's head. The new system shouldn't repeat that failure in a different form.

---

The original system didn't fail because it was built in Access. It failed because it lived in one place, and in one person's head.
