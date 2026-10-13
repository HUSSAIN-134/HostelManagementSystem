USE hostel_management;

-- SELECT: inspect a student
SELECT registration_no, first_name, last_name, department FROM students WHERE registration_no='STU2026001';

-- INSERT: add a sample visitor (use valid existing student/user IDs)
INSERT INTO visitors (student_id,visitor_name,relationship_to_student,phone,purpose,approved_by)
VALUES (1,'Sample Guest','Friend','9001112222','Query demonstration',2);

-- UPDATE: close that demonstration visitor record
UPDATE visitors SET check_out=CURRENT_TIMESTAMP WHERE visitor_id=LAST_INSERT_ID();

-- DELETE: remove only the demonstration record (adjust the predicate before running)
DELETE FROM visitors WHERE visitor_name='Sample Guest' AND purpose='Query demonstration';

-- INNER JOIN: current student assignments
SELECT s.registration_no, CONCAT(s.first_name,' ',s.last_name) AS student,
       hb.block_name, r.room_number, be.bed_label, a.allocation_date
FROM allocations a JOIN students s ON s.student_id=a.student_id
JOIN beds be ON be.bed_id=a.bed_id JOIN rooms r ON r.room_id=be.room_id
JOIN hostel_blocks hb ON hb.block_id=r.block_id WHERE a.status='ACTIVE';

-- LEFT JOIN: all students, including those without an active allocation
SELECT s.registration_no, s.first_name, a.allocation_id
FROM students s LEFT JOIN allocations a ON a.student_id=s.student_id AND a.status='ACTIVE';

-- GROUP BY, COUNT, SUM: bed occupancy by block
SELECT hb.block_name, COUNT(DISTINCT be.bed_id) AS beds,
       COUNT(DISTINCT a.allocation_id) AS occupied,
       SUM(CASE WHEN a.allocation_id IS NULL THEN 1 ELSE 0 END) AS vacant
FROM hostel_blocks hb JOIN rooms r ON r.block_id=hb.block_id
JOIN beds be ON be.room_id=r.room_id
LEFT JOIN allocations a ON a.bed_id=be.bed_id AND a.status='ACTIVE'
GROUP BY hb.block_id,hb.block_name;

-- HAVING: blocks with at least one active resident
SELECT hb.block_code, COUNT(a.allocation_id) AS residents
FROM hostel_blocks hb JOIN rooms r ON r.block_id=hb.block_id
JOIN beds be ON be.room_id=r.room_id JOIN allocations a ON a.bed_id=be.bed_id AND a.status='ACTIVE'
GROUP BY hb.block_id,hb.block_code HAVING COUNT(a.allocation_id)>=1;

-- AVG: average payment by fee type
SELECT fs.fee_type, AVG(p.amount) AS average_payment
FROM fee_schedules fs LEFT JOIN payments p ON p.fee_schedule_id=fs.fee_schedule_id
GROUP BY fs.fee_schedule_id,fs.fee_type;

-- Subquery: students who have paid more than the average payment
SELECT s.registration_no,s.first_name,s.last_name
FROM students s WHERE (SELECT COALESCE(SUM(p.amount),0) FROM payments p WHERE p.student_id=s.student_id) >
  (SELECT AVG(student_total) FROM (SELECT SUM(amount) AS student_total FROM payments GROUP BY student_id) totals);

-- Views: occupancy and vacancy
SELECT * FROM v_occupancy ORDER BY block_code,room_number;
SELECT * FROM v_vacant_beds ORDER BY block_code,room_number,bed_label;

-- Occupancy report (block-level)
SELECT hb.block_code,hb.block_name,COUNT(DISTINCT be.bed_id) AS total_beds,
       COUNT(DISTINCT a.allocation_id) AS occupied_beds,
       ROUND(100*COUNT(DISTINCT a.allocation_id)/NULLIF(COUNT(DISTINCT be.bed_id),0),1) AS occupancy_percent
FROM hostel_blocks hb JOIN rooms r ON r.block_id=hb.block_id
LEFT JOIN beds be ON be.room_id=r.room_id AND be.is_active=TRUE
LEFT JOIN allocations a ON a.bed_id=be.bed_id AND a.status='ACTIVE'
GROUP BY hb.block_id,hb.block_code,hb.block_name;

-- Vacancy report
SELECT * FROM v_vacant_beds;

-- Fee dues
SELECT registration_no,first_name,last_name,academic_year,term,fee_type,fee_amount,paid_amount,balance
FROM v_fee_dues WHERE balance>0 ORDER BY due_date,registration_no;

-- Allocation history, including transfer history
SELECT s.registration_no,a.allocation_id,a.allocation_date,a.actual_vacate_date,a.status,
       hb.block_code,r.room_number,be.bed_label
FROM allocations a JOIN students s ON s.student_id=a.student_id
JOIN beds be ON be.bed_id=a.bed_id JOIN rooms r ON r.room_id=be.room_id
JOIN hostel_blocks hb ON hb.block_id=r.block_id ORDER BY s.registration_no,a.allocation_date;

-- Visitor report
SELECT s.registration_no,v.visitor_name,v.relationship_to_student,v.purpose,v.check_in,v.check_out
FROM visitors v JOIN students s ON s.student_id=v.student_id ORDER BY v.check_in DESC;

-- Unresolved complaints
SELECT c.complaint_id,s.registration_no,c.category,c.subject,c.priority,c.status,c.submitted_at
FROM complaints c JOIN students s ON s.student_id=c.student_id WHERE c.status IN ('OPEN','IN_PROGRESS')
ORDER BY FIELD(c.priority,'URGENT','HIGH','MEDIUM','LOW'),c.submitted_at;

-- Maintenance status
SELECT m.maintenance_id,hb.block_code,r.room_number,m.category,m.status,m.priority,m.requested_at,m.completed_at
FROM maintenance_requests m JOIN rooms r ON r.room_id=m.room_id
JOIN hostel_blocks hb ON hb.block_id=r.block_id ORDER BY m.requested_at DESC;
