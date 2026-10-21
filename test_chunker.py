from app.rag.chunker import is_heading

tests = {
    "2. INNER JOIN": True,
    "3. LEFT JOIN": True,
    "4. RIGHT JOIN": True,
    "5. FULL OUTER JOIN": True,
    "7. SELF JOIN": True,
    "8. JOIN Conditions": True,
    "7. Normalization": True,
    "10.5.1 First Normal Form (1NF)": True,
    "4. Join employees with their managers using SELF JOIN.": False,
    "5. Explain INNER JOIN versus LEFT JOIN.": False,
    "1. What is a DBMS?": False,
}

for line, expected in tests.items():
    actual = is_heading(line)
    status = "PASS" if actual == expected else "FAIL"
    print(f"{status}: {line}")

    if actual != expected:
        raise AssertionError(
            f"Expected {expected}, got {actual}: {line}"
        )

print("\nAll heading tests passed.")