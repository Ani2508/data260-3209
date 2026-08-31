# DOMAIN_SCHEMA.md

**Domain:** Clinical Trial Listings
**DOMAIN_ID:** 1
**Entity:** Clinical Trial

A single record describes one clinical trial submitted to the public listing
catalogue by a trial coordinator, sponsor, or research institution (the poster),
not by a patient. The listing is a public record of the study across its whole
lifecycle.

## Fields

| Field | Key | Type | Required | Description |
|-------|-----|------|----------|-------------|
| Trial Title | `trialTitle` | text | yes | Primary field. Official name of the study. |
| Sponsor / Institution | `sponsor` | text | yes | Secondary field. Organization running the trial. |
| Submitter Email | `email` | email | yes | Email of the person submitting the listing. |
| Trial Summary | `content` | textarea | yes | Description / eligibility summary. Must be > 25 characters. |
| Status | `status` | select | yes | Category field. Current lifecycle state of the trial. |
| Terms Agreement | `terms` | checkbox | yes | Confirms agreement to terms and conditions. |

## Category Values (Status)

The `status` dropdown has exactly four domain-appropriate options representing
where the trial currently stands in its lifecycle:

1. **Recruiting** — actively enrolling new participants.
2. **Active – Not Recruiting** — running, but no longer enrolling.
3. **Completed** — finished; results may be available.
4. **Terminated** — stopped early before planned completion.
