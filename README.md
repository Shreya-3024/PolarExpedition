# PolarOps

PolarOps is a Django-based polar expedition logistics and asset management workspace. The app uses server-rendered templates and a local SQLite database.

## Run locally on Windows

From the project folder, open PowerShell and run:

```powershell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_demo
python manage.py createsuperuser
python manage.py runserver
```

Open `http://127.0.0.1:8000/` and sign in with the superuser created above. The Django admin is available at `/admin/`. Sample records are added by `seed_demo`; it is safe to run the command again.

Password reset emails use Django's console email backend for local development, so the reset link appears in the runserver terminal. Set `DJANGO_SECRET_KEY`, `DJANGO_DEBUG=0`, and `DJANGO_ALLOWED_HOSTS` before deploying.

## Main areas

- Command center dashboard and polar operations overview
- Expedition, asset, inventory, shipment, logistics, team, and maintenance CRUD
- Search, status filters, pagination, record details, and delete confirmation
- Notifications, profile settings, and downloadable CSV reporting
- Django authentication, registration, and password reset
-password-K2!Aurora-Glacier#94Tundra