# FastAPI Testing Demo

Small FastAPI project written in pure Python that demonstrates:

- A minimal `/users/` API backed by SQLite + SQLAlchemy.
- Basic tests with `pytest` and `TestClient`.
- Use of fixtures and an in-memory SQLite database for isolation.
- Error simulation with `monkeypatch` / mocks.
- Continuous integration with GitHub Actions.

## Project layout

```text
app/
  __init__.py
  main.py          # FastAPI app
  database.py      # SQLAlchemy engine, SessionLocal, Base, get_db
  models.py        # ORM models
  schemas.py       # Pydantic schemas
  crud.py          # DB access helpers

tests/
  conftest.py      # PyTest fixtures (TestClient, test DB, factory)
  test_users.py    # Basic API tests
  test_error_handling.py  # Mock / monkeypatch example

.github/
  workflows/
    tests.yml      # GitHub Actions workflow for running pytest
```

## Running the app locally

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Then open http://127.0.0.1:8000/docs to play with the API.

## Running tests

```bash
pytest
```

## GitHub Actions

1. Create a **private** GitHub repository.
2. Copy this project into it and push.
3. The workflow in `.github/workflows/tests.yml` will automatically run
   `pytest` on every push and pull request.
4. Take a screenshot of a successful run from the GitHub Actions UI and
   include it in your assignment submission if required.
