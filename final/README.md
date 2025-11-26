# TestHub - Final Delivery

Final build of **TestHub**, a FastAPI + PostgreSQL app for authoring and taking online quizzes. HTML is rendered with Jinja2 templates; sessions handle login; roles gate authoring versus test-taking.

## Features

- User accounts with session login/logout and registration (optionally request author permissions).
- Role-aware navigation (Admin/Author/Test Taker), seeded default admin (`admin@testhub.local` / `ChangeMe123!`).
- CRUD for **Tests** (publish toggle, difficulty, time limit) and **Questions** (free-text or single/multiple choice with correct answers).
- Taking tests: start attempts, submit answers, automatic scoring for choice questions, per-question result breakdown.
- Dashboard: see recent attempts and authored tests.
- Server-side validation and friendly banners plus custom 404/500 pages.

## Quickstart

1. Start PostgreSQL (defaults from `.env.example`):

```bash
cd final
docker compose up -d db
```

2. Create a virtualenv and install deps:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

3. Configure environment:

```bash
cp .env.example .env
```

4. Run the app:

```bash
uvicorn app.main:app --reload
```

Visit http://127.0.0.1:8000/tests

## Usage

- **Register/Login**: via `/auth/register` or `/auth/login`. Registration grants Test Taker; optionally check "author" to create tests. Default admin is pre-seeded with admin/author/test_taker roles.
- **Authoring**: Authors/Admins can create tests, add/edit/delete questions/options, and publish/unpublish tests. Drafts are only visible to the creator/admin.
- **Taking tests**: Logged-in users can start attempts on published tests with questions. Submission auto-scores choice questions; free-text is recorded for later review. Results show per-question correctness and totals.
- **Dashboard**: `/dashboard` lists your recent attempts and authored tests.

## Notes

- Tables auto-create on startup and seed roles/admin user from `.env`.
- Cascades remove questions/options when a test is deleted. Question delete is also available individually.
- Time limits are stored but not enforced client-side in this build. Add migrations/tests as next hardening steps for production.
