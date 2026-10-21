
from sqlalchemy import create_engine, inspect, text

DATABASE_URL = (
    "mysql+pymysql://root:root@localhost:3306/"
    "ai_learning_planner"
)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)

try:
    with engine.begin() as conn:
        database = conn.execute(
            text("SELECT DATABASE()")
        ).scalar_one()

        if database != "ai_learning_planner":
            raise RuntimeError(
                f"Unsafe database target: {database}"
            )

        inspector = inspect(conn)

        columns = {
            column["name"]
            for column in inspector.get_columns("performance")
        }

        if "quiz_result_id" in columns:
            raise RuntimeError(
                "quiz_result_id already exists. Inspect "
                "the schema before proceeding."
            )

        if not inspector.has_table("quiz_results"):
            raise RuntimeError("quiz_results table is missing.")

        conn.execute(text("""
            ALTER TABLE performance
            ADD COLUMN quiz_result_id INT NULL
        """))

        conn.execute(text("""
            ALTER TABLE performance
            ADD CONSTRAINT uq_performance_quiz_result_id
            UNIQUE (quiz_result_id)
        """))

        conn.execute(text("""
            ALTER TABLE performance
            ADD CONSTRAINT fk_performance_quiz_result
            FOREIGN KEY (quiz_result_id)
            REFERENCES quiz_results(result_id)
            ON DELETE SET NULL
        """))

    print("Development database migration applied successfully.")

finally:
    engine.dispose()
