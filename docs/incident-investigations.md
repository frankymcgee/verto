# Verto Investigations

The dedicated app opens at `/investigations` and appears as **Verto
Investigations** on the Frappe apps screen. It lives in the existing Verto app,
with its own frontend, access roles and default-app identifier. Planner and
Mobile keep their existing routes and permissions.

## Deployment and access

Run the normal Verto migration and asset build. The build now installs and
builds `investigations/` as well as `planner/` and `frontend/`. The schema creates
`Verto Investigation`, its evidence/analysis/action/history child tables, and
the previously missing `EHS ICAM Factors` child model referenced by EHS Incident.
Existing incidents and submitted EHS records are not converted or rewritten.

Migration creates these roles and matching Role Profiles:

| Role                           | Access                                                                                                                                                                           |
| ------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Verto Investigator             | Create a draft as lead; read investigations where assigned as lead, reviewer or team member; contribute as an investigator or subject matter expert. Observers have read access. |
| Verto Investigation Manager    | Access all investigations; be appointed as an independent reviewer; close, reopen or cancel actions with recorded reasons.                                                       |
| System Manager / Administrator | Management access, with the same independent-review and action-verification boundaries.                                                                                          |

Assign the appropriate profile to users. Existing Planner/Mobile profiles do not
automatically grant investigations access. Source incident lookups also respect
the user's existing permissions on EHS Incident and Shutdown Incident Tracker.

The app is selectable as a separate default app, `verto_investigations`.

## Investigation process

1. Create a standalone record or link an accessible EHS Incident or Shutdown
   Incident Tracker record. Copying source details fills empty fields; inspect
   the event time and its precision. A shutdown date without an exact time is
   explicitly marked **Date only**.
2. Record the event, immediate response, consequences, project/site and
   reportability assessment. Appoint a lead, independent manager reviewer and
   the investigation team.
3. Gather evidence under PEEPO categories. Add observations, private files and
   a verification basis. Changing a verified item's content withdraws its
   verification until it is checked again. Build the event timeline and link
   the supporting evidence.
4. Select **5 Whys**, **ICAM**, or **5 Whys + ICAM**. Findings start as
   hypotheses. Resolve them to Supported or Not supported before review.
5. Map supported causes/factors to corrective actions. Assign an owner, due
   date, hierarchy-of-control category, effectiveness criteria, independent
   verifier and verification due date.
6. Submit for review. The app checks evidence, unresolved hypotheses, causal
   branches, ICAM category coverage and action mappings. Content locks while
   the appointed independent reviewer approves it or returns it with reasons.
   The lead or a manager can withdraw it for revision with a recorded reason,
   including when its appointed reviewer has left the business.
7. After approval, owners record completion evidence. The appointed independent
   verifier records effectiveness or sends the action back for further work.
   Investigation managers can cancel an action with a recorded reason.
   Managers can also reassign outstanding responsibilities with reasons;
   completed work retains its recorded owner and completion evidence when a
   replacement verifier is appointed. Historic users remain in the record
   after their accounts are deactivated.
8. Close only after actions are verified effective or cancelled with reasons,
   and the reportability assessment is complete. Record the close-out summary.
   A manager can reopen with reasons; fresh investigation review is required.

The workflow is Draft → Evidence Gathering → Analysis → In Review → Actions
in Progress → Closed, with Reopened for subsequent investigation work. The
evidence and analysis stages can be entered from a draft without forcing an
otherwise unnecessary transition.

### Analysis details

5 Whys supports multiple branches and a variable number of questions. Every
supported terminal branch needs a root-cause designation and stopping rationale;
five answers alone do not establish a root cause. Circular/orphaned links are
rejected. Deleting an intermediate draft why retains its descendants under the
preceding cause and clears any dangling cross-references in the app.

ICAM groups factors into the four standard categories, records supporting
evidence and explicit factor-to-factor relationships, and presents a grouped
causal map. Non-defence factors must connect to a supported causal pathway.
Where a category has no supported finding, investigators record the reason
rather than invent a factor. A completed ICAM analysis must identify at least
one supported absent/failed defence.

Method references:

- [Safety Wise: direction and causal relationships in ICAM](https://www.safetywise.com/post/why-good-investigators-work-backwards)
- [Lean Enterprise Institute: 5 Whys](https://www.lean.org/lexicon-terms/5-whys/)

## Record handling and reports

The workspace uses Frappe UI 1.0.2, pinned in the Investigations package and
lockfile. Desktop navigation uses its DesktopShell and collapsible Sidebar;
narrow screens use MobileShell, MobileNav and a section selector. Form controls,
permission-filtered Combobox lookups, badges, alerts and decision/discard dialogs
use the same component library. The print report is rendered outside the screen
shell so its fixed header, sidebar, mobile navigation and overlays do not print.

The server applies record permissions to lists and individual reads. Mutations
lock the record and require the caller's last-seen modification timestamp.
Stale saves fail while the browser retains the user's unsaved changes.

Approval, action verification and close-out fields are server-controlled.
Workflow history and Frappe Versions retain decisions and changes. Completed
actions cannot be silently deleted or rewritten during reopened analysis.
Investigation records and their private attachments are retained. File lifecycle
checks run before File's own insertion/deletion handlers; evidence cannot be
made public or detached through ordinary File editing.

**Print / PDF** produces a report from the saved record, including evidence
references, analysis, action outcomes, review decisions and workflow history.
Attachment references identify separate private files; printing does not embed
their bytes. Use the browser's PDF destination to save the report.

Raw investigation and witness material is kept separate from the existing
reviewed JHA Incident Learning dataset. Publication into crew-facing lessons
requires that dataset's separate curation and sanitisation workflow.

## Validation

Run `yarn test:ui` and `yarn build` in `investigations/`. Standalone analysis
checks run with `python -m unittest discover -s tests -p
'test_investigation_rules.py'`. Fresh-site CI also runs
`verto.api.test_investigations` for actual database permissions, stale edits,
approval/action/close-out transitions, evidence invalidation and private file
retention, plus `verto.test_default_apps` for independent app selection.
