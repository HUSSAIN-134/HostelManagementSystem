# DBMS Viva Preparation

### What is this project?

It is a hostel accommodation and student services management system. It stores student, room, bed, allocation, fee, visitor, complaint, maintenance, and vacating information in MySQL and provides a Flask API and web dashboard to manage it.

### Why use a DBMS?

A DBMS stores related information consistently, checks rules, prevents invalid references, supports concurrent users, and lets the system retrieve useful reports with SQL.

### What are the entities?

The main entities are users, students, hostel blocks, rooms, beds, allocations, transfers, fee schedules, payments, visitors, complaints, maintenance requests, and vacating records.

### What is a primary key?

A primary key uniquely identifies each row in a table. For example, `student_id` identifies one student and `room_id` identifies one room.

### What is a foreign key?

A foreign key references a key in another table. For example, `rooms.block_id` references `hostel_blocks.block_id`, so a room cannot refer to a missing block.

### What is normalization?

Normalization organizes data into related tables to reduce duplicate facts and prevent insert, update, and delete anomalies.

### Why use 3NF?

Third Normal Form requires a table to be in 2NF and for non-key columns to depend on the key, the whole key, and nothing but the key. This avoids storing facts that can be derived from other non-key attributes.

### What are functional dependencies?

A functional dependency means one attribute or attribute set determines another. For example, `student_id` determines that student's registration number and contact fields.

### What constraints are used?

The schema uses primary keys, foreign keys, unique constraints, `NOT NULL`, `CHECK`, `DEFAULT`, `ENUM`, generated columns with unique indexes, and triggers for rules such as room capacity and payment limits.

### What is a transaction?

A transaction groups database changes into one unit. It either commits all intended changes or rolls them back after a failure.

### Why are transactions used for transfer and vacating?

A transfer changes the old allocation, creates a new allocation, and records the transfer. Vacating changes allocation status and inserts a vacating record. Transactions prevent a partial operation from leaving inconsistent history or bed availability.

### What are JOINs?

JOINs combine related rows from different tables. The allocation report joins allocations, students, beds, rooms, and blocks to show where each resident lives.

### What are aggregate functions?

Aggregate functions summarize multiple rows. The project uses `COUNT`, `SUM`, and `AVG` for occupancy, payments, and fee reports.

### What are subqueries?

A subquery is a query nested inside another query. It can calculate a value or select rows used by the outer query, such as comparing a student's payment total with an average.

### What are views?

A view is a saved query presented like a table. `v_occupancy`, `v_vacant_beds`, and `v_fee_dues` centralize reusable reporting logic.

### What indexes are used?

Indexes support primary and unique keys, foreign-key relationships, searches by student name or department, allocation status/history, bed and room lookup, fee due dates, and service-request status/date filters. Generated unique indexes enforce one active allocation per student and bed.

### How is room capacity controlled?

Room capacity is checked by a `CHECK` constraint and triggers that prevent creating more physical beds than capacity or reducing capacity below the existing bed count. Allocation logic checks active occupancy before admitting another resident.

### How is duplicate bed allocation prevented?

An active-only generated column is `bed_id` for active allocations and `NULL` for historical allocations. A unique index on it permits only one active row for a bed. The API also checks availability inside a transaction before inserting.

### Why does a transfer reference allocations?

The transfer points to the old and new allocation rows. The student's identity is derived through those allocations, avoiding a duplicate student fact in the transfer row while preserving full allocation history.
