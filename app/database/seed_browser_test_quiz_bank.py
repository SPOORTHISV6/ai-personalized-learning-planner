
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database.connection import SessionLocal
from app.database.models import (
    Student,
    Subject,
    Topic,
    Quiz,
    QuizQuestion,
)


STUDENT_ID = 4
TARGET_QUESTIONS = 10

QUIZ_BANK = {
    1: {
        "title": "SQL Basics Quiz",
        "difficulty": 2,

        "questions": [
            {
                "question_text": "Which SQL command is used to retrieve data from a table?",
                "option_a": "INSERT",
                "option_b": "SELECT",
                "option_c": "UPDATE",
                "option_d": "DELETE",
                "correct_option": "B",
                "explanation": "SELECT retrieves records from one or more database tables.",
            },
            {
                "question_text": "Which SQL clause filters rows based on a condition?",
                "option_a": "ORDER BY",
                "option_b": "GROUP BY",
                "option_c": "WHERE",
                "option_d": "DISTINCT",
                "correct_option": "C",
                "explanation": "WHERE filters rows based on a specified condition.",
            },
            {
                "question_text": "Which SQL clause sorts query results?",
                "option_a": "WHERE",
                "option_b": "ORDER BY",
                "option_c": "HAVING",
                "option_d": "JOIN",
                "correct_option": "B",
                "explanation": "ORDER BY sorts query results in ascending or descending order.",
            },
            {
                "question_text": "Which SQL keyword removes duplicate rows from query results?",
                "option_a": "UNIQUE",
                "option_b": "REMOVE",
                "option_c": "DISTINCT",
                "option_d": "DELETE",
                "correct_option": "C",
                "explanation": "DISTINCT returns only unique rows in the result set.",
            },
            {
                "question_text": "Which aggregate function counts rows?",
                "option_a": "SUM()",
                "option_b": "AVG()",
                "option_c": "COUNT()",
                "option_d": "MAX()",
                "correct_option": "C",
                "explanation": "COUNT() returns the number of rows or non-NULL values, depending on its argument.",
            },
            {
                "question_text": "Which clause filters groups after GROUP BY?",
                "option_a": "WHERE",
                "option_b": "HAVING",
                "option_c": "ORDER BY",
                "option_d": "LIMIT",
                "correct_option": "B",
                "explanation": "HAVING filters grouped results after aggregation.",
            },
            {
                "question_text": "Which operator checks whether a value matches a specified pattern?",
                "option_a": "IN",
                "option_b": "BETWEEN",
                "option_c": "LIKE",
                "option_d": "IS",
                "correct_option": "C",
                "explanation": "LIKE performs pattern matching, commonly using % and _ wildcards.",
            },
            {
                "question_text": "Which SQL command adds a new record to a table?",
                "option_a": "INSERT INTO",
                "option_b": "ALTER TABLE",
                "option_c": "UPDATE",
                "option_d": "DROP TABLE",
                "correct_option": "A",
                "explanation": "INSERT INTO adds new rows to a database table.",
            },
            {
                "question_text": "Which SQL constraint uniquely identifies each record in a table?",
                "option_a": "FOREIGN KEY",
                "option_b": "PRIMARY KEY",
                "option_c": "DEFAULT",
                "option_d": "CHECK",
                "correct_option": "B",
                "explanation": "A PRIMARY KEY uniquely identifies each row and cannot contain NULL values.",
            },
            {
                "question_text": "Which SQL command modifies existing records in a table?",
                "option_a": "INSERT",
                "option_b": "UPDATE",
                "option_c": "CREATE",
                "option_d": "SELECT",
                "correct_option": "B",
                "explanation": "UPDATE modifies existing rows, optionally restricting them with WHERE.",
            },
        ],

    },

    2: {
        "title": "SQL Joins Quiz",
        "difficulty": 3,
        "questions": [
            {
                "question_text": "Which SQL JOIN returns only matching rows from both tables?",
                "option_a": "LEFT JOIN",
                "option_b": "RIGHT JOIN",
                "option_c": "INNER JOIN",
                "option_d": "CROSS JOIN",
                "correct_option": "C",
                "explanation": "INNER JOIN returns rows satisfying the join condition in both tables.",
            },
            {
                "question_text": "Which JOIN preserves every row from the left table?",
                "option_a": "INNER JOIN",
                "option_b": "LEFT JOIN",
                "option_c": "CROSS JOIN",
                "option_d": "SELF JOIN",
                "correct_option": "B",
                "explanation": "LEFT JOIN preserves all left-side rows and uses NULL for unmatched right-side values.",
            },
            {
                "question_text": "What happens to right-table columns when a LEFT JOIN finds no match?",
                "option_a": "They contain NULL",
                "option_b": "The row is deleted",
                "option_c": "The query fails",
                "option_d": "They become zero",
                "correct_option": "A",
                "explanation": "Unmatched columns from the right table are returned as NULL.",
            },
            {
                "question_text": "Which JOIN produces a Cartesian product?",
                "option_a": "INNER JOIN",
                "option_b": "LEFT JOIN",
                "option_c": "CROSS JOIN",
                "option_d": "SELF JOIN",
                "correct_option": "C",
                "explanation": "CROSS JOIN combines every row from the first table with every row from the second.",
            },
            {
                "question_text": "Which JOIN is used to compare rows within the same table?",
                "option_a": "SELF JOIN",
                "option_b": "CROSS JOIN",
                "option_c": "FULL JOIN",
                "option_d": "NATURAL JOIN",
                "correct_option": "A",
                "explanation": "A SELF JOIN references the same table using different aliases.",
            },
            {
                "question_text": "Which clause specifies the matching condition in a JOIN?",
                "option_a": "HAVING",
                "option_b": "ORDER BY",
                "option_c": "ON",
                "option_d": "LIMIT",
                "correct_option": "C",
                "explanation": "The ON clause specifies the relationship between joined tables.",
            },
            {
                "question_text": "A table has 5 rows and another has 4 rows. How many rows can their CROSS JOIN produce?",
                "option_a": "9",
                "option_b": "20",
                "option_c": "5",
                "option_d": "4",
                "correct_option": "B",
                "explanation": "A CROSS JOIN produces the product of the row counts: 5 multiplied by 4.",
            },
            {
                "question_text": "Which JOIN preserves unmatched rows from both tables, where supported?",
                "option_a": "INNER JOIN",
                "option_b": "LEFT JOIN",
                "option_c": "RIGHT JOIN",
                "option_d": "FULL OUTER JOIN",
                "correct_option": "D",
                "explanation": "FULL OUTER JOIN preserves matching and nonmatching rows from both tables.",
            },
            {
                "question_text": "Why are aliases useful in a SELF JOIN?",
                "option_a": "They permanently rename tables",
                "option_b": "They distinguish two references to the same table",
                "option_c": "They remove duplicate records",
                "option_d": "They create indexes",
                "correct_option": "B",
                "explanation": "Aliases distinguish the two logical references to the same physical table.",
            },
            {
                "question_text": "Which query correctly joins Students and Enrollments using student_id?",
                "option_a": "SELECT * FROM Students s JOIN Enrollments e ON s.student_id = e.student_id;",
                "option_b": "SELECT * FROM Students s JOIN Enrollments e WHERE s.student_id;",
                "option_c": "SELECT * FROM Students s GROUP BY Enrollments e;",
                "option_d": "SELECT * FROM Students s ORDER BY e.student_id;",
                "correct_option": "A",
                "explanation": "The ON condition matches student_id in both tables.",
            },
        ],
    },

    3: {
        "title": "Normalization Quiz",
        "difficulty": 3,
        "questions": [
            {
                "question_text": "What is the primary purpose of database normalization?",
                "option_a": "Increase redundancy",
                "option_b": "Reduce redundancy and improve data integrity",
                "option_c": "Remove primary keys",
                "option_d": "Duplicate every record",
                "correct_option": "B",
                "explanation": "Normalization organizes data to reduce redundancy and modification anomalies.",
            },
            {
                "question_text": "Which normal form requires atomic attribute values?",
                "option_a": "1NF",
                "option_b": "2NF",
                "option_c": "3NF",
                "option_d": "BCNF",
                "correct_option": "A",
                "explanation": "First Normal Form requires atomic values in each attribute.",
            },
            {
                "question_text": "Which dependency violates 2NF?",
                "option_a": "Transitive dependency",
                "option_b": "Partial dependency",
                "option_c": "Multivalued dependency",
                "option_d": "Functional dependency on a superkey",
                "correct_option": "B",
                "explanation": "2NF removes partial dependencies of non-key attributes on candidate keys.",
            },
            {
                "question_text": "Which normal form removes transitive dependencies of non-key attributes?",
                "option_a": "1NF",
                "option_b": "2NF",
                "option_c": "3NF",
                "option_d": "None",
                "correct_option": "C",
                "explanation": "Third Normal Form addresses transitive dependencies of non-key attributes.",
            },
            {
                "question_text": "What is a partial dependency?",
                "option_a": "A non-key attribute depends on part of a composite candidate key",
                "option_b": "A primary key depends on a foreign key",
                "option_c": "Every attribute depends on the whole key",
                "option_d": "A table has no candidate key",
                "correct_option": "A",
                "explanation": "Partial dependency occurs when a non-key attribute depends on a proper subset of a composite candidate key.",
            },
            {
                "question_text": "Which is a common anomaly caused by data redundancy?",
                "option_a": "Insertion anomaly",
                "option_b": "Compilation anomaly",
                "option_c": "Network anomaly",
                "option_d": "Execution anomaly",
                "correct_option": "A",
                "explanation": "Insertion, update and deletion anomalies can result from redundant data.",
            },
            {
                "question_text": "StudentID, CourseID and StudentName are stored in a table with composite key (StudentID, CourseID). StudentName depends only on StudentID. What is this?",
                "option_a": "Transitive dependency",
                "option_b": "Partial dependency",
                "option_c": "Multivalued dependency",
                "option_d": "No dependency",
                "correct_option": "B",
                "explanation": "StudentName depends on only part of the composite key.",
            },
            {
                "question_text": "In BCNF, the determinant of every non-trivial functional dependency must be a:",
                "option_a": "Foreign key",
                "option_b": "Non-prime attribute",
                "option_c": "Superkey",
                "option_d": "Nullable attribute",
                "correct_option": "C",
                "explanation": "BCNF requires every determinant of a non-trivial functional dependency to be a superkey.",
            },
            {
                "question_text": "What is a deletion anomaly?",
                "option_a": "Deleting one fact unintentionally removes another useful fact",
                "option_b": "Sorting rows alphabetically",
                "option_c": "Creating an index",
                "option_d": "Renaming a column",
                "correct_option": "A",
                "explanation": "A deletion anomaly occurs when deleting one record unintentionally removes other information.",
            },
            {
                "question_text": "Why is a relation decomposed during normalization?",
                "option_a": "To increase uncontrolled duplication",
                "option_b": "To separate independent facts and reduce anomalies",
                "option_c": "To eliminate all relationships",
                "option_d": "To avoid SQL",
                "correct_option": "B",
                "explanation": "Decomposition separates logically independent facts into related tables.",
            },
        ],
    },

    4: {
        "title": "Python OOP Quiz",
        "difficulty": 3,
        "questions": [
            {
                "question_text": "What does OOP stand for?",
                "option_a": "Object-Oriented Programming",
                "option_b": "Operational Output Processing",
                "option_c": "Object Operation Protocol",
                "option_d": "Ordered Object Programming",
                "correct_option": "A",
                "explanation": "OOP stands for Object-Oriented Programming.",
            },
            {
                "question_text": "Which keyword defines a class in Python?",
                "option_a": "object",
                "option_b": "class",
                "option_c": "define",
                "option_d": "struct",
                "correct_option": "B",
                "explanation": "The class keyword defines a class in Python.",
            },
            {
                "question_text": "What is the purpose of __init__?",
                "option_a": "Destroy an object",
                "option_b": "Initialize an instance",
                "option_c": "Import a module",
                "option_d": "Create a loop",
                "correct_option": "B",
                "explanation": "__init__ initializes an instance after it is created.",
            },
            {
                "question_text": "What does self represent in an instance method?",
                "option_a": "The parent class",
                "option_b": "The current instance",
                "option_c": "A global variable",
                "option_d": "The module name",
                "correct_option": "B",
                "explanation": "self refers to the current instance.",
            },
            {
                "question_text": "Which OOP concept allows a class to acquire properties and methods from another class?",
                "option_a": "Encapsulation",
                "option_b": "Polymorphism",
                "option_c": "Inheritance",
                "option_d": "Abstraction",
                "correct_option": "C",
                "explanation": "Inheritance allows a child class to reuse and extend a parent class.",
            },
            {
                "question_text": "What is method overriding?",
                "option_a": "A subclass provides its own implementation of an inherited method",
                "option_b": "Deleting a parent class",
                "option_c": "Calling a method without an object",
                "option_d": "Defining unrelated variables",
                "correct_option": "A",
                "explanation": "A subclass overrides an inherited method by providing its own implementation.",
            },
            {
                "question_text": "Which function commonly accesses a parent class method?",
                "option_a": "parent()",
                "option_b": "base()",
                "option_c": "super()",
                "option_d": "this()",
                "correct_option": "C",
                "explanation": "super() provides access to methods in the method resolution order.",
            },
            {
                "question_text": "Which concept bundles data and methods together?",
                "option_a": "Encapsulation",
                "option_b": "Inheritance",
                "option_c": "Iteration",
                "option_d": "Recursion",
                "correct_option": "A",
                "explanation": "Encapsulation groups data and related methods while controlling access to internal state.",
            },
            {
                "question_text": "What is polymorphism?",
                "option_a": "Using one interface with different implementations",
                "option_b": "Creating only one object",
                "option_c": "Making every variable global",
                "option_d": "Removing class methods",
                "correct_option": "A",
                "explanation": "Polymorphism allows different objects to respond to the same interface differently.",
            },
            {
                "question_text": "What is the output? class A: def speak(self): return 'A'; class B(A): def speak(self): return 'B'; print(B().speak())",
                "option_a": "A",
                "option_b": "B",
                "option_c": "None",
                "option_d": "Error",
                "correct_option": "B",
                "explanation": "Class B overrides speak(), so B().speak() returns B.",
            },
        ],
    },
}


def seed_quiz_bank(db: Session):
    student = (
        db.query(Student)
        .filter(Student.student_id == STUDENT_ID)
        .one_or_none()
    )

    if student is None:
        raise ValueError("Browser-test student was not found.")

    print(f"Student: {student.name} ({STUDENT_ID})")

    inserted_count = 0
    skipped_count = 0

    try:
        for topic_id, config in QUIZ_BANK.items():

            topic = (
                db.query(Topic)
                .join(Subject, Topic.subject_id == Subject.subject_id)
                .filter(
                    Topic.topic_id == topic_id,
                    Subject.student_id == STUDENT_ID,
                )
                .one_or_none()
            )

            if topic is None:
                raise ValueError(
                    f"Topic {topic_id} does not belong to student {STUDENT_ID}."
                )

            quiz = (
                db.query(Quiz)
                .filter(Quiz.topic_id == topic_id)
                .order_by(Quiz.quiz_id)
                .first()
            )

            if quiz is None:
                quiz = Quiz(
                    topic_id=topic_id,
                    title=config["title"],
                    difficulty=config["difficulty"],
                )
                db.add(quiz)
                db.flush()
                print(f"Created quiz: {config['title']}")
            else:
                print(f"Reusing quiz: {quiz.title}")

            existing_count = (
                db.query(func.count(QuizQuestion.question_id))
                .filter(QuizQuestion.quiz_id == quiz.quiz_id)
                .scalar()
            )

            existing_texts = {
                question.question_text
                for question in db.query(QuizQuestion)
                .filter(QuizQuestion.quiz_id == quiz.quiz_id)
                .all()
            }

            for question in config["questions"]:

                if existing_count >= TARGET_QUESTIONS:
                    break

                if question["question_text"] in existing_texts:
                    skipped_count += 1
                    continue

                db.add(
                    QuizQuestion(
                        quiz_id=quiz.quiz_id,
                        question_text=question["question_text"],
                        option_a=question["option_a"],
                        option_b=question["option_b"],
                        option_c=question["option_c"],
                        option_d=question["option_d"],
                        correct_option=question["correct_option"],
                        explanation=question["explanation"],
                        points=1,
                    )
                )

                existing_texts.add(question["question_text"])
                existing_count += 1
                inserted_count += 1

            if existing_count < TARGET_QUESTIONS:
                raise ValueError(
                    f"{topic.topic_name} has only {existing_count} questions. "
                    "More questions must be added."
                )

        db.commit()

        print("\nQUIZ BANK SEEDING SUCCESSFUL")
        print("Questions inserted:", inserted_count)
        print("Duplicate questions skipped:", skipped_count)

    except Exception:
        db.rollback()
        raise


def main():
    # Confirm the application is using the isolated browser database.
    from sqlalchemy import text

    with SessionLocal() as db:
        database = db.execute(
            text("SELECT DATABASE()")
        ).scalar_one()

        account = db.execute(
            text("SELECT CURRENT_USER()")
        ).scalar_one()

        if database != "ai_learning_planner_browser_test":
            raise RuntimeError("Wrong database. Seeding cancelled.")

        if account != "browser_test_app@localhost":
            raise RuntimeError("Wrong database account. Seeding cancelled.")

        seed_quiz_bank(db)


if __name__ == "__main__":
    main()
