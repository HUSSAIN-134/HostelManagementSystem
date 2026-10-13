# Final Project Audit

Audit date: 2026-10-13

## Requirements checked

- MySQL keys, constraints, defaults, indexes, relationships, referential integrity, and normalization
- Allocation, room capacity, payment, transfer, and vacating rules
- SQL query catalog syntax and coverage
- Flask route behavior against the configured `hostel_management` database
- Transaction rollback paths, invalid input, and uniqueness/FK handling
- Frontend modules, API usage, and presence of hardcoded database records
- Environment-secret handling, parameterized queries, project structure, and documentation

## Findings and fixes

1. Allocation creation read its optional creator ID from an undefined variable after replacing the request data. The allocation endpoint now validates and retains that ID. A real allocation test confirms it persists correctly.
2. Transfer and vacating date comparisons compared Python dates with ISO strings returned by the shared JSON conversion helper. Both paths now parse the database date before comparing it.
3. Transfer reasons longer than the schema's 500-character limit previously reached MySQL and returned a generic server error. The API now rejects them with HTTP 400.
4. Student creation/update passed `year_of_study` through text-only validation. The API now accepts either a JSON integer or a form string and applies the existing 1–8 integer rule.
5. `transfers.student_id` duplicated the student already determined by its unique source allocation, creating a 3NF violation and allowing inconsistent transfer identity. The schema now derives student identity through the source allocation. The sample insert and API query were updated, and a one-time migration was added and applied to the existing database after verifying the source and destination allocation student IDs matched.
6. The request wrapper now explicitly rolls back active transactions for unexpected exceptions as well as handled API and MySQL exceptions.

`database/schema.sql` and `database/sample_data.sql` were changed only for the transfer normalization issue. The other fixes were limited to backend handling and documentation/tests.

## Database tables

`users`, `hostel_blocks`, `rooms`, `beds`, `students`, `allocations`, `transfers`, `fee_schedules`, `payments`, `visitors`, `complaints`, `maintenance_requests`, and `vacating_records`.

## Main relationships

- A hostel block has rooms; a room contains beds.
- A student can have multiple historical allocations, but unique active-only generated keys allow at most one active allocation per student and per bed.
- A transfer references its source and destination allocations; its student is determined through the source allocation.
- Fee schedules have payment rows by student; payment totals are checked against the applicable schedule amount.
- Students have visitor and complaint records; maintenance belongs to a room and may optionally record a requesting student.
- A vacating record references one allocation and is unique per allocation.
- Users are referenced by optional warden, creator, approver, assignee, receiver, and processor relationships.

## SQL catalog

`database/queries.sql` includes SELECT/WHERE/ORDER BY, INSERT/UPDATE/DELETE, inner and left joins, multiple-table joins, grouping/HAVING, COUNT/SUM/AVG, a subquery, views, and all requested occupancy, vacancy, fee dues, allocation history, visitor, unresolved complaint, and maintenance reports. All 19 statements executed successfully against MySQL 8.0.46. The three DML examples were enclosed in a transaction and rolled back after verification.

## API modules

Health and stats; students; blocks; rooms; beds; allocations; transfers; fees and payments; visitors; complaints; maintenance; vacating; occupancy, vacancy, fee dues, allocation history, visitor, complaint, and maintenance reports.

## Testing results

Against the configured real MySQL database:

- `GET /api/health`: HTTP 200, `{"database":"connected","status":"ok"}`.
- `GET /api/stats`: HTTP 200; students 20, users 14, blocks 3, rooms 10, beds 30, allocations 21, active allocations 19, transfers 1, payments 8, visitors 5, complaints 4, maintenance requests 4, vacating records 1.
- All module and report GET endpoints returned HTTP 200.
- Five integration tests passed. They cover API reads, student/block/room/bed CRUD, fee/payment/visitor/complaint/maintenance writes, allocation/transfer/vacating, duplicate registration/email, invalid student/room/bed, occupied bed, existing active allocation, invalid dates, and invalid/over-balance payments.
- Failed transfer and vacating attempts were checked against the database afterward; original allocation state remained intact. Temporary test records were removed.
- The project Python files and tests passed `compileall`.
- Frontend code review confirmed the Dashboard and all listed modules call Flask endpoints through `fetch()` and no static sample database arrays were found. The root route renders `templates/index.html`.
- `.env` is ignored by `.gitignore`; Python reads the password from environment/local `.env`, not a source-code literal.

## Remaining limitations

- The `users` table is not accompanied by an authentication/authorization workflow. Sample password hashes are documented placeholders. This is suitable for a local academic demo, not a public deployment with real student information.
- No cross-browser visual automation was available for this audit. Frontend/API wiring was reviewed in source, and the rendered root route plus all called API endpoints were exercised through Flask's test client.
- Concurrency stress testing was not performed. API allocation paths lock the relevant student/room/bed records; the database's payment-cap trigger was verified sequentially, not under simultaneous payment submissions.
- The migration is one-time. On a fresh installation, run the current `schema.sql` and `sample_data.sql`; on an existing earlier installation, run `database/migrations/001_normalize_transfers.sql` once instead of rebuilding the database.

## Submission/demo readiness

Ready for a local DBMS submission/demo after setting the local `.env`. The project demonstrates relational schema design, constraints/triggers, transaction handling, SQL reporting, and a live API-backed frontend. Present the authentication and concurrency-testing limitations accurately if asked.
