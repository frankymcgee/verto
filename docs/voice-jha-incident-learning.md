# Voice JHA incident learning

PERI analyses the current crew discussion for potential critical risks and mechanisms, including pinch points and line of fire. It uses the restricted `find_relevant_incidents` tool to retrieve real evidence and explains relevant incident references, findings and investigation actions during the current job step. It proposes controls for crew consideration and only records controls after confirmation. Recording a confirmed hazard also performs a server-side lookup so the evidence is available even if PERI does not explicitly call the search tool.

## Importing the INX InControl dump

`JHA Incident Learning` is the crew-facing incident dataset. After updating Verto, run the normal site migration and asset build. A System Manager can import records using Frappe Data Import; download its template with the fields below, and include the child action table if the export contains individual actions. No INX export or sample records are included in this release. Actual INX column mapping must be established from the supplied export; these are Verto destination fields, not claims about INX column names.

| Verto destination | Source information |
| --- | --- |
| Source System | INX InControl (default) or another named system |
| Source Incident Reference | Stable incident identifier from the export (required) |
| Title | Incident title (required) |
| Incident Date | Event date, when recorded |
| Source Site | Source site label, when appropriate to share with crews |
| What Happened | Crew-facing event summary (required) |
| Critical Risk Categories | Canonical labels below, separated by semicolons or newlines |
| Exposure Mechanisms | Canonical labels below, separated by semicolons or newlines |
| Investigation Findings | Findings actually recorded in the investigation |
| Recorded Investigation Actions | Flattened actions text if the export has one actions column |
| Individual Investigation Actions | Source action reference, recorded action, source status and effectiveness evidence |
| Controls Recorded in the Source | Controls or lessons actually recorded in the investigation |
| Available for JHA | 1 to include the record, 0 to exclude it |

Use summaries intended for crew learning. Do not map names, medical information, confidential raw reports or other personal identifiers into this dataset. Existing `EHS Incident` and `Shutdown Incident Tracker` documents are not automatically exposed; a source incident's learning can be imported under its original reference. Individual action status is preserved as source text; a missing status is unknown and a closed action is not assumed effective. Do not duplicate the same actions in both flattened text and child rows.

Source system plus source reference produces a stable SHA-256 document ID and a unique source key. Repeated insert imports fail on duplicate incidents instead of creating duplicates. For later dumps, use Data Import's Update Existing Records and the IDs from an exported Verto template. Changing the source identity on an existing record is rejected.

Critical risk labels: Uncontrolled Release of Energy; Entanglement and Crushing; Vehicles and Mobile Equipment; Lifting Operations; Dropped Objects; Fall from Height; Contact with Electricity; Confined Space; Hot Works; Working Near Water.

Mechanism labels: Pinch Points; Line of Fire; Caught Between; Entanglement; Struck By; Unexpected Movement; Stored Energy Release; Loss of Containment; Fall; Electric Contact.

These are search categories based on the existing Verto CCV topics, not an exhaustive list of site critical risks. Recognised phrases in What Happened also contribute search tags. Map other client labels to this vocabulary when importing; unrecognised explicit tags are rejected so incorrect labels do not silently weaken retrieval. PERI may supply canonical semantic tags when the team uses different words.

## Retrieval and review

Permission-aware `frappe.get_list` queries search enabled lessons by mechanisms and risk categories. Mechanism overlap ranks above a broad risk category; context words and event date break ties. If no recognised signals are present, at least two context words must match. Each query considers up to 100 matching candidates and returns up to three lessons; the response/UI flags truncated searches. This is a bounded matching search, not a complete incident investigation or a vector search.

Authenticated users have read access to enabled crew-facing lessons; System Managers maintain the dataset. Access to the JHA itself remains restricted to its Work Summary assignment. Child actions are loaded only for permission-filtered incident parents. Disabling an incident removes it from future results and from refreshed JHA evidence. The tool cannot access arbitrary DocTypes, execute instructions in incident text, advance a step, sign or authorise work.

Draft hazard writes retain reference IDs, matching signals and lookup timestamps in a protected child table, including explicit no-match/unavailable outcomes. Snapshot responses re-read permission-filtered source records; a changed source is flagged. Changing the hazard or activity invalidates the earlier reference fingerprint, and reopening a new JHA revision excludes previous-revision searches. Imported source text is displayed as plain text. Confirmed controls remain in the ordinary JHA hazards table and workpack print format.

The spoken prompt follows Safe Work Australia's [risk-management guidance](https://www.safeworkaustralia.gov.au/safety-topic/managing-health-and-safety/identify-assess-and-control-hazards/managing-risks) by considering higher-order controls and consulting the crew; it does not declare work safe or replace site requirements. [Frappe Database API](https://docs.frappe.io/framework/user/en/api/database) documents permission-aware list retrieval.

## Validation

Run `python -m unittest discover -s tests -p 'test_jha_risk_signals.py'` for vocabulary and ranking tests. In a test bench, run `bench --site test_site run-tests --app verto --module verto.api.mobile.test_voice_jha_incidents --skip-before-tests`. The CI job includes these tests after a fresh v16 installation. Frontend evidence rendering tests are included in `frontend`'s `test:ui` suite.

Live microphone/Realtime behaviour and matching against the real INX dataset still require development-site validation after importing the export.
