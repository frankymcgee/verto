<div align="center" markdown="1">
<img src="https://webwire.com.au/files/verto-icon-clear.png" alt="Logo" width="80" height="80">
<h1 align="center">Webwire Verto</h1>
**ERPNext v15 Custom App for Operations, Safety, Project Controls, Mobile Workflows and AI-Assisted Insights**

</div>

---

## About The Project

**Webwire Verto** is a custom ERPNext/Frappe application developed to extend ERPNext Version 15 with practical tools for project delivery, shutdown management, safety workflows, mobile field operations, dashboards, automation, and AI-assisted decision support.

The app was originally created to enhance ERPNext for operational and project-based environments where field teams, supervisors, safety advisors, and project leaders require improved visibility, streamlined mobile workflows, and structured safety management processes.

---

## Key Features

### ERPNext v15 Enhancements

- Custom ERPNext Version 15 functionality
- Enhanced task, project, and shutdown workflow support
- Custom reports and dashboard extensions
- Improved project and task visibility
- Workflow automation through custom scripts and server methods

### Map and Geolocation Improvements

- Enhanced map view customization
- Topographical map support
- Improved geolocation display and tracking
- Field-based task and work area visibility

### Gantt and Project Controls

- Enhanced Gantt chart functionality
- Improved task grouping and work area visibility
- Shutdown and project-specific task navigation
- Project scope filtering support
- Integration with Gameplan, handover records, folders, and Raven channels

### Mobile Browser Experience

- Mobile-friendly ERPNext interfaces
- Bottom navigation for improved usability
- Simplified task and form access
- Assigned task dashboards
- Mobile-first form submission workflows
- Quick access to Gantt, Maps, Handover, Gameplan, Folders, and Chat

### Work Health & Safety Module

- Safety metrics tracking and reporting
- Field interaction workflows
- Critical Control Verification (CCV) workflows
- Contractor and supervisor safety insights
- Positive and at-risk behaviour tracking
- Compliance percentage reporting
- Areas-for-improvement reporting
- Safety handover and lead safety handover support

### Dashboard and Insights Support

- Frappe Insights workbook and dashboard integration
- Shutdown Safety Metrics dashboard support
- Compliance trend analysis
- Contractor compliance reporting
- Work area compliance reporting
- Critical Control Verification compliance cards
- Positive and at-risk behaviour visualizations
- Project scope filtering across dashboards

### Raven and PERI AI Integration

- Raven chat integration
- Project-specific Raven channel linking
- User-specific PERI direct message channel support
- PERI dashboard analysis triggers from assigned task views
- Backend methods for sending PERI analysis commands to Raven
- AI-assisted dashboard interpretation and insights

---

## Example Use Cases

Webwire Verto supports workflows such as:

- Managing shutdown safety performance
- Reviewing task and work area compliance
- Completing field safety forms from mobile devices
- Tracking positive and at-risk behaviours
- Monitoring contractor safety performance
- Triggering PERI AI dashboard analysis from project task lists
- Navigating between assigned tasks, Gantt charts, maps, handovers, Gameplans, folders, and project chat channels
- Delivering mobile-friendly ERPNext experiences for field teams

---

## Technology Stack

- Frappe Framework
- ERPNext v15
- Frappe Insights
- Raven
- Python
- JavaScript
- HTML/CSS
- MariaDB
- Mobile Browser and PWA-focused ERPNext customizations

---

## Installation

Install this application into an existing Frappe/ERPNext bench.

```bash
cd frappe-bench
bench get-app verto <repository-url>
bench --site <site-name> install-app verto
bench build
bench restart
```

Replace:

```text
<repository-url>
```

with the GitHub repository URL.

Replace:

```text
<site-name>
```

with your ERPNext site name.

---

## Development Notes

This application is designed to be customized for specific ERPNext v15 environments. Some functionality may depend on custom DocTypes, custom fields, Raven configuration, Frappe Insights dashboards, or organization-specific workflows.

Before deploying to production, review and configure:

- Custom DocTypes
- Custom Fields
- Client Scripts
- Server Scripts and backend API methods
- Role permissions
- Raven workspaces and channels
- Frappe Insights dashboards
- Mobile workspace pages
- Safety workflow configurations

---

## Project Status

This project is under active development and continues to evolve with new ERPNext, safety, mobile, reporting, and AI-assisted workflow capabilities.

---

## License

Distributed under the Apache License 2.0.

For more information, see the [Apache License 2.0](https://www.apache.org/licenses/LICENSE-2.0).

---

## Maintained By

**Webwire**

Website: [https://webwire.com.au](https://webwire.com.au)
