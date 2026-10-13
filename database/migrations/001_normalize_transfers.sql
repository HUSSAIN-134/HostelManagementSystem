-- Apply once to an existing database created from the earlier project schema.
-- Transfer student identity is derivable from its referenced allocation rows.
-- The audit verified the existing transfer row has matching student IDs on
-- the source and destination allocations before applying this migration.
ALTER TABLE transfers
  DROP FOREIGN KEY fk_transfer_student,
  DROP INDEX fk_transfer_student,
  DROP COLUMN student_id;
