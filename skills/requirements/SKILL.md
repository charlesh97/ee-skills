---
name: requirements
description: >
  Kick off a board design by interviewing the engineer about what the board has
  to do — what powers it, how big it is, where it lives, what it talks to, what
  it costs, how many we make — and writing project.yaml and requirements.yaml.
  Load this when someone says "new board", "spec out", "what do we need for",
  "requirements", "kick off a design", "let's start a design", "scope this",
  "revision of", "rev B of", "derivative of", or describes a product idea and
  wants to know what to build. Also load it when any downstream skill finds
  project.yaml or requirements.yaml missing. This skill asks; it does not design.
---

# Requirements

This is the brainstorming skill for a board. The job is to get hold of all the
parameters the design will need and to help the engineer understand the scope of
what is being built — no more. Every downstream skill (system-architecture,
power-architecture, part-spec, the reviews) reads what is written here, so a
number you don't ask for now becomes a guess somebody makes later. The moment a
model starts designing it stops asking, which is why this skill refuses to
design.

## Contract

Reads:  nothing required to start.
        Optional: a prior project directory (`project.yaml`, `requirements.yaml`,
        `system.yaml`, `power_tree.yaml`, `open_items.yaml`) when this is a
        derivative of an existing board.
        `ee-schematic-rules/references/asks.yaml` — the four project questions.
Writes: `project.yaml`, `requirements.yaml`, `open_items.yaml` (append).
Stops if: a prior project directory is named but cannot be read, or its
        `requirements.yaml` is malformed. Interviewing deltas against a file you
        can't parse produces a spec that silently disagrees with its parent.

## Before you start

Load `ee-schematic-rules`. Read `references/asks.yaml` there — its four questions
are part of this interview and their answers go to the `project_field` paths it
names. Read `references/question-bank.md` here. If `project.yaml` or
`requirements.yaml` already exist in the project directory, read them and don't
re-ask anything they answer; say what you found and ask what's changing.

## How to ask

- One question per message. If a topic needs more, that's more messages.
- Where the answer is a choice, offer options with the trade-off attached and
  say which you'd pick and why. "BLE only (cheapest, phone must be nearby),
  WiFi (realistically wants mains power), or both (roughly $4 more and an
  antenna coexistence problem)" — not "do you need wireless?"
- Where the answer is a number, get a number. "Standard industrial temp" is
  not an answer until you have written down -40 to 85 and where it came from.
  Record the source next to the number.
- Never ask something a loaded artifact already answers.
- Follow the branches in the question bank. "Battery powered" opens chemistry,
  capacity, charge source, gauging, runtime, shipping regs; "wall powered"
  closes those and opens inrush, hold-up, isolation. A flat form gets skipped;
  a tree that asks the dozen relevant questions gets finished.
- If the engineer doesn't know, offer a sensible default, mark it `source:
  default`, and log it in `open_items.yaml`. A recorded default is fine; a
  silent one is the failure this skill exists to prevent.
- Product-level capability trade-offs are in scope: BLE vs WiFi, rechargeable vs
  primary cell, USB-C vs barrel jack, module vs discrete radio. Blocks, rails,
  topologies and part numbers are not — see "What this skill refuses to do".

## Steps

1. **Scope check.** One board or several? A "system" with a base station and a
   sensor puck is two boards with an interconnect. Interview each board
   separately and write the interconnect as an interface requirement on both.
   Don't interview a system as if it were a board.

2. **Provenance — first real question.** Is this a derivative of an existing
   board? If yes, load the prior project, play back a short summary of what it
   was (power, size, interfaces, modes, cost), set `derived_from`, and interview
   only what changes. Keep the parent's `REQ-` ids for requirements that carry
   over so downstream references survive; mark dropped ones `priority: wont`
   with a note rather than deleting them. A revision of a working board should
   be about ten questions.

3. **Product in a sentence.** What is it, who uses it, what does it do. This
   names the project and tells you which branches of the bank are live.

4. **Board size and mechanical envelope — early.** Size gates 0201 passives,
   test-point form and debug-header choice, so ask it before the four
   `asks.yaml` questions, then ask those four straight after, one at a time.
   Write the answers to the `project_field` paths in `project.yaml`.

5. **Power source.** This is the biggest branch in the bank. Battery, wall/DC
   input, USB, host-supplied rails, or a combination (battery + USB charge is
   common and opens both branches). Capture Vin range as min/nom/max numbers.

6. **Operating modes with duty cycles.** Define them once — `off`, `sleep`,
   `active`, `peak`, or whatever fits — with a duty percentage for each. Every
   load in `system.yaml` declares a current per mode and power-architecture
   sums them, so without modes nothing downstream is checkable. Duty cycles
   should sum to about 100% of operating time; `off` is outside that.

7. **Environment as numbers.** Ambient range, Vin range, target unit cost,
   annual volume. These four go in the `environment` block verbatim because
   downstream arithmetic (derating, junction temp, cost roll-up) reads them.
   Humidity, ingress, shock and vibration go in as requirements.

8. **Walk the remaining live categories.** Compute, wireless, I/O and sensing,
   compliance and safety, debug and test, cost and lifecycle, manufacturing.
   Skip branches the earlier answers closed. Each question in the bank says
   which category it closes.

9. **Coverage sweep.** Every category in `coverage` reaches `answered`,
   `deferred`, or `n/a`. Deferred means an `open_items.yaml` entry with
   `kind: deferral`, who owns it and which skill must resolve it. n/a means a
   reason ("no radio"). Silence is not a pass.

10. **Play back in sections.** Product and scope; mechanical and project
    settings; power and modes; environment; interfaces, I/O and wireless;
    compute and firmware; compliance and safety; debug, test and manufacturing;
    cost and lifecycle. Get a yes on each section before moving on. Don't
    present a wall and ask "look good?"

11. **Write the files.** `project.yaml` and `requirements.yaml` in the shapes
    given in `shared-v2.md`. Each requirement is one testable statement with
    `category`, `priority` (must/should/wont), `verify` (analysis, inspection,
    test, demonstration) and `source` (who said it, when). Show the YAML.

## Writing good requirement statements

Say what the board must do, not how. "Operate from 9-36V DC" is a requirement;
"use a buck converter" is a design decision that belongs to power-architecture.
One thing per statement, with a number where there is one. If you can't say how
you'd verify it, it isn't a requirement yet — ask again.

When the engineer gives you two numbers that imply a third — battery capacity
and runtime target, say — compute the implied figure in a short Python snippet
and write it down as a derived requirement with `verify: analysis`. That is the
one place arithmetic shows up here; don't do it in your head.

## What this skill refuses to do

No blocks, no rails, no topologies, no part classes, no part numbers, no power
tree, no "you'll probably want an STM32". If the engineer asks "so what chip
should we use?" — note the question, say that's system-architecture's job and
that it reads this file, and carry on asking. Designing stops you asking, and
the unasked question is what causes the respin. The only skill that follows
this one is `system-architecture`, and only after the playback is approved.

## Check yourself

- Every category in `coverage` has a terminal state, and every `deferred` has a
  matching `open_items.yaml` entry.
- `modes` has at least two entries with duty percentages; `environment` has
  numeric `t_ambient_c`, `vin_v`, `target_unit_cost_usd`, `annual_volume`.
- All four `asks.yaml` answers are in `project.yaml`, and any that took the
  default is marked as such and logged.
- `board_size_mm` is filled in. `derived_from` is set or null.
- No requirement names a part, a rail voltage the board generates, or a
  topology. Input voltage is fine; "3V3 rail" is not.
- Every requirement has a `source` and a `verify` method.
- Read the finished YAML back once as the engineer would. Anything that
  surprises you is a question you should have asked.

## Handoff

`system-architecture` reads `project.yaml` and `requirements.yaml` and turns
the modes, environment and requirements into blocks and loads. Tell the
engineer that's next, and that a fresh session is fine — everything it needs is
in the files.
