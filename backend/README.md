<!-- Fungsi file: Panduan setup, endpoint, aturan fitur, pengujian, dan batas implementasi backend. -->

# SIMEVENT backend

Phases 1–9 implement accounts, authentication, organizer proposals, events, approval,
registration, tickets, QR generation, attendance, feedback, achievements, reward policies and statistics
using Django 5.2 LTS and PostgreSQL.
Frontend integration is deferred. The account views return small JSON responses
using ordinary Django views, Forms, sessions, and CSRF; there is no DRF or JWT.
These forms/models can be reused by MVT template views during integration.

## Statistics (phase 9)

- `GET /registrations/statistics/`: dashboard summary and event metrics, 20 events
  per page (`?page=2`). Summary covers all accessible events, not just the page.
- `GET /registrations/events/<event_id>/statistics/`: metrics for one event.

Organizer access is restricted to owned events. Platform Admin can see all events.
Both endpoints require event-view and feedback-view permissions in addition to
the organizer/platform capability. Another organizer's event returns 404.
Responses are read-only and uncached; no participant identities, feedback text,
ticket tokens or private meeting information are included.

Metric definitions:

| Field | Meaning |
| --- | --- |
| `total_registrations` | Stored registration rows, including cancelled registrations; reactivation reuses the row. |
| `active_registrations` / `cancelled_registrations` | Counts by registration status, including historical cancelled events. |
| `unique_participants` | Distinct participants across those registration rows, including historical cancellations. |
| `eligible_registrations` | Active registrations on PUBLISHED or COMPLETED events. |
| `total_attendance` | PRESENT attendance for eligible registrations. |
| `recorded_check_ins` / `voided_check_ins` | Historical attendance rows / rows explicitly voided. |
| `attendance_rate` | Valid attendance divided by eligible registrations, percentage string with two decimals; null if no denominator. |
| `feedback_count` / `average_*_rating` | Feedback with active registration, PRESENT attendance and COMPLETED event; null averages when none qualify. |

Dashboard summary also supplies `total_events` and `events_by_status`. Overall
rates and averages are calculated from underlying records, not averages of event
averages. An event with registrations and no attendance has a `0.00` rate.
Dashboard rows include event ID, title, status, capacity, start time and event type
code. No date, demographic or revenue filters are implemented.

The normal nonempty dashboard uses four data queries and event detail uses two,
excluding session/authentication permission queries. Separate summary/page queries
can observe concurrent updates at different instants; this is an operational
dashboard, not an accounting snapshot. No new migration or dependency is required.

## Setup

Use Python 3.12–3.14 and a running PostgreSQL instance (validation used PostgreSQL 18).
Run from `backend/`:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

Create a local `.env` using `.env.example` as a reference. Set a random
`DJANGO_SECRET_KEY` and your own database credentials. To generate a secret:

```bash
.venv/bin/python -c 'import secrets; print(secrets.token_urlsafe(64))'
```

The application reads environment variables, not `.env` files automatically.
For a trusted local `.env` containing shell-compatible assignments:

```bash
set -a
source .env
set +a
.venv/bin/python manage.py migrate
.venv/bin/python manage.py bootstrap_roles
.venv/bin/python manage.py createsuperuser
.venv/bin/python manage.py runserver
```

The database must already exist and belong to the configured PostgreSQL user.
For local tests, that database user needs permission to create a test database.
Do not grant production database accounts this permission just for testing.
PostgreSQL is mandatory; no SQLite fallback is configured.

## Account endpoints

| Method | Path | Input/result |
| --- | --- | --- |
| GET | `/accounts/csrf/` | CSRF token and cookie |
| POST | `/accounts/register/` | email, first_name, last_name, password1, password2 |
| POST | `/accounts/login/` | email, password; creates Django session |
| POST | `/accounts/logout/` | Invalidates current session |
| GET | `/accounts/profile/` | Current account only; 401 without session |

POST bodies are form-encoded, not JSON. Send the CSRF token as
`X-CSRFToken` and retain cookies. Login rotates the CSRF token: fetch a fresh token
after login before making another mutation. Registration does not auto-login.
Errors use `{"errors": {"field": [{"message": "...", "code": "..."}]}}`.
Successful registration returns 201; validation failures return 400.
No endpoint accepts a target account ID, role, owner, or permission assignment.

## Roles and administration

New users are participants with no privileged group. `role` is a derived display
property, never a client-writable database field. All email addresses are
normalized to lowercase; a database constraint prevents case-variant duplicates.

Run `bootstrap_roles` after applying the new migrations too. It is idempotent
and does not assign any users:

- Organizer: `accounts.access_organizer` and event create/view/edit/delete,
  submit/complete/cancel permissions, constrained to owned events.
- Platform Admin: global administration, organizer grant/revoke, account
  suspension/activation, proposal/event review, publication, event type management,
  and read access to users and audit logs.

`is_staff` only allows entry to Django Admin; it is not platform authorization.
Only superusers may edit ordinary account fields. Non-superusers remain read-only
even if accidentally granted `change_user`; Platform Admins instead use audited
actions for organizer access and activation state. These workflow fields are
read-only on the user edit form, including for superusers. Account deletion is
disabled in Admin; suspend instead to preserve history.

Provision trusted administrative users through `createsuperuser`, or assign the
Platform Admin group and `is_staff=True` through a trusted operator using Django's
shell. Public registration never exposes this operation. Group/permission
configuration and shell access remain trusted maintenance capabilities, not
ordinary organizer-management workflows.

`require_organizer` checks capability and active status. It does **not** implement
event ownership. Event endpoints additionally use `Event.objects.managed_by(user)`.
Permissions are evaluated on each request using Django's normal request-local
user object. Do not retain authenticated User objects across requests.

## Organizer proposals (phase 2)

All applicant endpoints require a session, operate on the current user's own
proposals, and use form-encoded POST with CSRF as above:

| Method | Path | Operation |
| --- | --- | --- |
| GET | `/partnerships/proposals/` | Own proposals, 20 per page (`?page=2`) |
| POST | `/partnerships/proposals/` | Create draft |
| GET | `/partnerships/proposals/<id>/` | Own proposal and review reasons |
| POST | `/partnerships/proposals/<id>/` | Edit draft or requested revision |
| POST | `/partnerships/proposals/<id>/submit/` | Submit/re-submit for review |
| POST | `/partnerships/proposals/<id>/delete/` | Delete unsubmitted draft; `confirm=on` required |

Content fields: `organization_name` (200 characters), `contact_information` (500),
and `proposal_text` (10000). All three are required, including when saving a draft.
Applicant, status and timestamps are assigned server-side. One open proposal per
applicant is enforced by PostgreSQL. Rejected applicants may start a new proposal.
Submitted, approved and rejected content cannot be edited. Only unsubmitted drafts
may be deleted; submitted history is retained. Participants with existing organizer
or platform access cannot open or submit another proposal.

Out-of-scope IDs return 404, unauthenticated requests return 401, business/form
errors return 400, and denied capabilities return 403. Proposal business errors
use `{"errors": {"field_or___all__": ["message"]}}`.

In Django Admin, select **one** proposal, choose Approve/Request revision/Reject,
enter a reason and tick the confirmation field. Approval also requires organizer
grant permission. Generic edit/delete cannot bypass the workflow, even for a
superuser. Approval, organizer membership and both audit records commit together.
Replaying approval after access revocation is rejected. Applicants cannot review
their own proposals, even if later granted administrative privileges.

On the User changelist, the same native action controls support grant/revoke
organizer access and suspend/activate. Each requires a reason and confirmation.
Use proposal approval for a pending proposal; manual grant is a separate admin
decision and does not approve or alter existing proposal history. Administrators
cannot use these actions on themselves or other platform administrators. Changes
to privileged administrators remain a trusted maintenance operation.

Revocation removes the Organizer group and any direct organizer permission. If
another group also grants that permission, it refuses the operation with an
explicit error so the operator can resolve the conflicting configuration.
Suspension blocks authentication/access while inactive; activation preserves the
account's group assignments. Audit records are read-only in Django Admin.

## Events (phase 3)

Public responses only include published/completed events and an explicit field
allowlist. Meeting URLs, access instructions, review history and owner email are
never included. Managed endpoints require active organizer or platform access;
other organizers' IDs return 404. Mutation services independently recheck scope,
permissions and state using fresh, locked database records.

| Method | Path | Operation |
| --- | --- | --- |
| GET | `/events/` | Public catalogue; 20 per page |
| GET | `/events/<slug>/` | Public detail |
| GET/POST | `/events/manage/` | Own events / create draft |
| GET/POST | `/events/manage/<id>/` | Own private detail / update content |
| POST | `/events/manage/<id>/<action>/` | State transition |
| POST | `/events/manage/<id>/delete/` | Delete unsubmitted draft; `confirm=on` |

Platform administrators have global scope. Creation by an administrator requires
an explicit `organizer` pointing to an active organizer. Ordinary organizer input
cannot assign owner, slug or status. Ownership cannot be transferred through edit.

Content fields: `title`, `description`, `event_type` (ID), `delivery_mode`
(`OFFLINE`, `ONLINE`, `HYBRID`), `start_datetime`, `end_datetime`, `venue`, `capacity`,
`price`, `registration_open`, `registration_close`, optional `banner`,
`meeting_url`, `access_instructions`, and `remove_banner`.
Updates submit the complete form, including private access fields. Use ISO-8601
timestamps with timezone offsets. Omitted banners are retained; use
`remove_banner=on` to remove them. Use multipart form data for image uploads.

Four event types are seeded: CONFERENCE, WORKSHOP, SEMINAR, WEBINAR. Type is
independent of delivery mode. Administrators can add/deactivate types in Django
Admin; existing codes stay immutable to preserve reporting semantics.

| Action | From → to | Who / extra conditions |
| --- | --- | --- |
| `submit` | DRAFT / NEEDS_REVISION → SUBMITTED | Owner or Admin; ready for review |
| `request_revision` | SUBMITTED / APPROVED → NEEDS_REVISION | Admin; reason required |
| `approve` | SUBMITTED → APPROVED | Admin; ready for review |
| `reject` | SUBMITTED → REJECTED | Admin; reason required |
| `publish` | APPROVED → PUBLISHED | Admin; readiness rechecked |
| `unpublish` | PUBLISHED → APPROVED | Admin; before event starts |
| `complete` | PUBLISHED → COMPLETED | Owner or Admin; at/after end time |
| `cancel` | Any nonterminal state → CANCELLED | Owner or Admin; before end, reason required |

Only DRAFT/NEEDS_REVISION content is editable. Only DRAFT can be physically deleted.
COMPLETED, REJECTED and CANCELLED are terminal. Ongoing is derived from time;
completion is explicit, without a scheduler. Unpublishing before start allows
safe review/republication; an underway event can be cancelled instead.

Readiness requires an active organizer/type, future start, valid date windows and
zero price. Offline/hybrid events need a venue; online/hybrid need an HTTPS meeting
URL. Paid events can be saved as drafts but cannot be submitted or published until
payment support is implemented. Registration closing must be no later than start.

Native Django Admin exposes review/publication actions with one selected event,
a reason and confirmation. Ordinary Admin edits/deletes of events are disabled,
including for superusers; content creation/editing uses the same managed endpoints
and forms. Transition history and private access records are read-only in Admin.
Event type deactivation blocks new submissions/publications; it does not silently
remove already published events. Revoking an owner's organizer access blocks their
management and new publication, while Admin retains moderation access.

Banners accept JPEG/PNG/WebP up to 5 MiB and 4096 pixels per dimension, verified by
Pillow and stored under random filenames. Replacement/removal deletes old files
after commit; failed content writes clean up newly uploaded files. Storage is not
transactional: process crashes or caller-owned outer transaction rollbacks can
still leave orphan files, so deployment needs an orphan cleanup policy.
`MEDIA_ROOT` is local `backend/media/`; configure media serving separately using
a dedicated untrusted-media origin. No media-serving development route is added.
Only banners belong there; private meeting information stays in protected data.

See [OOP.md](OOP.md) for concrete examples of all four OOP pillars.

## Registration and tickets (phase 4)

All endpoints require a session. POST uses form data with CSRF and `confirm=on`.
Participant identity always comes from the session; no input can assign another
participant, ticket token, registration status or payment state.

| Method | Path | Operation |
| --- | --- | --- |
| GET | `/registrations/` | My registrations, including cancelled; 20 per page |
| POST | `/registrations/events/<event_id>/register/` | Register or reactivate |
| POST | `/registrations/<id>/cancel/` | Cancel own registration |
| GET | `/registrations/<id>/ticket/` | Own ticket identifier, validity and token |
| GET | `/registrations/events/<event_id>/participants/` | Owner/Admin participant list |

Registration requires a published, upcoming, free event, an open registration
window (`open <= now < close`) and an available seat. Any active account may
participate, including organizers; organizer privileges do not grant the ability
to register or cancel on behalf of others. Duplicate active registration returns
400. Nonpublic event IDs and another participant's record IDs return 404.

One participant/event pair has one persistent registration. Cancellation is
available before event start (or at any time if the event itself is cancelled),
releases the seat and disables the ticket. Repeated cancellation is idempotent.
Reactivation rechecks every registration rule, reuses the same registration and
ticket identifier, resets `registered_at` to the latest registration time, and
rotates the ticket token. The old token no longer identifies a ticket.
This phase stores current registration state, not a separate lifecycle audit log.

Registration and ticket issuance commit together. Seat changes lock the event
row, serializing concurrent registrations, cancellations and event transitions.
An event revision cannot lower capacity below active registrations.

Ticket identifiers and tokens are separate random UUID4 values. Only the ticket's
participant can retrieve its token through HTTP; lists and native Admin omit it.
Invalid tickets return `token: null`. Validity additionally requires an active
participant, active registration, published event and an end time in the future.
Unpublishing or cancelling the event immediately makes tickets invalid without
rewriting registration history; republishing restores validity if all conditions
still hold. Event cancellation does not automatically change each registration's
stored status. Future reports must also consider event status.

Participant lists include name/email for the scoped organizer or global Admin,
with pagination and joined queries. Registration and Ticket are read-only in
Django Admin, including for superusers. Use cancellation rather than destructive
deletion to retain history.

QR, scanner redemption, attendance and participant meeting access are described
below. There is no payment gateway or attendance/achievement inference from
registration. Media/frontend integration is unchanged.

## QR and attendance (phase 5)

| Method | Path | Operation |
| --- | --- | --- |
| GET | `/registrations/<id>/ticket/qr/` | Own valid ticket as private PNG |
| GET | `/registrations/<id>/meeting/` | Own valid ticket's meeting URL/instructions |
| GET | `/registrations/<id>/attendance/` | Own attendance status/time |
| POST | `/registrations/events/<event_id>/scan/` | Owner/Admin scans `token` |

QR uses qrcode 8.2 with existing Pillow, generated in memory without a public
media file. The payload is the ticket's UUID token only, not a URL, participant
record or authorization claim. Endpoints require session authentication and use
no-store responses. Meeting access requires the same active ticket entitlement;
public event responses remain unchanged. Access already downloaded or a meeting
URL already copied cannot be recalled by the server.

Scanner input is form-encoded `token=<uuid>` with CSRF and a session. A camera UI
must decode the QR locally and POST its token; camera/scanner frontend is deferred.
Tokens must not appear in URL query strings or application/proxy request-body logs.
The scanner is marked sensitive for Django error reports.

Scanning requires active organizer capability, `registrations.scan_ticket`,
and ownership of the selected event; Platform Admin can scan globally. The server
rechecks the event, current ticket token, active registration, participant account
and event schedule. The selected rule is `start <= now < end` for PUBLISHED events;
there is no early check-in window in this phase.

A successful first scan returns 201 and `already_checked_in: false`. A repeat
during the valid window returns 200 with `already_checked_in: true`, preserving
the original timestamp and verifier. Invalid/malformed/other-event tokens return
400 with a generic error; out-of-scope event IDs return 404. Registration does not
become completed merely because it has been scanned.

Attendance is OneToOne with Registration. Its state is PRESENT or VOIDED;
NOT_CHECKED_IN in responses means there is no stored attendance. Owners see
attendance in their paginated participant list. Participant detail exposes only
status/time, not internal moderation reasons or verifier contact information.

Admin can void a mistaken attendance through the native Attendance changelist:
select one row, supply a reason and confirm. Original check-in/verifier are retained,
with void time/actor/reason recorded. Generic edits/deletes are disabled; rescanning
does not restore a voided record. Restoration is intentionally not implemented.
Voiding has no achievement side effects yet; later eligibility must require
PRESENT attendance and a completed event and support award reconciliation.

Ticket validity and attendance differ: a valid ticket grants access, but only a
successful authorized scan records attendance. Event cancellation prevents new
scans without deleting historical attendance.

QR encoding follows the [qrcode documentation](https://pypi.org/project/qrcode/).
No custom cryptography or QR encoder was introduced.

## Feedback (phase 6)

Feedback is submitted once and then locked for this MVP.

| Method | Path | Operation |
| --- | --- | --- |
| POST | /registrations/<id>/feedback/ | Submit feedback for own registration |
| GET | /registrations/<id>/feedback/ | Read own submitted feedback |
| GET | /registrations/events/<event_id>/feedback/ | Scoped results and rating summary |

Submission requires an active account, REGISTERED registration, PRESENT attendance
and COMPLETED event. Ratings are integers from 1 to 5; comment and suggestion are
optional and limited to 2000 characters. The registration ID is resolved from the
session user, so client input cannot assign another participant, event or timestamp.
Repeated submission returns 400 and cannot edit the original.

Organizer results require ownership and registrations.view_feedback; Platform Admin
has global scope. Results contain no participant identity or ticket token. The
summary uses the whole eligible dataset, not only the current page. If attendance
is later voided, feedback remains historical and readable by its owner, but is
excluded from organizer results and averages. There is no public feedback endpoint.
Generic Admin add/edit/delete is disabled.

## Achievements (phase 7)

Achievement definitions are configured by Platform Admin in Django Admin. Each
definition has a unique code, name, description, required count, optional event
type scope and active flag. A missing event type means the threshold applies to
all event types. No Python branch is hard-coded for a particular badge.

Participant endpoint:

| Method | Path | Operation |
| --- | --- | --- |
| GET | `/achievements/` | List own awarded achievements that remain eligible |
| POST | `/achievements/reconcile/` | Reconcile own assignments with current attendance |

Evaluation counts only REGISTERED registrations with PRESENT attendance on
COMPLETED events. Registration alone, a ticket, feedback, or a merely published
event never qualifies. Assignments are unique per user/achievement and store the
qualifying count and award time. If attendance is later voided, the evaluator
marks the assignment inactive while retaining its history; restored valid data
can reactivate the same assignment.

GET performs no writes. POST reconciliation requires a session and CSRF and
evaluates only the signed-in user; a submitted user ID cannot select another account.
Lists and discount previews recheck current attendance and rule eligibility, so a
stale assignment cannot grant a benefit after attendance voiding or rule changes.
To award newly earned badges or reactivate assignments, call the POST endpoint or
run the trusted `reconcile_achievements` command (optionally `--user-id ID`).
There is no scheduler. Reconciliation locks accounts, participant event rows and
definitions in stable order; batch reconciliation commits per participant.
Achievement definitions and assignments are read-only to ordinary users; Admin
can create/deactivate definitions but cannot delete definitions or edit awards.

Achievement rules are deliberately limited to event type plus completed-count
threshold. Streaks, dates, points, levels, revocation reasons and notifications
remain future requirements.

## Reward and discount policy (phase 8)

Admin manages Reward in Django Admin: one reward per achievement, percentage
greater than 0 and no greater than 100, and an active flag. Deactivate a reward
to remove its benefit; generic deletion is disabled.

| Method | Path | Operation |
| --- | --- | --- |
| GET/POST | `/achievements/events/<event_id>/policy/` | Read/update owned event policy |
| GET | `/achievements/events/<event_id>/discount/` | Preview current user's discount |

Policy updates require organizer capability, event ownership and change-event
permission (Admin has global scope), form-encoded POST and CSRF. Fields are
`accept_achievement_discount` and `max_discount_percentage`. Missing policy means
no discount. Disabled policies require a zero cap; enabled policies require a cap
greater than 0 and no greater than 100. Disable a policy using false/unchecked
acceptance with cap 0.

Policy changes are allowed only in DRAFT/NEEDS_REVISION. Submission, review,
approval and publication freeze the policy with the event. Admin can inspect all
policies in the read-only native EventRewardPolicy Admin or through the endpoint
before approving. A revision is required to change an approved policy. Policy
updates and event transitions use the same row lock.

The quote uses the highest active reward attached to an awarded achievement that
still meets current attendance/type/count rules, limited by the event cap. Rewards
do not stack. No policy, disabled acceptance or no eligible reward yields zero.
Calculations use Decimal: discount amount rounds half-up to two decimal places,
and final price is original price minus discount amount. A free event remains free.

Responses contain `original_price`, `discount_percentage`, `discount_amount`,
`final_price`, `reward_id` and `preview_only: true`. The server ignores supplied
price, percentage and target user IDs. Quotes require an active session, are
uncached, and are visible for public events or events managed by the caller.
Terminal or already-started events cannot be quoted. Draft previews therefore
belong only to the owner/Admin and use that caller's own achievements.

Quotes are nonbinding snapshots; configuration or attendance may change afterward.
They do not reserve a price, charge money, create payments or modify registrations.
Paid events still cannot be submitted/published in this MVP. Future checkout must
revalidate eligibility and persist agreed pricing atomically; no payment integration
or additional currency support is introduced here.

## Verification

With environment variables loaded:

```bash
.venv/bin/python manage.py check
.venv/bin/python manage.py makemigrations --check --dry-run
.venv/bin/python manage.py migrate --plan
.venv/bin/python manage.py test --settings=config.test_settings
```

`test_settings` still uses PostgreSQL. Its fast password hasher and disabled HTTPS
redirect are only for tests; never use it to serve the application.

## Before deployment

This is a foundation, not a production-ready release. Add login/registration rate
limiting, email verification and recovery workflows when their delivery provider
is selected, and frontend integration. Public registration reports duplicate
emails, so it currently permits account enumeration; login failures are generic.

Set `DJANGO_DEBUG=false`, configure HTTPS, hosts and deployment-specific proxy
trust, and run `manage.py check --deploy`. Secure cookies and HTTPS redirection
are enabled by default. Do not disable CSRF to integrate the frontend.

See `ARCHITECTURE.md` for the approved scope and incremental roadmap, and
`VERIFICATION.md` for verification evidence.
