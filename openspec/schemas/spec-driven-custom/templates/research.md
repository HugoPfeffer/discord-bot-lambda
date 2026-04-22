<!-- RESEARCH CONTEXT — Reference material only. Do NOT treat findings as new requirements.
     These notes describe existing state and known constraints; the spec defines desired state. -->

## Knowledge Gaps

<!-- List each external dependency or unknown identified from the proposal.
     One gap per line. These drive the parallel research sub-agents. -->

1. <!-- Gap 1: e.g., "How does <library X> handle pagination for cursor-based results?" -->
2. <!-- Gap 2: e.g., "What are the rate limits for <external API Y>?" -->
3. <!-- Gap 3: e.g., "What does the existing <module Z> expose that we can reuse?" -->

---

## Findings

<!-- One section per gap. Cite source URLs for every factual claim.
     Mark unresolved gaps clearly — do not fabricate findings. -->

### Gap 1: <!-- Repeat gap title -->

**Status**: Resolved | Unresolved — requires human input | Conflict — requires resolution

**Summary**: <!-- 2-4 sentences synthesizing what was found -->

**Key facts**:
- <!-- Fact 1 — [Source](<url>) -->
- <!-- Fact 2 — [Source](<url>) -->

**Conflicts**: <!-- If sources disagree, document both positions and flag for human resolution -->

---

### Gap 2: <!-- Repeat gap title -->

**Status**: Resolved | Unresolved — requires human input | Conflict — requires resolution

**Summary**:

**Key facts**:
-

---

## Constraints

<!-- Hard limits discovered during research that MUST constrain spec scenarios and design decisions.
     These are non-negotiable facts, not preferences. -->

| Constraint | Source | Impact on Specs/Design |
|------------|--------|------------------------|
| <!-- e.g., API rate limit: 100 req/min --> | [Link](<url>) | <!-- e.g., SCN-001-02-01 must account for 429 response --> |
| | | |

## Recommendations

<!-- Actionable suggestions flowing from the research into the spec and design phases.
     Each recommendation should link to the gap it resolves and the artifact it informs. -->

- **Spec impact** (Gap 1): <!-- e.g., "Add SCN for rate-limit exceeded path in REQ-001-02" -->
- **Design impact** (Gap 2): <!-- e.g., "Prefer library X over Y — better pagination support per [finding]" -->
- **Open questions for human**: <!-- Items that research could not resolve; need decision before specs are finalized -->
