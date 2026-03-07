Project for tracking poker stats from tournaments. 

**This is a work in progress**.

# Local Dev Setup

## Prerequisites
- Python 3.10 (install via Scoop: `scoop install versions/python310`)
- PostgreSQL 10+ installed and running as a Windows service

## Steps

1. **Create and activate the virtual environment** (from the parent `PokerStats/` directory):
    ```bat
    py -3.10 -m venv D:\DjangoProjects\PokerStats
    D:\DjangoProjects\PokerStats\Scripts\activate
    ```

2. **Install dependencies**:
    ```bat
    pip install -r requirements.txt
    ```

3. **Create a `.env` file** in the project root based on the prod `.env`, but override:
    - `DB_NAME`, `DB_USER`, `DB_PASSWORD` — local PostgreSQL credentials
    - `EMAIL_PASSWORD` — must be a Gmail [App Password](https://support.google.com/accounts/answer/185833), not your regular Gmail password

4. **Create a local database** in psql:
    ```sql
    CREATE DATABASE your_db_name;
    ```

5. **Run migrations**:
    ```bat
    python manage.py migrate
    ```

6. **Run the server**:
    ```bat
    python manage.py runserver
    ```

## Prod
- Server: 67.205.147.15 (Python 3.10.12, PostgreSQL 14, Django 3.2, Gunicorn)
- Restart Gunicorn after changes: `sudo systemctl restart gunicorn`
- Static/media files served from AWS S3

# Running tests
```
python3 manage.py test tournament/
python3 manage.py test tournament_analytics/tests
python3 manage.py test tournament_group/tests
```

# Resources
1. django-allauth
	1. doc: https://django-allauth.readthedocs.io/en/latest/index.html
	1. https://github.com/ksarthak4ever/Django-Video_Subscription_App
	1. https://www.codesnail.com/django-allauth-email-authentication-tutorial
	1. https://medium.com/@ksarthak4ever/django-custom-user-model-allauth-for-oauth-20c84888c318
1. django-bootstrap-v5
	1. doc: https://django-bootstrap-v5.readthedocs.io/en/latest/index.html
1. Chart.js
	1. https://www.chartjs.org/docs





