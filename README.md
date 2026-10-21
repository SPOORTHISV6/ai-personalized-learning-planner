\# AI Personalized Learning \& Study Planner



An AI-powered learning platform that analyzes student performance, identifies learning gaps, and generates personalized study plans using an agent-based workflow and Retrieval-Augmented Generation (RAG).



\## Features



\- \*\*Adaptive Learning:\*\* Adjusts learning priorities based on student performance.

\- \*\*Learning Gap Analysis:\*\* Identifies weak, moderate, and strong topics.

\- \*\*Personalized Study Plans:\*\* Generates and validates study sessions.

\- \*\*Performance Evaluation:\*\* Evaluates quiz scores and stores performance records.

\- \*\*Student Memory:\*\* Maintains learning history and relevant student context.

\- \*\*RAG-Based Resources:\*\* Retrieves relevant educational content from indexed curriculum documents.

\- \*\*REST API:\*\* Provides endpoints for students, subjects, topics, quizzes, resources, performance, and study plans.

\- \*\*Database Persistence:\*\* Uses MySQL to store student and learning data.

\- \*\*Automated Tests:\*\* Includes unit, workflow, API, and database integration tests.



\## Technology Stack



\- \*\*Language:\*\* Python

\- \*\*Backend:\*\* FastAPI

\- \*\*Database:\*\* MySQL

\- \*\*ORM:\*\* SQLAlchemy

\- \*\*Validation:\*\* Pydantic

\- \*\*RAG:\*\* FAISS and Sentence Transformers

\- \*\*Workflow:\*\* Agent-based learning and evaluation workflows

\- \*\*Testing:\*\* pytest



\## Project Structure



```text

ai-personalized-learning-planner/

├── app/

│   ├── agents/

│   ├── api/

│   ├── core/

│   ├── database/

│   ├── memory/

│   ├── rag/

│   ├── schemas/

│   ├── tools/

│   ├── validation/

│   └── workflows/

├── data/

│   ├── documents/

│   ├── extraction\_reports/

│   └── vector\_store/

├── frontend/

├── migrations/

├── tests/

├── requirements.txt

└── README.md

```



\## Setup



\### 1. Clone the repository



```bash

git clone https://github.com/SPOORTHISV6/ai-personalized-learning-planner.git

cd ai-personalized-learning-planner

```



\### 2. Create a virtual environment



Windows PowerShell:



```powershell

py -3.12 -m venv .venv

.\\.venv\\Scripts\\Activate.ps1

```



\### 3. Install dependencies



```powershell

python -m pip install --upgrade pip

pip install -r requirements.txt

```



\### 4. Configure MySQL



Create the development database in MySQL:



```sql

CREATE DATABASE ai\_learning\_planner;

```



Configure the database connection using your local environment settings. Do not commit passwords, secret keys, or other credentials.



Review the SQL files in `migrations/` before applying migrations. Apply each migration only when the corresponding schema change is not already present.



\### 5. Start the application



Run the FastAPI application using the entry point defined in `app/main.py`:



```powershell

python -m uvicorn app.main:app --reload

```



Open the interactive API documentation at:



`http://127.0.0.1:8000/docs`



\## Testing



Run the test suite:



```powershell

python -m pytest -q

```



MySQL integration tests require a separate test database. Configure `ai\_learning\_planner\_test` and its connection settings according to `tests/integration/test\_database.py` before running integration tests.



Enable the integration-test guard in PowerShell when required:



```powershell

$env:ALLOW\_MYSQL\_INTEGRATION\_TESTS = "1"

```



Never run integration tests against the development database.



\## Current Status



The project includes adaptive learning workflows, RAG-based resource retrieval, performance evaluation, study-plan validation, MySQL persistence, and automated tests.



\## Future Improvements



\- Add a user-friendly student dashboard.

\- Improve learning-resource retrieval and evaluation.

\- Add progress visualizations and study reminders.

\- Deploy the application with secure database configuration.



\## Author



Spoorthi S. V.

