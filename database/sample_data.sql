USE hostel_management;
START TRANSACTION;

-- Explicit user IDs keep all user references deterministic on a fresh import.
INSERT INTO users (user_id,username,password_hash,full_name,email,role) VALUES
(1,'admin','$2b$12$replace.this.with.a.real.bcrypt.hash.before.use','System Administrator','admin@example.edu','ADMIN'),
(2,'warden_north','$2b$12$replace.this.with.a.real.bcrypt.hash.before.use','Asha Menon','asha.menon@example.edu','WARDEN'),
(3,'warden_south','$2b$12$replace.this.with.a.real.bcrypt.hash.before.use','Rahul Das','rahul.das@example.edu','WARDEN'),
(4,'staff_facilities','$2b$12$replace.this.with.a.real.bcrypt.hash.before.use','Kiran Rao','kiran.rao@example.edu','STAFF'),
(5,'student01','$2b$12$replace.this.with.a.real.bcrypt.hash.before.use','Aarav Sharma','aarav.sharma@student.example.edu','STUDENT'),
(6,'student02','$2b$12$replace.this.with.a.real.bcrypt.hash.before.use','Ishita Verma','ishita.verma@student.example.edu','STUDENT'),
(7,'student03','$2b$12$replace.this.with.a.real.bcrypt.hash.before.use','Rohan Patel','rohan.patel@student.example.edu','STUDENT'),
(8,'student04','$2b$12$replace.this.with.a.real.bcrypt.hash.before.use','Meera Nair','meera.nair@student.example.edu','STUDENT'),
(9,'student05','$2b$12$replace.this.with.a.real.bcrypt.hash.before.use','Kabir Singh','kabir.singh@student.example.edu','STUDENT'),
(10,'student06','$2b$12$replace.this.with.a.real.bcrypt.hash.before.use','Ananya Iyer','ananya.iyer@student.example.edu','STUDENT'),
(11,'student07','$2b$12$replace.this.with.a.real.bcrypt.hash.before.use','Dev Kumar','dev.kumar@student.example.edu','STUDENT'),
(12,'student08','$2b$12$replace.this.with.a.real.bcrypt.hash.before.use','Sara Khan','sara.khan@student.example.edu','STUDENT'),
(13,'student09','$2b$12$replace.this.with.a.real.bcrypt.hash.before.use','Arjun Reddy','arjun.reddy@student.example.edu','STUDENT'),
(14,'student10','$2b$12$replace.this.with.a.real.bcrypt.hash.before.use','Diya Bose','diya.bose@student.example.edu','STUDENT');

INSERT INTO hostel_blocks (block_code,block_name,gender_policy,address,warden_user_id) VALUES
('NORTH','North Residence','MALE','North Campus',2),
('SOUTH','South Residence','FEMALE','South Campus',3),
('EAST','East Residence','MIXED','East Campus',2);

INSERT INTO rooms (block_id,room_number,floor_number,capacity,room_type) VALUES
(1,'N-101',1,3,'STANDARD'),(1,'N-102',1,3,'STANDARD'),(1,'N-201',2,3,'DELUXE'),(1,'N-202',2,3,'STANDARD'),
(2,'S-101',1,3,'STANDARD'),(2,'S-102',1,3,'ACCESSIBLE'),(2,'S-201',2,3,'STANDARD'),
(3,'E-101',1,3,'STANDARD'),(3,'E-102',1,3,'DELUXE'),(3,'E-201',2,3,'STANDARD');

INSERT INTO beds (room_id,bed_label) VALUES
(1,'A'),(1,'B'),(1,'C'),(2,'A'),(2,'B'),(2,'C'),(3,'A'),(3,'B'),(3,'C'),(4,'A'),(4,'B'),(4,'C'),
(5,'A'),(5,'B'),(5,'C'),(6,'A'),(6,'B'),(6,'C'),(7,'A'),(7,'B'),(7,'C'),
(8,'A'),(8,'B'),(8,'C'),(9,'A'),(9,'B'),(9,'C'),(10,'A'),(10,'B'),(10,'C');

INSERT INTO students (user_id,registration_no,first_name,last_name,email,phone,gender,date_of_birth,department,course,year_of_study,emergency_contact_name,emergency_contact_phone) VALUES
(5,'STU2026001','Aarav','Sharma','aarav.sharma@student.example.edu','9000000001','MALE','2005-02-14','Computer Science','BSc Computer Science',2,'Raj Sharma','9110000001'),
(6,'STU2026002','Ishita','Verma','ishita.verma@student.example.edu','9000000002','FEMALE','2004-07-08','Economics','BA Economics',3,'Neha Verma','9110000002'),
(7,'STU2026003','Rohan','Patel','rohan.patel@student.example.edu','9000000003','MALE','2005-01-21','Mechanical Engineering','BEng Mechanical',2,'Ketan Patel','9110000003'),
(8,'STU2026004','Meera','Nair','meera.nair@student.example.edu','9000000004','FEMALE','2004-11-30','Biology','BSc Biology',3,'Anil Nair','9110000004'),
(9,'STU2026005','Kabir','Singh','kabir.singh@student.example.edu','9000000005','MALE','2006-03-12','Physics','BSc Physics',1,'Aman Singh','9110000005'),
(10,'STU2026006','Ananya','Iyer','ananya.iyer@student.example.edu','9000000006','FEMALE','2005-05-18','Computer Science','BSc Computer Science',2,'Kavya Iyer','9110000006'),
(11,'STU2026007','Dev','Kumar','dev.kumar@student.example.edu','9000000007','MALE','2004-09-05','Commerce','BCom',3,'Sanjay Kumar','9110000007'),
(12,'STU2026008','Sara','Khan','sara.khan@student.example.edu','9000000008','FEMALE','2006-01-17','Chemistry','BSc Chemistry',1,'Farah Khan','9110000008'),
(13,'STU2026009','Arjun','Reddy','arjun.reddy@student.example.edu','9000000009','MALE','2005-08-23','Mathematics','BSc Mathematics',2,'Lakshmi Reddy','9110000009'),
(14,'STU2026010','Diya','Bose','diya.bose@student.example.edu','9000000010','FEMALE','2004-04-10','History','BA History',3,'Mita Bose','9110000010'),
(NULL,'STU2026011','Neil','Joseph','neil.joseph@student.example.edu','9000000011','MALE','2005-12-01','Physics','BSc Physics',2,'George Joseph','9110000011'),
(NULL,'STU2026012','Priya','Shah','priya.shah@student.example.edu','9000000012','FEMALE','2005-06-22','Commerce','BCom',2,'Nisha Shah','9110000012'),
(NULL,'STU2026013','Ibrahim','Ali','ibrahim.ali@student.example.edu','9000000013','MALE','2006-02-09','Computer Science','BSc Computer Science',1,'Sameer Ali','9110000013'),
(NULL,'STU2026014','Kavya','Rao','kavya.rao@student.example.edu','9000000014','FEMALE','2005-10-16','Mathematics','BSc Mathematics',2,'Suma Rao','9110000014'),
(NULL,'STU2026015','Vikram','Jain','vikram.jain@student.example.edu','9000000015','MALE','2004-12-28','Economics','BA Economics',3,'Ritu Jain','9110000015'),
(NULL,'STU2026016','Nisha','Thomas','nisha.thomas@student.example.edu','9000000016','FEMALE','2006-07-03','Biology','BSc Biology',1,'Mary Thomas','9110000016'),
(NULL,'STU2026017','Aditya','Gupta','aditya.gupta@student.example.edu','9000000017','MALE','2005-03-26','Electrical Engineering','BEng Electrical',2,'Pooja Gupta','9110000017'),
(NULL,'STU2026018','Tara','Sen','tara.sen@student.example.edu','9000000018','FEMALE','2004-08-19','English','BA English',3,'Anup Sen','9110000018'),
(NULL,'STU2026019','Manav','Desai','manav.desai@student.example.edu','9000000019','MALE','2006-05-11','Chemistry','BSc Chemistry',1,'Rina Desai','9110000019'),
(NULL,'STU2026020','Leela','Pillai','leela.pillai@student.example.edu','9000000020','FEMALE','2005-09-14','History','BA History',2,'Sunil Pillai','9110000020');

-- Insert the old side of the transfer as historical before the student's new active allocation.
INSERT INTO allocations (student_id,bed_id,allocation_date,expected_vacate_date,actual_vacate_date,status,created_by) VALUES
(1,1,'2026-07-01','2027-05-31','2026-09-01','TRANSFERRED',2);

INSERT INTO allocations (student_id,bed_id,allocation_date,expected_vacate_date,status,created_by) VALUES
(3,2,'2026-07-01','2027-05-31','ACTIVE',2),
(5,3,'2026-07-02','2027-05-31','ACTIVE',2),(7,4,'2026-07-02','2027-05-31','ACTIVE',2),
(9,5,'2026-07-03','2027-05-31','ACTIVE',2),(11,6,'2026-07-03','2027-05-31','ACTIVE',2),
(15,7,'2026-07-04','2027-05-31','ACTIVE',2),(17,8,'2026-07-04','2027-05-31','ACTIVE',2),
(19,9,'2026-07-05','2027-05-31','ACTIVE',2),(2,13,'2026-07-01','2027-05-31','ACTIVE',3),
(4,14,'2026-07-01','2027-05-31','ACTIVE',3),(6,15,'2026-07-02','2027-05-31','ACTIVE',3),
(8,16,'2026-07-02','2027-05-31','ACTIVE',3),(10,17,'2026-07-03','2027-05-31','ACTIVE',3),
(12,19,'2026-07-03','2027-05-31','ACTIVE',3),(14,22,'2026-07-04','2027-05-31','ACTIVE',2),
(16,23,'2026-07-04','2027-05-31','ACTIVE',2),(18,25,'2026-07-05','2027-05-31','ACTIVE',2),
(20,28,'2026-07-05','2027-05-31','ACTIVE',2);
-- Transfer: student 1 leaves bed 1 and receives bed 10, preserving allocation history.
INSERT INTO allocations (student_id,bed_id,allocation_date,expected_vacate_date,status,created_by) VALUES
(1,10,'2026-09-01','2027-05-31','ACTIVE',2);
INSERT INTO transfers (from_allocation_id,to_allocation_id,transfer_date,reason,approved_by)
VALUES (1,20,'2026-09-01','Room change due to accessibility needs',2);
-- A completed prior stay and its vacating record.
INSERT INTO allocations (student_id,bed_id,allocation_date,expected_vacate_date,actual_vacate_date,status,created_by)
VALUES (13,26,'2025-07-01','2026-05-31','2026-05-28','VACATED',2);
INSERT INTO vacating_records (allocation_id,vacating_date,reason,inspection_notes,deposit_refund,processed_by)
VALUES (21,'2026-05-28','Completed academic year','Room inspected; minor wear noted',500.00,2);

INSERT INTO fee_schedules (academic_year,term,fee_type,amount,due_date) VALUES
('2026-2027','Annual','HOSTEL',60000.00,'2026-08-01'),
('2026-2027','Annual','MESS',30000.00,'2026-08-01'),
('2026-2027','Annual','SECURITY_DEPOSIT',10000.00,'2026-07-15');
INSERT INTO payments (student_id,fee_schedule_id,amount,payment_date,payment_method,transaction_reference,received_by) VALUES
(1,1,30000,'2026-07-10 10:30:00','UPI','TXN-HOSTEL-001',2),
(1,2,30000,'2026-07-10 10:35:00','UPI','TXN-MESS-001',2),
(2,1,60000,'2026-07-11 11:00:00','BANK_TRANSFER','TXN-HOSTEL-002',3),
(2,2,15000,'2026-07-11 11:05:00','BANK_TRANSFER','TXN-MESS-002',3),
(3,1,25000,'2026-07-12 09:00:00','CARD','TXN-HOSTEL-003',2),
(4,3,10000,'2026-07-13 14:15:00','CASH','TXN-DEP-004',3),
(5,1,60000,'2026-07-14 10:00:00','UPI','TXN-HOSTEL-005',2),
(6,2,12000,'2026-07-15 16:20:00','CARD','TXN-MESS-006',3);

INSERT INTO visitors (student_id,visitor_name,relationship_to_student,phone,purpose,check_in,check_out,approved_by) VALUES
(1,'Raj Sharma','Parent','9110000001','Family visit','2026-09-20 10:00:00','2026-09-20 12:15:00',2),
(2,'Neha Verma','Parent','9110000002','Deliver books','2026-09-21 11:30:00','2026-09-21 12:00:00',3),
(3,'Ketan Patel','Parent','9110000003','Weekend visit','2026-09-22 09:10:00','2026-09-22 13:00:00',2),
(4,'Anil Nair','Parent','9110000004','Student meeting','2026-09-23 15:00:00',NULL,3),
(5,'Aman Singh','Sibling','9110000005','Drop off supplies','2026-09-24 08:40:00','2026-09-24 09:20:00',2);

INSERT INTO complaints (student_id,category,subject,description,status,priority,submitted_at,assigned_to) VALUES
(1,'WATER','Low water pressure','Water pressure is low on the second floor.','OPEN','HIGH','2026-09-20 09:00:00',4),
(2,'FOOD','Dining menu variety','Please add more vegetarian options.','IN_PROGRESS','MEDIUM','2026-09-21 10:00:00',3),
(3,'NOISE','Late night noise','Repeated noise after quiet hours.','OPEN','LOW','2026-09-22 11:00:00',2),
(4,'CLEANLINESS','Common area cleaning','The common lounge needs cleaning.','RESOLVED','MEDIUM','2026-09-23 12:00:00',4);
UPDATE complaints SET resolved_at='2026-09-25 16:00:00' WHERE complaint_id=4;

INSERT INTO maintenance_requests (room_id,requested_by_student_id,category,description,status,priority,requested_at,assigned_to) VALUES
(1,1,'ELECTRICAL','Desk lamp outlet is not working.','ASSIGNED','HIGH','2026-09-23 08:00:00',4),
(5,2,'PLUMBING','Wash basin tap is leaking.','IN_PROGRESS','MEDIUM','2026-09-24 09:00:00',4),
(8,14,'FURNITURE','Study chair requires repair.','OPEN','LOW','2026-09-25 10:00:00',NULL),
(3,5,'CLEANING','Window ledge needs deep cleaning.','COMPLETED','LOW','2026-09-24 11:00:00',4);
UPDATE maintenance_requests SET completed_at='2026-09-26 12:00:00' WHERE maintenance_id=4;

COMMIT;
