# Project TODO - Expand in-app documentation

## Goal
Expand the existing user docs (already shown in dashboards via analytics partials) so they explain how to use each module/feature.

## Scope (per confirmation)
- Only edit the docs templates already used by “Docs Usage” / in-app help:
  - `templates/analytics/docs_usage.html`
  - `templates/analytics/partials/in_app_docs.html`
  - (optionally) `templates/analytics/dashboard_admin.html` and `templates/analytics/dashboard_headmaster_ops.html` only if needed to render new sections
- No new pages, no new apps, no backend logic changes.

## Steps
1. Review all existing module features based on code that affects user workflows:
   - accounts/auth flow
   - schools dashboards + roles
   - academics (students/classes/subjects/enrollment)
   - results (CA/exam, approval, locking)
   - attendance (sessions/recording)
   - fees (structures, invoices, payments, credits, expenses, PDF receipts)
   - analytics dashboards (what tiles/charts represent)
   - messaging/notifications (where users see it)
2. Draft doc sections for each module:
   - where to find it in the UI (menu/sidebar/route name)
   - step-by-step “how to use” (for common tasks)
   - important states/terminology (e.g., invoice statuses: unpaid/partial/overdue; results statuses: submitted/approved/locked)
   - automation notes (fees monthly generation + cron)
3. Implement updates in `templates/analytics/partials/in_app_docs.html`:
   - add structured headings + short steps per module
   - keep it readable (accordion or grouped lists if already consistent)
4. Ensure docs_usage page still works:
   - `templates/analytics/docs_usage.html` should render the updated partial
5. Quick sanity check:
   - verify includes/templates compile (no missing tags/blocks)
   - ensure no broken Django template syntax

## Acceptance
- “Open Docs” and the in-dashboard “Help & Documentation” section contain comprehensive, module-by-module usage guidance.

