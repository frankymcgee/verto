# Voice JHA incident learning

PERI analyses the current crew discussion for potential critical risks and mechanisms, including pinch points and line of fire. It uses the restricted `find_relevant_incidents` tool to retrieve real evidence and explains relevant incident references, findings and investigation actions during the current job step. It proposes controls for crew consideration and only records controls after confirmation. Recording a confirmed hazard also performs a server-side lookup so the evidence is available even if PERI does not explicitly call the search tool.

## Importing the INX InControl dump

After updating Verto, run the normal site migration and asset build. As a System Manager, open **JHA Incident Learning**, choose **Import INX Export**, and upload the original XLSX Summary Events export. The upload is private. Preview the counts before choosing **Import Draft Lessons**. No incident records or original exports are committed to this repository.

The importer reads the `v_EventsReport` worksheet and validates every event before writing. It rejects missing identifiers/dates, duplicate references, duplicate headings, formulas and oversized exports. It accepts up to 2,000 events and a 10 MB XLSX file per import. Text dates use Australian day/month order; typed Excel timestamps are preserved as the original local INX times, without inventing a timezone conversion. Long Short Observations are retained in a text field rather than truncated to the 140-character Title limit.

The supplied Summary Events report has 190 unique work-related injury events, dated 6 January 2025 to 17 September 2026. Every event is Closed and has Immediate Action Taken. Review Date, Reviewed Date and Review Summary are blank throughout. The export does **not** contain separate investigation findings, corrective action records, action completion/effectiveness evidence or recorded preventive controls. These need another INX export or a reviewed investigation source. Immediate response and incident closure must not be substituted for them.

| INX export column | Restricted JHA INX Incident destination |
| --- | --- |
| Reference | INX Reference; stable incident identity |
| Event Date | Event Date, including time |
| Event Type / Event Sub Type | Event Type / Event Sub Type |
| RE Workgroup Name / Workgroup | Separate workgroup fields |
| Location / Country | Location / Country |
| Short Observation / Detailed Observation | Separate original observation text fields |
| Immediate Action Taken | Immediate Action Taken, separate from corrective actions |
| Status | INX Incident Status, separate from action status |
| Moderator Comment | Original Moderator Comment, not an inferred finding |
| Review Date / Reviewed Date / Review Summary | Separate original review fields; blanks remain blank |
| Closed Out Date | Closed Out Date, including time |
| Reported By Name / Originator / Responsible Manager(s) / Closed Out By / Reported By Lookup Name | Excluded from imported records |

`JHA INX Incident` holds the original mapped source fields and phrase-based risk/mechanism suggestions. Only System Managers have access. Narratives can still contain names or medical details even though the five personnel columns are excluded. The original private workbook is attached to a restricted source incident. Unrecognised extra columns are reported in the preview and excluded. Review Summary is preserved as source text, not automatically relabelled as a completed investigation.

Each source produces a linked, disabled `JHA Incident Learning` draft with a generic reference-based title, event metadata and suggested search tags. What Happened, immediate response, investigation findings/actions and controls start blank. Choose **Review INX Source**, prepare an appropriate crew summary and title, review the risk tags, and add only recorded actions/controls from suitable evidence. Keep personal identifiers, medical details and confidential report text out of crew-facing fields. Then enable **Available for JHA** and save. An enabled lesson requires a nonempty crew summary. A changed source fingerprint rejects a stale approval.

The source system and reference produce the same stable SHA-256 ID used by existing incident learning. Reimporting unchanged events preserves approved lesson content, availability and modification time. Changed source content updates the restricted record and disables its lesson until it is reviewed again, while preserving curated summaries, tags, actions and controls. An existing manually imported lesson under the same INX reference is linked and returned to review when its source is first loaded. Import writes use a single transaction; a failed row rolls back the batch. Personnel-only changes do not invalidate a lesson.

Manual imports of already curated learning through Frappe Data Import remain supported. Download its template for Source System, Source Incident Reference, Title, Incident Date, Source Site, What Happened, Critical Risk Categories, Exposure Mechanisms, Immediate Response Recorded, Investigation Findings, Recorded Investigation Actions, Individual Investigation Actions and Controls Recorded in the Source. Use Update Existing Records with exported IDs for later curated imports. Individual action status remains source text; missing status is unknown and a closed action is not assumed effective. Do not duplicate the same actions in flattened text and child rows. Changing an existing source identity is rejected.

Critical risk labels: Uncontrolled Release of Energy; Entanglement and Crushing; Vehicles and Mobile Equipment; Lifting Operations; Dropped Objects; Fall from Height; Contact with Electricity; Confined Space; Hot Works; Working Near Water.

Mechanism labels: Pinch Points; Line of Fire; Caught Between; Entanglement; Struck By; Unexpected Movement; Stored Energy Release; Loss of Containment; Fall; Electric Contact.

These are search categories based on the existing Verto CCV topics, not an exhaustive list of site critical risks. Recognised phrases in the reviewed Title and What Happened also contribute search tags. Restricted source narratives are never queried or returned to the voice models. Map other client labels to this vocabulary when importing; unrecognised explicit tags are rejected so incorrect labels do not silently weaken retrieval. PERI may supply canonical semantic tags when the team uses different words.

## Retrieval and review

Permission-aware `frappe.get_list` queries search enabled lessons by mechanisms and risk categories. Mechanism overlap ranks above a broad risk category; context words and event date break ties. If no recognised signals are present, at least two context words must match. Each query considers up to 100 matching candidates and returns up to three lessons; the response/UI flags truncated searches. This is a bounded matching search, not a complete incident investigation or a vector search.

Authenticated users have read access to enabled crew-facing lessons; System Managers maintain the dataset. The linked INX source and its fingerprint have permission level 1, and all raw narratives live in the separate manager-only DocType. Both voice engines use the same allowlisted evidence fields and exclude raw source data. Access to the JHA itself remains restricted to its Work Summary assignment. Child actions are loaded only for permission-filtered incident parents. Disabling an incident removes it from future results and from refreshed JHA evidence. The tool cannot access arbitrary DocTypes, execute instructions in incident text, advance a step, sign or authorise work.

Draft hazard writes retain reference IDs, matching signals and lookup timestamps in a protected child table, including explicit no-match/unavailable outcomes. Snapshot responses re-read permission-filtered source records; a changed source is flagged. Changing the hazard or activity invalidates the earlier reference fingerprint, and reopening a new JHA revision excludes previous-revision searches. Imported source text is displayed as plain text. Confirmed controls remain in the ordinary JHA hazards table and workpack print format.

The spoken prompt follows Safe Work Australia's [risk-management guidance](https://www.safeworkaustralia.gov.au/safety-topic/managing-health-and-safety/identify-assess-and-control-hazards/managing-risks) by considering higher-order controls and consulting the crew; it does not declare work safe or replace site requirements. [Frappe Database API](https://docs.frappe.io/framework/user/en/api/database) documents permission-aware list retrieval.

## Validation

Run `python -m unittest discover -s tests -p 'test_jha_risk_signals.py'` for vocabulary and ranking tests, and `python -m unittest discover -s tests -p 'test_inx_import.py'` for export mapping and validation. In a test bench, run `bench --site test_site run-tests --app verto --module verto.api.test_inx_incident_import --skip-before-tests` for permissions, repeat imports and changed-source withdrawal. In a test bench, run `bench --site test_site run-tests --app verto --module verto.api.mobile.test_voice_jha_incidents --skip-before-tests`. The CI job includes these tests after a fresh v16 installation. Frontend evidence rendering tests are included in `frontend`'s `test:ui` suite.

The parser has been checked against all 190 events in the supplied workbook. Live microphone behaviour, the Desk upload flow and incident matching still require development-site validation after importing and reviewing the lessons.
