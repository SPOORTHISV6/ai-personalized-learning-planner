ALTER TABLE study_plan_items
ADD COLUMN learning_objective TEXT NULL,
ADD COLUMN study_activity TEXT NULL,
ADD COLUMN resources JSON NULL,
ADD COLUMN expected_outcome TEXT NULL,
ADD COLUMN session_type VARCHAR(50) NULL,
ADD COLUMN reason TEXT NULL,
ADD COLUMN score FLOAT NULL,
ADD COLUMN learning_status VARCHAR(30) NULL;