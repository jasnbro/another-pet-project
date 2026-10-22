# pipelinetools

*the plumbing every pipeline kept rewriting*

---

## The problem

My team's ETL processes grew the way most do: each new script started as a copy of an older one. I kept seeing the same code in script after script: database connectors, credential handling, environment setup, project scaffolding. Each copy drifted a little from the last, and none of it lived in one place.

I consolidated it into a shared library. Then a Python migration showed exactly what that duplication costs. Moving off Python 3.7 meant **182 legacy scripts had to be updated by hand** to run on Python 3.14. It was the same fix 182 times, because the shared logic had never actually been shared.

---

## The design

PipelineTools consolidates those repeated pieces into one library that any pipeline running in the team's managed environment can use:

- database connectors and connection handling
- project scaffolding: folders, files, repo setup
- credential generation and rotation
- environment variable management

I kept it deliberately simple: a single entry point wrapping the patterns the team already relied on, plus new credential generation and rotation. The goal wasn't a framework. It was one copy of the plumbing, in one place.

![PipelineTools architecture: pipelines import one shared library with four modules, running on a managed Python environment](/images/pipelinetools-architecture.svg)

---

## Decisions

**Own it in-house instead of adopting an external library.** I considered building on an externally managed repo and rejected it: it had no clear ownership and no distribution path. A shared dependency nobody owns turns into the next legacy problem.

**Distribute through a shared path, for now.** Pipelines import the library from a shared location. It's the simplest option that works across every user and server, and it means a fix lands everywhere at once. It also means a mistake does.

---

## The risk

Centralizing code centralizes failure. Before, a bad change broke one script. Now a breaking change reaches every pipeline that imports the library.

I contain that by managing the environment underneath it. Package versions are pinned, and the Python version is standardized across users and servers, so the library runs against one known set of dependencies instead of whatever each machine happens to have.

---

## In production

PipelineTools runs behind a YAML-configured batch process and a Qualys API integration, where it handles credential rotation and endpoint ingestion.

---

## What I'd do next

- **Tests first.** A library with this blast radius needs a test suite before it needs more features. Today, the pinned environment is the main safety net; tests would catch breaking changes before they ship instead of after.
- **Versioned packaging.** I'm evaluating uv for packaging and distribution. Pipelines could then pin a library version instead of always running whatever is on the shared path, so upgrades become a choice instead of an event.
- **Separate database work from project setup.** Database functions currently live alongside project scaffolding, so using a connector depends on setting up a project structure. I'd split them into independent modules and make scaffolding opt-in with a flag.

---

The point was never the library. It was making the next Python upgrade one change instead of 182.
