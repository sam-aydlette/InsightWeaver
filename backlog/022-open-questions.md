# Parked questions from the monitoring re-architecture Stage 0. Answer before the tasks that name them.
REPO: InsightWeaver
STATUS: PARKED            # QUEUED | IN_PROGRESS | PARKED | DONE | FAILED
SIZE: n/a
ACCEPTANCE: not a work item. Each question below is answered by the operator, the answer is recorded here, and the task that names it is unblocked.
OUT OF SCOPE: guessing any of them.
---
Written 2026-08-31.

## ANSWERED 2026-08-31

**Position lives in a separate private repository.** Not primarily for safety -- a gitignore
mostly holds -- but because Position must be under version control and cannot be public. The
quarterly review's value is the diff: what did I believe last quarter, which decisions closed,
which watches stopped mattering. Gitignoring the file means no history, and the outermost loop
loses the thing that makes it a loop. The public repo carries the schema and an example, matching
how `user_profile.json` is already handled.

**Quarterly review degrades visibly rather than suppressing alerts** (task 024, unchanged).

---

## Q1 -- Persistence. Blocks task 020. **I could not verify pricing and will not estimate it.**

The brief asks for the trade-off with current pricing verified. I could not obtain it:
`https://aws.amazon.com/rds/postgresql/pricing/` renders its figures in interactive elements that
do not survive extraction, and the pricing API is unavailable to this account --
`pricing:GetProducts` returns `AccessDeniedException` for `arn:aws:iam::975050324277:user/saydlette-dev`.

I am not supplying remembered figures. What I can state without pricing:

| option | shape | operational cost |
|---|---|---|
| SQLite in S3, single-writer Lambda | one file, read-modify-write per run, no server | no idle cost; concurrency is the risk and one daily Lambda has none |
| RDS `t4g.micro` | managed Postgres, always on | bills hourly whether or not the pipeline runs; needs a VPC, subnet group and security group |
| Aurora Serverless v2 | scales to a floor, not to zero | most expensive of the three at this shape |

At one user, one daily invocation, and a corpus currently 55,249 rows, **SQLite in S3 is the shape
that matches the workload** -- the concurrency it cannot handle is concurrency this system does not
have. The counter-argument is that a read-modify-write of a growing file per run gets slower and
has no partial-failure story, and that migrating off it later is real work.

**To answer:** either grant `pricing:GetProducts` and I will produce the figures, or choose on
shape and accept that the cost comparison is unverified.

## Q2 -- Watch versus the existing Decision + Factor model. Blocks task 013.

The audit found the repository already models most of Watch, and has never used it:
`decision_factors.what_would_update_me` is a trigger, `.current_state_note` is a belief state,
`decisions.name` is what `so_what` points at, `decision_evidence.direction` is evidence direction.
All of it holds **0 rows**.

Evolving Decision+Factor avoids a second overlapping model; creating Watch alongside avoids
inheriting a prose-shaped schema where the new one needs floats and structured triggers. **My
recommendation is to evolve rather than add**, because this repository already carries one
unresolved duplication -- see the reconciliation note -- and a second would be worse than either
choice on its merits. But it is a schema decision with migration consequences and it is yours.

## Q3 -- Observations versus the existing `articles` table. Blocks task 014.

55,249 rows exist and every current query reads them. Observations can supersede that table
(migration of 55k rows), wrap it (two shapes for one concept), or coexist (a rule nobody remembers
in six months). I have no recommendation strong enough to make silently; the task file requires the
implementer to state the rule, but if you have a preference it belongs here first.

## Q4 -- The `so_what` -> decision link. Blocks task 013.

Invariant 2 requires every Watch to name a specific decision. Should that be a **free-text
`so_what` string**, or a **foreign key into the Position's decisions** with the prose as an
annotation? The key makes the invariant machine-checkable and makes "which watches serve this
decision" a query; the string is faster to author and does not force Position structure. The
acceptance in task 013 currently assumes the key, because an invariant enforced only by prose is
the pattern this repository has been correcting all week. Confirm or overrule.

## Q5 -- What happens to the beat, questions, predictions and calibration machinery?

Tasks 004-011 shipped beats, standing questions, institutional activity, coverage probes and the
operator calibration loop -- roughly 2,400 lines with 844 tests behind them. Some maps onto the new
model cleanly: `coverage_probes` is a staleness check by another name, and the operator calibration
loop is watch resolution scoring. Some does not: institutional activity is a briefing feature.

The plan above does **not** archive any of it, and does not port it either. That is a deliberate
gap, not an oversight -- deciding it needs your view on whether the compliance beat continues to
exist as a concept under the new architecture, or whether Position + Watches replaces it entirely.

## Q6 -- Dead-man's switch channel. Blocks task 018.

It must not be SES. SNS to SMS, a CloudWatch alarm to a phone push, or a third-party healthcheck
service that alarms on a missed heartbeat are the obvious candidates, each with a different failure
mode and cost. Which do you want, and to what endpoint?
