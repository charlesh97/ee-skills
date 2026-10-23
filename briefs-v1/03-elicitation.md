# Shared Elicitation Discipline

Read this if your skill has an interview phase: `requirements`, `system-architecture`,
`power-architecture`, and `part-select` all do. Derived from the superpowers
`brainstorming` skill, adapted for EE.

## What transfers directly

1. **Scope check before detail questions.** If the request spans multiple
   independent subsystems, say so immediately rather than spending questions
   refining details of something that needs decomposing first.
2. **One question per message.** If a topic needs more exploration, break it into
   several messages. Multiple choice is preferred; open-ended is acceptable.
3. **Options with trade-offs and a recommendation** wherever a decision is a
   choice rather than a constraint. Not "do you need wireless?" but "BLE only
   (cheapest, needs a phone nearby), WiFi (realistically needs mains power), or
   both (adds roughly $4 and an antenna coexistence problem)."
4. **Play back in sections and get approval per section**, scaled to complexity.
   Do not present a wall of output and ask "look good?"
5. **A hard gate against running ahead.** Name the skills you are refusing to
   invoke and the single skill that may follow.

## What changes for EE

**The question space is knowable in advance.** Software brainstorming discovers
its own questions. EE does not: the set of things you must know before designing a
board is finite and enumerable. Questions therefore live in a **versioned question
bank in `references/`**, and the model's job is selecting and ordering them, not
inventing them. If questions are emergent, you have rebuilt the inconsistency the
project exists to eliminate.

**Ask branch-conditionally, not as a flat form.** "Battery powered" opens
chemistry, capacity, charge source, fuel gauging, runtime target, and shipping
regulations. "Wall powered" closes all six and opens inrush, hold-up, and
isolation instead. A flat 60-question form is what engineers learn to skip; a tree
that asks twelve relevant questions is one they finish.

**Most answers already exist.** Before question one, ask whether this is a
derivative of an existing design. If yes, load that project's artifacts and
interview only the deltas. A revision of a working board should be a ten-question
conversation.

**Approval is not a sufficient terminal state.** Superpowers ends when the user
approves. For EE the unasked question is the one that causes a respin, so every
category must reach an explicit terminal state: `answered`, `deferred` (with owner
and resolve-by phase), or `n/a` (with a reason). Silence is not a pass.

Per Principle 6 this is **advisory**: an unresolved category warns and lands in
`open_items.yaml`, it does not block. The record is the safeguard, not the barrier.

## Anti-patterns

- Asking a question whose answer is already in a loaded artifact.
- Asking three questions in one message because they feel related.
- Accepting "standard" or "typical" as an answer to a numeric question without
  recording what number that resolved to and where it came from.
- Proceeding to design in the middle of an interview. Designing stops you asking.
