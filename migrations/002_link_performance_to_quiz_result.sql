
ALTER TABLE performance
ADD COLUMN quiz_result_id INT NULL;

ALTER TABLE performance
ADD CONSTRAINT uq_performance_quiz_result_id
UNIQUE (quiz_result_id);

ALTER TABLE performance
ADD CONSTRAINT fk_performance_quiz_result
FOREIGN KEY (quiz_result_id)
REFERENCES quiz_results(result_id)
ON DELETE SET NULL;
