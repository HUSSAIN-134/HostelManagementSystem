-- Hostel Accommodation and Student Services Management System
-- Target: MySQL 8.0.16+ (enforced CHECK constraints and generated columns)
CREATE DATABASE IF NOT EXISTS hostel_management
  CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
USE hostel_management;

SET FOREIGN_KEY_CHECKS = 0;
DROP VIEW IF EXISTS v_occupancy;
DROP VIEW IF EXISTS v_vacant_beds;
DROP VIEW IF EXISTS v_fee_dues;
DROP TABLE IF EXISTS vacating_records, maintenance_requests, complaints, visitors,
  payments, fee_schedules, transfers, allocations, students, beds, rooms,
  hostel_blocks, users;
SET FOREIGN_KEY_CHECKS = 1;

CREATE TABLE users (
  user_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  username VARCHAR(50) NOT NULL UNIQUE,
  password_hash VARCHAR(255) NOT NULL,
  full_name VARCHAR(120) NOT NULL,
  email VARCHAR(254) NOT NULL UNIQUE,
  role ENUM('ADMIN','WARDEN','STAFF','STUDENT') NOT NULL DEFAULT 'STUDENT',
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX ix_users_role_active (role, is_active)
) ENGINE=InnoDB;

CREATE TABLE hostel_blocks (
  block_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  block_code VARCHAR(20) NOT NULL UNIQUE,
  block_name VARCHAR(100) NOT NULL,
  gender_policy ENUM('MALE','FEMALE','MIXED') NOT NULL,
  address VARCHAR(255),
  warden_user_id BIGINT UNSIGNED,
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_blocks_warden FOREIGN KEY (warden_user_id) REFERENCES users(user_id) ON DELETE SET NULL,
  INDEX ix_blocks_active_policy (is_active, gender_policy)
) ENGINE=InnoDB;

CREATE TABLE rooms (
  room_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  block_id BIGINT UNSIGNED NOT NULL,
  room_number VARCHAR(20) NOT NULL,
  floor_number SMALLINT NOT NULL DEFAULT 0,
  capacity TINYINT UNSIGNED NOT NULL,
  room_type ENUM('STANDARD','DELUXE','ACCESSIBLE') NOT NULL DEFAULT 'STANDARD',
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  UNIQUE KEY uq_room_block_number (block_id, room_number),
  CONSTRAINT fk_rooms_block FOREIGN KEY (block_id) REFERENCES hostel_blocks(block_id) ON DELETE RESTRICT,
  CONSTRAINT ck_rooms_capacity CHECK (capacity BETWEEN 1 AND 12),
  INDEX ix_rooms_block_active (block_id, is_active)
) ENGINE=InnoDB;

CREATE TABLE beds (
  bed_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  room_id BIGINT UNSIGNED NOT NULL,
  bed_label VARCHAR(10) NOT NULL,
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  UNIQUE KEY uq_bed_room_label (room_id, bed_label),
  CONSTRAINT fk_beds_room FOREIGN KEY (room_id) REFERENCES rooms(room_id) ON DELETE RESTRICT,
  INDEX ix_beds_room_active (room_id, is_active)
) ENGINE=InnoDB;

CREATE TABLE students (
  student_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  user_id BIGINT UNSIGNED UNIQUE,
  registration_no VARCHAR(30) NOT NULL UNIQUE,
  first_name VARCHAR(70) NOT NULL,
  last_name VARCHAR(70) NOT NULL,
  email VARCHAR(254) NOT NULL UNIQUE,
  phone VARCHAR(25) NOT NULL,
  gender ENUM('MALE','FEMALE','OTHER') NOT NULL,
  date_of_birth DATE,
  department VARCHAR(100) NOT NULL,
  course VARCHAR(100) NOT NULL,
  year_of_study TINYINT UNSIGNED NOT NULL,
  emergency_contact_name VARCHAR(120) NOT NULL,
  emergency_contact_phone VARCHAR(25) NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_students_user FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE SET NULL,
  CONSTRAINT ck_students_year CHECK (year_of_study BETWEEN 1 AND 8),
  INDEX ix_students_name (last_name, first_name),
  INDEX ix_students_department_year (department, year_of_study)
) ENGINE=InnoDB;

CREATE TABLE allocations (
  allocation_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  student_id BIGINT UNSIGNED NOT NULL,
  bed_id BIGINT UNSIGNED NOT NULL,
  allocation_date DATE NOT NULL,
  expected_vacate_date DATE NOT NULL,
  actual_vacate_date DATE,
  status ENUM('ACTIVE','TRANSFERRED','VACATED','CANCELLED') NOT NULL DEFAULT 'ACTIVE',
  created_by BIGINT UNSIGNED,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  active_student_id BIGINT UNSIGNED GENERATED ALWAYS AS
    (CASE WHEN status='ACTIVE' THEN student_id ELSE NULL END) STORED,
  active_bed_id BIGINT UNSIGNED GENERATED ALWAYS AS
    (CASE WHEN status='ACTIVE' THEN bed_id ELSE NULL END) STORED,
  UNIQUE KEY uq_one_active_allocation_student (active_student_id),
  UNIQUE KEY uq_one_active_allocation_bed (active_bed_id),
  CONSTRAINT fk_alloc_student FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE RESTRICT,
  CONSTRAINT fk_alloc_bed FOREIGN KEY (bed_id) REFERENCES beds(bed_id) ON DELETE RESTRICT,
  CONSTRAINT fk_alloc_creator FOREIGN KEY (created_by) REFERENCES users(user_id) ON DELETE SET NULL,
  CONSTRAINT ck_alloc_dates CHECK (expected_vacate_date >= allocation_date AND (actual_vacate_date IS NULL OR actual_vacate_date >= allocation_date)),
  INDEX ix_alloc_student_history (student_id, allocation_date),
  INDEX ix_alloc_status_dates (status, allocation_date),
  INDEX ix_alloc_bed_status (bed_id, status)
) ENGINE=InnoDB;

CREATE TABLE transfers (
  transfer_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  from_allocation_id BIGINT UNSIGNED NOT NULL UNIQUE,
  to_allocation_id BIGINT UNSIGNED NOT NULL UNIQUE,
  transfer_date DATE NOT NULL,
  reason VARCHAR(500) NOT NULL,
  approved_by BIGINT UNSIGNED,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_transfer_from FOREIGN KEY (from_allocation_id) REFERENCES allocations(allocation_id) ON DELETE RESTRICT,
  CONSTRAINT fk_transfer_to FOREIGN KEY (to_allocation_id) REFERENCES allocations(allocation_id) ON DELETE RESTRICT,
  CONSTRAINT fk_transfer_approver FOREIGN KEY (approved_by) REFERENCES users(user_id) ON DELETE SET NULL,
  CONSTRAINT ck_transfer_different_alloc CHECK (from_allocation_id <> to_allocation_id),
  INDEX ix_transfers_date (transfer_date)
) ENGINE=InnoDB;

CREATE TABLE fee_schedules (
  fee_schedule_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  academic_year VARCHAR(9) NOT NULL,
  term VARCHAR(30) NOT NULL,
  fee_type ENUM('HOSTEL','MESS','SECURITY_DEPOSIT','OTHER') NOT NULL,
  amount DECIMAL(10,2) NOT NULL,
  due_date DATE NOT NULL,
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uq_fee_year_term_type (academic_year, term, fee_type),
  CONSTRAINT ck_fee_amount CHECK (amount > 0),
  INDEX ix_fees_due (due_date, is_active)
) ENGINE=InnoDB;

CREATE TABLE payments (
  payment_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  student_id BIGINT UNSIGNED NOT NULL,
  fee_schedule_id BIGINT UNSIGNED NOT NULL,
  amount DECIMAL(10,2) NOT NULL,
  payment_date DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  payment_method ENUM('CASH','CARD','BANK_TRANSFER','UPI','OTHER') NOT NULL,
  transaction_reference VARCHAR(100) UNIQUE,
  received_by BIGINT UNSIGNED,
  notes VARCHAR(500),
  CONSTRAINT fk_pay_student FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE RESTRICT,
  CONSTRAINT fk_pay_fee FOREIGN KEY (fee_schedule_id) REFERENCES fee_schedules(fee_schedule_id) ON DELETE RESTRICT,
  CONSTRAINT fk_pay_receiver FOREIGN KEY (received_by) REFERENCES users(user_id) ON DELETE SET NULL,
  CONSTRAINT ck_payment_positive CHECK (amount > 0),
  INDEX ix_pay_student_fee (student_id, fee_schedule_id),
  INDEX ix_pay_date (payment_date)
) ENGINE=InnoDB;

CREATE TABLE visitors (
  visitor_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  student_id BIGINT UNSIGNED NOT NULL,
  visitor_name VARCHAR(120) NOT NULL,
  relationship_to_student VARCHAR(60) NOT NULL,
  phone VARCHAR(25) NOT NULL,
  purpose VARCHAR(255) NOT NULL,
  check_in DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  check_out DATETIME,
  approved_by BIGINT UNSIGNED,
  CONSTRAINT fk_vis_student FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE RESTRICT,
  CONSTRAINT fk_vis_approver FOREIGN KEY (approved_by) REFERENCES users(user_id) ON DELETE SET NULL,
  CONSTRAINT ck_visitor_times CHECK (check_out IS NULL OR check_out >= check_in),
  INDEX ix_vis_student_checkin (student_id, check_in),
  INDEX ix_vis_open (check_out, check_in)
) ENGINE=InnoDB;

CREATE TABLE complaints (
  complaint_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  student_id BIGINT UNSIGNED NOT NULL,
  category ENUM('CLEANLINESS','FOOD','NOISE','SECURITY','WATER','ELECTRICAL','OTHER') NOT NULL,
  subject VARCHAR(150) NOT NULL,
  description TEXT NOT NULL,
  status ENUM('OPEN','IN_PROGRESS','RESOLVED','CLOSED') NOT NULL DEFAULT 'OPEN',
  priority ENUM('LOW','MEDIUM','HIGH','URGENT') NOT NULL DEFAULT 'MEDIUM',
  submitted_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  resolved_at DATETIME,
  assigned_to BIGINT UNSIGNED,
  CONSTRAINT fk_comp_student FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE RESTRICT,
  CONSTRAINT fk_comp_assignee FOREIGN KEY (assigned_to) REFERENCES users(user_id) ON DELETE SET NULL,
  CONSTRAINT ck_complaint_resolution CHECK (resolved_at IS NULL OR resolved_at >= submitted_at),
  INDEX ix_comp_status_priority (status, priority),
  INDEX ix_comp_student_date (student_id, submitted_at)
) ENGINE=InnoDB;

CREATE TABLE maintenance_requests (
  maintenance_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  room_id BIGINT UNSIGNED NOT NULL,
  requested_by_student_id BIGINT UNSIGNED,
  category ENUM('PLUMBING','ELECTRICAL','FURNITURE','CLEANING','STRUCTURAL','OTHER') NOT NULL,
  description TEXT NOT NULL,
  status ENUM('OPEN','ASSIGNED','IN_PROGRESS','COMPLETED','CANCELLED') NOT NULL DEFAULT 'OPEN',
  priority ENUM('LOW','MEDIUM','HIGH','URGENT') NOT NULL DEFAULT 'MEDIUM',
  requested_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  completed_at DATETIME,
  assigned_to BIGINT UNSIGNED,
  CONSTRAINT fk_maint_room FOREIGN KEY (room_id) REFERENCES rooms(room_id) ON DELETE RESTRICT,
  CONSTRAINT fk_maint_student FOREIGN KEY (requested_by_student_id) REFERENCES students(student_id) ON DELETE SET NULL,
  CONSTRAINT fk_maint_assignee FOREIGN KEY (assigned_to) REFERENCES users(user_id) ON DELETE SET NULL,
  CONSTRAINT ck_maintenance_completion CHECK (completed_at IS NULL OR completed_at >= requested_at),
  INDEX ix_maint_status_priority (status, priority),
  INDEX ix_maint_room_date (room_id, requested_at)
) ENGINE=InnoDB;

CREATE TABLE vacating_records (
  vacating_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  allocation_id BIGINT UNSIGNED NOT NULL UNIQUE,
  vacating_date DATE NOT NULL,
  reason VARCHAR(300) NOT NULL,
  inspection_notes TEXT,
  deposit_refund DECIMAL(10,2) NOT NULL DEFAULT 0,
  processed_by BIGINT UNSIGNED,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_vac_alloc FOREIGN KEY (allocation_id) REFERENCES allocations(allocation_id) ON DELETE RESTRICT,
  CONSTRAINT fk_vac_processor FOREIGN KEY (processed_by) REFERENCES users(user_id) ON DELETE SET NULL,
  CONSTRAINT ck_vac_refund CHECK (deposit_refund >= 0),
  INDEX ix_vac_date (vacating_date)
) ENGINE=InnoDB;

-- Keep physical bed count within capacity, even when beds are inactive.
DELIMITER $$
CREATE TRIGGER trg_beds_capacity_insert BEFORE INSERT ON beds FOR EACH ROW
BEGIN
  IF (SELECT COUNT(*) FROM beds WHERE room_id=NEW.room_id) >=
     (SELECT capacity FROM rooms WHERE room_id=NEW.room_id) THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Room capacity exceeded by bed count';
  END IF;
END$$
CREATE TRIGGER trg_beds_capacity_update BEFORE UPDATE ON beds FOR EACH ROW
BEGIN
  IF NEW.room_id <> OLD.room_id AND (SELECT COUNT(*) FROM beds WHERE room_id=NEW.room_id) >=
     (SELECT capacity FROM rooms WHERE room_id=NEW.room_id) THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Room capacity exceeded by bed count';
  END IF;
END$$
CREATE TRIGGER trg_room_capacity_update BEFORE UPDATE ON rooms FOR EACH ROW
BEGIN
  IF NEW.capacity < (SELECT COUNT(*) FROM beds WHERE room_id=OLD.room_id) THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Capacity cannot be below existing bed count';
  END IF;
END$$
CREATE TRIGGER trg_payments_balance_insert BEFORE INSERT ON payments FOR EACH ROW
BEGIN
  DECLARE fee_amount DECIMAL(10,2);
  DECLARE paid_amount DECIMAL(12,2);
  SELECT amount INTO fee_amount FROM fee_schedules WHERE fee_schedule_id=NEW.fee_schedule_id;
  SELECT COALESCE(SUM(amount),0) INTO paid_amount FROM payments
    WHERE student_id=NEW.student_id AND fee_schedule_id=NEW.fee_schedule_id;
  IF NEW.amount + paid_amount > fee_amount THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Payment exceeds applicable fee balance';
  END IF;
END$$
CREATE TRIGGER trg_payments_balance_update BEFORE UPDATE ON payments FOR EACH ROW
BEGIN
  DECLARE fee_amount DECIMAL(10,2);
  DECLARE paid_amount DECIMAL(12,2);
  SELECT amount INTO fee_amount FROM fee_schedules WHERE fee_schedule_id=NEW.fee_schedule_id;
  SELECT COALESCE(SUM(amount),0) INTO paid_amount FROM payments
    WHERE student_id=NEW.student_id AND fee_schedule_id=NEW.fee_schedule_id AND payment_id<>OLD.payment_id;
  IF NEW.amount + paid_amount > fee_amount THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Payment exceeds applicable fee balance';
  END IF;
END$$
CREATE TRIGGER trg_allocation_validate_insert BEFORE INSERT ON allocations FOR EACH ROW
BEGIN
  DECLARE room_cap INT;
  DECLARE room_bed_count INT;
  DECLARE student_gender VARCHAR(10);
  DECLARE block_policy VARCHAR(10);
  SELECT r.capacity, b.gender_policy INTO room_cap, block_policy
    FROM beds be JOIN rooms r ON be.room_id=r.room_id JOIN hostel_blocks b ON r.block_id=b.block_id
    WHERE be.bed_id=NEW.bed_id;
  SELECT COUNT(*) INTO room_bed_count FROM allocations a JOIN beds be ON a.bed_id=be.bed_id
    JOIN rooms r ON be.room_id=r.room_id WHERE r.room_id=(SELECT room_id FROM beds WHERE bed_id=NEW.bed_id)
    AND a.status='ACTIVE';
  IF room_bed_count >= room_cap THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Room occupancy capacity exceeded'; END IF;
  SELECT gender INTO student_gender FROM students WHERE student_id=NEW.student_id;
  IF block_policy <> 'MIXED' AND student_gender <> block_policy THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Student gender conflicts with hostel block policy';
  END IF;
END$$
CREATE TRIGGER trg_allocation_validate_update BEFORE UPDATE ON allocations FOR EACH ROW
BEGIN
  IF NEW.actual_vacate_date IS NOT NULL AND NEW.actual_vacate_date < NEW.allocation_date THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Vacating date cannot precede allocation date';
  END IF;
END$$
CREATE TRIGGER trg_vacating_validate_insert BEFORE INSERT ON vacating_records FOR EACH ROW
BEGIN
  DECLARE start_date DATE;
  SELECT allocation_date INTO start_date FROM allocations WHERE allocation_id=NEW.allocation_id;
  IF NEW.vacating_date < start_date THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Vacating date cannot precede allocation date';
  END IF;
END$$
DELIMITER ;

CREATE OR REPLACE VIEW v_occupancy AS
SELECT hb.block_id, hb.block_code, hb.block_name, r.room_id, r.room_number,
       r.capacity, COUNT(DISTINCT be.bed_id) AS bed_count,
       COUNT(DISTINCT a.allocation_id) AS occupied_beds,
       r.capacity - COUNT(DISTINCT a.allocation_id) AS available_capacity,
       ROUND(100 * COUNT(DISTINCT a.allocation_id) / NULLIF(r.capacity,0), 1) AS occupancy_percent
FROM hostel_blocks hb JOIN rooms r ON r.block_id=hb.block_id
LEFT JOIN beds be ON be.room_id=r.room_id AND be.is_active=TRUE
LEFT JOIN allocations a ON a.bed_id=be.bed_id AND a.status='ACTIVE'
GROUP BY hb.block_id, hb.block_code, hb.block_name, r.room_id, r.room_number, r.capacity;

CREATE OR REPLACE VIEW v_vacant_beds AS
SELECT be.bed_id, be.bed_label, r.room_number, hb.block_code, hb.block_name
FROM beds be JOIN rooms r ON r.room_id=be.room_id JOIN hostel_blocks hb ON hb.block_id=r.block_id
LEFT JOIN allocations a ON a.bed_id=be.bed_id AND a.status='ACTIVE'
WHERE be.is_active=TRUE AND r.is_active=TRUE AND hb.is_active=TRUE AND a.allocation_id IS NULL;

CREATE OR REPLACE VIEW v_fee_dues AS
SELECT s.student_id, s.registration_no, s.first_name, s.last_name,
       fs.fee_schedule_id, fs.academic_year, fs.term, fs.fee_type, fs.due_date,
       fs.amount AS fee_amount, COALESCE(SUM(p.amount),0) AS paid_amount,
       fs.amount-COALESCE(SUM(p.amount),0) AS balance
FROM students s CROSS JOIN fee_schedules fs
LEFT JOIN payments p ON p.student_id=s.student_id AND p.fee_schedule_id=fs.fee_schedule_id
WHERE fs.is_active=TRUE
GROUP BY s.student_id, s.registration_no, s.first_name, s.last_name,
         fs.fee_schedule_id, fs.academic_year, fs.term, fs.fee_type, fs.due_date, fs.amount;
