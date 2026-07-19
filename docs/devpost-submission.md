# Devpost submission contract

```yaml
ai_card:
  id: command-center.devpost-submission
  repository: Command Center
  title: Devpost Submission Contract
  kind: submission_receipt
  audience: [operator, presenter, evaluator, ai_agent]
  status: active
  owner_area: submission
  main_files: [README.md, docs/demo-script.md, docs/deployment-checklist.md]
  public_interfaces: [OpenAI Build Week submission, public repository, judge demo]
  provides: [live submission requirements, editable draft receipt, final human gates]
  depends_on: [command-center.demo-script, command-center.deployment-checklist]
  safe_edit_points: [evidence-backed project links and final human-authored copy]
  risk_areas: [missing feedback ID, inaccessible video, premature submission]
  graph_rag_entities: [Devpost, OpenAI Build Week, Codex Command Center]
  last_verified: 2026-07-19
```

## Editable draft

The authenticated individual submitter is registered for **OpenAI Build Week**.
An editable Devpost project exists:

- project ID: `1352380`;
- project slug: `codex-command-center-a8sxp4`;
- project URL:
  `https://devpost.com/software/codex-command-center-a8sxp4`;
- state at verification: `draft`.

The final human-authored description and video URL remain intentionally unset
until the deployed v1.0 artifact and dogfood recording pass their gates.

## Live deadline and deliverables

The submission period closes **July 21, 2026 at 5:00 PM Pacific Daylight Time**,
which is **July 22 at 03:00 Israel Daylight Time**. No submission edits are
available after the deadline.

The live rules require:

1. a working Codex and GPT-5.6 project in one category;
2. a project description;
3. a public or unlisted YouTube demonstration shorter than three minutes, with
   audio covering both Codex and GPT-5.6;
4. a public repository with the relevant license, or a private repository
   shared with both judge addresses;
5. a `/feedback` Codex session ID from the primary build thread;
6. for a developer tool, installation instructions, supported platforms, and
   a judge-test path that does not require rebuilding.

The video must be checked in an incognito window and must not contain
unlicensed music, copyrighted material, or unrelated third-party trademarks.

## Submission field map

| Field ID | Required value |
|---|---|
| `27945` | `Individual` |
| `27946` | `Israel` |
| `27947` | `Developer Tools` |
| `27948` | `https://github.com/verbalogicproject-creator/codex-command-center` |
| `27949` | Deployed judge URL, private demo code, and concise test instructions |
| `27950` | Human-captured `/feedback` session ID |
| `27951` | Plugin installation, supported platforms, and hosted testing path |

The final submit action is blocked until the video URL, `/feedback` ID,
human-authored description, deployed judge URL, and real dogfood receipts are
available. The [three-minute demo script](demo-script.md) is the recording
source of truth.
