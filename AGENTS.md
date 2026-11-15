# PolarOps project guidelines

## Architecture

- The application is Django: `manage.py`, `polarops/`, and `operations/`.
- Server-rendered templates live in `templates/`; shared styling is in `static/css/app.css`.
- SQLite is the local database. Add model changes through Django migrations.

## Build and test

- Install Python dependencies with `pip install -r requirements.txt`.
- Apply schema changes with `python manage.py migrate`.
- Start the Django app with `python manage.py runserver`.
- Run application tests with `python manage.py test operations`.
- Load example records with `python manage.py seed_demo`.

## Conventions

- Use Django forms, CSRF protection, messages, and named URL routes for browser workflows.
- Protect operational views with Django authentication.
- Keep sample data optional and safe to rerun; do not commit local databases, secrets, or virtual environments.
- Keep user-facing styles responsive and shared through the application stylesheet.
