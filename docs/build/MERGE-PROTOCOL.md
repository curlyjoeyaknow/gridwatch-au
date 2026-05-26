# Merge Protocol

> How a track lands on `main`. Standing rules in `../../CLAUDE.md` win on conflict.
> Companion to `build-plan.md` (the tracks).

## The rule
**Every track lands via a reviewed PR into `main`. No direct pushes to `main`.** Per-task
work runs during the session; the PR is where it stops for review. The PR is the human
gate.

## Why layered review
Bugs are caught by reviewers that fail **independently**. Each layer has a blind spot the
others cover — the value is in the independence, not the count.

| Layer | When | Catches | Blind spot |
|---|---|---|---|
| **Self-review of the diff** | per track | does it do what it claims; are the tests real (can they fail); spec match | shares the builder's framing |
| **External review bot** | per PR | best-practice breaches; the project contradicting its own stated rules | knows nothing about the domain |
| **CI on a clean runner** | per PR | does it run & pass the full suite without local luck | only what the tests assert |
| **Human (you)** | per PR | judgment, domain semantics, "is this the right design?" | time/attention |

## Branching
- One branch per PR (`scaffold`, `track-0-1-contracts-domain`, …); branch from latest
  `main`, squash-merge back, branch the next from the updated `main`.
- CI (`.github/workflows/ci.yml`) must be green before merge.
- Server-side branch protection on `main` needs GitHub Pro for a **private** repo, so it
  is **not** enabled here (the repo is private for academic-integrity reasons). The rule
  is therefore enforced **by process**: every change goes through a PR and is merged only
  after CI is green — no `git push` straight to `main`. Flip the repo to Pro/public to
  have GitHub enforce it server-side.

## Triaging review findings
Findings are **candidates, not verdicts**. Accept the real ones and fix them in the same
PR; dismiss noise with a one-line **recorded** reason, never silently. "The bot approved
it" never substitutes for thinking.
