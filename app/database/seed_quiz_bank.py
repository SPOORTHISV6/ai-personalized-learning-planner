
from sqlalchemy.orm import Session

from app.database.connection import SessionLocal
from app.database.models import Student, Subject, Topic, Quiz, QuizQuestion


STUDENT_ID = 5

QUIZ_BANK = {
    6: {
        "title": "SQL Joins Assessment",
        "difficulty": 3,
        "questions": [
            {
                "question_text": "Which SQL JOIN returns only rows with matching values in both tables?",
                "option_a": "LEFT JOIN",
                "option_b": "RIGHT JOIN",
                "option_c": "INNER JOIN",
                "option_d": "FULL OUTER JOIN",
                "correct_option": "C",
                "explanation": "INNER JOIN returns rows where the join condition matches in both tables.",
            },
            {
                "question_text": "Which JOIN returns all rows from the left table and matching rows from the right table?",
                "option_a": "INNER JOIN",
                "option_b": "LEFT JOIN",
                "option_c": "CROSS JOIN",
                "option_d": "SELF JOIN",
                "correct_option": "B",
                "explanation": "LEFT JOIN preserves every row from the left table and fills unmatched right-side columns with NULL.",
            },
            {
                "question_text": "What happens when a LEFT JOIN finds no matching row in the right table?",
                "option_a": "The left row is removed",
                "option_b": "The query returns an error",
                "option_c": "Right table columns contain NULL",
                "option_d": "The row is duplicated",
                "correct_option": "C",
                "explanation": "Unmatched columns from the right table are returned as NULL.",
            },
            {
                "question_text": "Which JOIN produces the Cartesian product of two tables?",
                "option_a": "INNER JOIN",
                "option_b": "CROSS JOIN",
                "option_c": "LEFT JOIN",
                "option_d": "FULL OUTER JOIN",
                "correct_option": "B",
                "explanation": "CROSS JOIN combines every row of the first table with every row of the second table.",
            },
            {
                "question_text": "Which JOIN is useful when a table needs to be joined with itself?",
                "option_a": "SELF JOIN",
                "option_b": "CROSS JOIN",
                "option_c": "FULL JOIN",
                "option_d": "NATURAL JOIN",
                "correct_option": "A",
                "explanation": "A SELF JOIN compares rows within the same table using table aliases.",
            },
            {
                "question_text": "Which clause specifies the condition used to match rows in a JOIN?",
                "option_a": "GROUP BY",
                "option_b": "ORDER BY",
                "option_c": "ON",
                "option_d": "HAVING",
                "correct_option": "C",
                "explanation": "The ON clause defines the relationship between the joined tables.",
            },
            {
                "question_text": "A Students table has 5 rows and a Courses table has 4 rows. How many rows can a CROSS JOIN produce?",
                "option_a": "9",
                "option_b": "20",
                "option_c": "5",
                "option_d": "4",
                "correct_option": "B",
                "explanation": "A CROSS JOIN produces 5 multiplied by 4, which equals 20 rows.",
            },
            {
                "question_text": "Which JOIN returns unmatched rows from both tables, where supported?",
                "option_a": "INNER JOIN",
                "option_b": "LEFT JOIN",
                "option_c": "RIGHT JOIN",
                "option_d": "FULL OUTER JOIN",
                "correct_option": "D",
                "explanation": "FULL OUTER JOIN preserves matched and unmatched rows from both sides.",
            },
            {
                "question_text": "What is the purpose of table aliases in a SELF JOIN?",
                "option_a": "To permanently rename the table",
                "option_b": "To distinguish the two references to the same table",
                "option_c": "To delete duplicate rows",
                "option_d": "To create a new table",
                "correct_option": "B",
                "explanation": "Aliases let SQL distinguish the two logical references to the same physical table.",
            },
            {
                "question_text": "Which query correctly joins Students and Enrollments using student_id?",
                "option_a": "SELECT * FROM Students s JOIN Enrollments e ON s.student_id = e.student_id;",
                "option_b": "SELECT * FROM Students s JOIN Enrollments e WHERE s.student_id;",
                "option_c": "SELECT * FROM Students s GROUP BY Enrollments e;",
                "option_d": "SELECT * FROM Students s ORDER BY e.student_id;",
                "correct_option": "A",
                "explanation": "The ON condition matches the student_id columns from both tables.",
            },
        ],
    },

    7: {
        "title": "Normalization Assessment",
        "difficulty": 3,
        "questions": [
            {
                "question_text": "What is the primary purpose of database normalization?",
                "option_a": "Increase data duplication",
                "option_b": "Reduce redundancy and improve data integrity",
                "option_c": "Remove all primary keys",
                "option_d": "Increase the number of tables without reason",
                "correct_option": "B",
                "explanation": "Normalization organizes data to reduce redundancy and prevent modification anomalies.",
            },
            {
                "question_text": "Which normal form requires every attribute to contain atomic values?",
                "option_a": "1NF",
                "option_b": "2NF",
                "option_c": "3NF",
                "option_d": "BCNF",
                "correct_option": "A",
                "explanation": "First Normal Form requires each attribute value to be atomic.",
            },
            {
                "question_text": "A relation is in 2NF when it is in 1NF and has no:",
                "option_a": "Foreign keys",
                "option_b": "Partial dependency of non-key attributes on a candidate key",
                "option_c": "Primary key",
                "option_d": "Candidate keys",
                "correct_option": "B",
                "explanation": "Second Normal Form removes partial dependencies on a composite candidate key.",
            },
            {
                "question_text": "Which normal form removes transitive dependencies of non-key attributes on candidate keys?",
                "option_a": "1NF",
                "option_b": "2NF",
                "option_c": "3NF",
                "option_d": "None of these",
                "correct_option": "C",
                "explanation": "Third Normal Form addresses transitive dependencies of non-key attributes.",
            },
            {
                "question_text": "What is a partial dependency?",
                "option_a": "A non-key attribute depends on only part of a composite candidate key",
                "option_b": "A primary key depends on a foreign key",
                "option_c": "Every attribute depends on the entire key",
                "option_d": "A table has no candidate key",
                "correct_option": "A",
                "explanation": "Partial dependency occurs when a non-key attribute depends on a proper subset of a composite candidate key.",
            },
            {
                "question_text": "Which of the following is a common anomaly caused by data redundancy?",
                "option_a": "Insertion anomaly",
                "option_b": "Compilation anomaly",
                "option_c": "Network anomaly",
                "option_d": "Execution anomaly",
                "correct_option": "A",
                "explanation": "Insertion, update and deletion anomalies can occur when data is redundantly stored.",
            },
            {
                "question_text": "A table stores StudentID, StudentName, CourseID and Grade. If StudentName depends only on StudentID, what issue may occur with a composite key (StudentID, CourseID)?",
                "option_a": "Transitive dependency",
                "option_b": "Partial dependency",
                "option_c": "Multivalued dependency",
                "option_d": "No dependency",
                "correct_option": "B",
                "explanation": "StudentName depends on only StudentID, which is part of the composite key.",
            },
            {
                "question_text": "In BCNF, for every non-trivial functional dependency X -> Y, what must X be?",
                "option_a": "A foreign key",
                "option_b": "A non-prime attribute",
                "option_c": "A superkey",
                "option_d": "A nullable attribute",
                "correct_option": "C",
                "explanation": "BCNF requires the determinant of every non-trivial functional dependency to be a superkey.",
            },
            {
                "question_text": "Which operation can introduce a deletion anomaly in a poorly normalized table?",
                "option_a": "Deleting a row may unintentionally remove other useful information",
                "option_b": "Sorting rows alphabetically",
                "option_c": "Creating an index",
                "option_d": "Renaming a column",
                "correct_option": "A",
                "explanation": "A deletion anomaly occurs when deleting one fact accidentally removes another fact stored in the same row.",
            },
            {
                "question_text": "Why might a normalized database be decomposed into multiple related tables?",
                "option_a": "To increase uncontrolled duplication",
                "option_b": "To separate logically independent facts and reduce anomalies",
                "option_c": "To eliminate relationships",
                "option_d": "To avoid using SQL JOINs",
                "correct_option": "B",
                "explanation": "Decomposition separates facts into related relations to reduce redundancy and anomalies.",
            },
        ],
    },

    8: {
        "title": "Python OOP Assessment",
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
                "question_text": "Which keyword is used to define a class in Python?",
                "option_a": "object",
                "option_b": "class",
                "option_c": "define",
                "option_d": "struct",
                "correct_option": "B",
                "explanation": "The class keyword defines a class in Python.",
            },
            {
                "question_text": "What is the purpose of the __init__ method?",
                "option_a": "Destroy an object",
                "option_b": "Initialize a newly created object",
                "option_c": "Import a module",
                "option_d": "Create a loop",
                "correct_option": "B",
                "explanation": "__init__ initializes an instance after it has been created.",
            },
            {
                "question_text": "What does self represent in an instance method?",
                "option_a": "The parent class",
                "option_b": "The current instance",
                "option_c": "A global variable",
                "option_d": "The module name",
                "correct_option": "B",
                "explanation": "self refers to the current instance and is used to access its attributes and methods.",
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
                "option_a": "Defining a method with the same name in a subclass to provide different behavior",
                "option_b": "Deleting a parent class",
                "option_c": "Calling a method without an object",
                "option_d": "Defining two unrelated variables",
                "correct_option": "A",
                "explanation": "A subclass overrides an inherited method by providing its own implementation.",
            },
            {
                "question_text": "Which function is commonly used to call a parent class method in Python?",
                "option_a": "parent()",
                "option_b": "base()",
                "option_c": "super()",
                "option_d": "this()",
                "correct_option": "C",
                "explanation": "super() provides access to methods in the method resolution order, including parent class methods.",
            },
            {
                "question_text": "Which concept bundles data and methods together and controls access to internal state?",
                "option_a": "Encapsulation",
                "option_b": "Inheritance",
                "option_c": "Iteration",
                "option_d": "Recursion",
                "correct_option": "A",
                "explanation": "Encapsulation groups data and related methods while controlling how internal state is accessed.",
            },
            {
                "question_text": "What is polymorphism in OOP?",
                "option_a": "Using one interface with different implementations",
                "option_b": "Creating only one object",
                "option_c": "Making every variable global",
                "option_d": "Removing class methods",
                "correct_option": "A",
                "explanation": "Polymorphism allows different objects to respond to the same interface in different ways.",
            },
            {
                "question_text": "What is the output of this code? class A: def speak(self): return 'A'; class B(A): def speak(self): return 'B'; print(B().speak())",
                "option_a": "A",
                "option_b": "B",
                "option_c": "None",
                "option_d": "Error",
                "correct_option": "B",
                "explanation": "Class B overrides speak(), so the instance of B returns 'B'.",
            },
        ],
    },
}


def seed_quiz_bank(db: Session):
    student = db.query(Student).filter(
        Student.student_id == STUDENT_ID
    ).first()

    if not student:
        raise ValueError(f"Student {STUDENT_ID} does not exist.")

    print(f"Seeding quiz banks for {student.name} (ID: {STUDENT_ID})")

    inserted_count = 0
    skipped_count = 0

    try:
        for topic_id, config in QUIZ_BANK.items():

            # Verify that the topic belongs to this student.
            topic = (
                db.query(Topic)
                .join(Subject, Topic.subject_id == Subject.subject_id)
                .filter(
                    Topic.topic_id == topic_id,
                    Subject.student_id == STUDENT_ID,
                )
                .first()
            )

            if not topic:
                raise ValueError(
                    f"Topic {topic_id} does not belong to student {STUDENT_ID}."
                )

            # Reuse an existing quiz with this title, if present.
            quiz = (
                db.query(Quiz)
                .filter(
                    Quiz.topic_id == topic_id,
                    Quiz.title == config["title"],
                )
                .first()
            )

            if not quiz:
                quiz = Quiz(
                    topic_id=topic_id,
                    title=config["title"],
                    difficulty=config["difficulty"],
                )
                db.add(quiz)
                db.flush()
                print(f"Created quiz: {config['title']}")
            else:
                print(f"Reusing quiz: {config['title']}")

            existing_questions = {
                q.question_text
                for q in db.query(QuizQuestion)
                .filter(QuizQuestion.quiz_id == quiz.quiz_id)
                .all()
            }

            for question in config["questions"]:
                if question["question_text"] in existing_questions:
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
                inserted_count += 1

        db.commit()

        print("\nQuiz bank seeding completed.")
        print(f"Questions inserted: {inserted_count}")
        print(f"Questions skipped: {skipped_count}")

    except Exception:
        db.rollback()
        raise


def main():
    db = SessionLocal()
    try:
        seed_quiz_bank(db)
    finally:
        db.close()


if __name__ == "__main__":
    main()
