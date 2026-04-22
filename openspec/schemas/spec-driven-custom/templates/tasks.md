<!-- TASK FORMAT:
     - [ ] TSK-<CAP>-<REQ>-<seq> [P] <Description> | traces: REQ-<CAP>-<REQ> | depends_on: none
     [P] = parallelizable (no unresolved dependencies within the same or earlier wave)
     Each task: 1-4 hours, one concern, verifiable (you know when it's done)
-->

## Wave 0 — Foundation (no dependencies) [P]

<!-- Tasks that can start immediately and run in parallel. -->

- [ ] TSK-001-01-01 [P] <!-- Task description --> | traces: REQ-001-01 | depends_on: none
- [ ] TSK-001-02-01 [P] <!-- Task description --> | traces: REQ-001-02 | depends_on: none

## Wave 1 — Core Implementation [P]

<!-- Tasks that depend only on Wave 0. Tasks within this wave are parallel. -->

- [ ] TSK-001-01-02 [P] <!-- Task description --> | traces: REQ-001-01 | depends_on: TSK-001-01-01
- [ ] TSK-001-03-01 [P] <!-- Task description --> | traces: REQ-001-03 | depends_on: TSK-001-02-01

## Wave 2 — Integration & Validation

<!-- Tasks that depend on Wave 1 completing. May be sequential if they share outputs. -->

- [ ] TSK-001-01-03 <!-- Task description --> | traces: REQ-001-01 | depends_on: TSK-001-01-02, TSK-001-03-01

---

## Dependency Graph

<!-- Auto-computed from the tasks above. Update whenever tasks or dependencies change. -->

```
Wave 0 [P]: TSK-001-01-01, TSK-001-02-01
Wave 1 [P]: TSK-001-01-02, TSK-001-03-01
Wave 2:     TSK-001-01-03
```

**Critical path**: TSK-001-01-01 → TSK-001-01-02 → TSK-001-01-03

**Sub-agent allocation**:
- Wave 0: 2 agents (one per task, run in parallel)
- Wave 1: 2 agents (one per task, run in parallel)
- Wave 2: 1 agent (sequential — depends on both Wave 1 tasks)
