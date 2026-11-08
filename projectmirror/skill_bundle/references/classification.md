# Evidence-aware classifications

| Verdict | Minimum justification | Never infer from |
|---|---|---|
| complete | Mapped implementation + current passed evidence for **all named acceptance criteria** | Code files alone or stale tests |
| missing | Reviewed explicit exhaustive-scoped absence confirmation or reviewed `absent_confirmed` implementation state | One grep returning nothing |
| partial | Reviewed link to an explicitly `partial` implementation | Number of TODO comments |
| broken | Current failed check with evidence for approved requirement | A guess based on code style |
| mismatch | Current evidenced result contradicts accepted behavior | Different naming convention |
| unverified | Implementation mapped but relevant current evidence absent/incomplete | Assuming success |
| unknown | No reviewed link, incomplete coverage, draft intent, inaccessible code | Assuming missing |
| undocumented | Explicit discovered capability/endpoint with no reviewed requirement mapping | Every orphan source file |
| spec_conflict | Contradictory user requirements that require clarification | Arbitrary preference |

**Important:** Severity and confidence are separate dimensions. This MVP intentionally does *not* compute arbitrary severity scores or claim full functional test coverage. The model should explain evidence quality and limitations before proposing changes.

Review from two directions: requirements → implementation and implementation capabilities → requirements. Inventory only maps structure, so do not treat every scanned file as an undocumented feature.
