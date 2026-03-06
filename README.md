Project for tracking poker stats from tournaments. 

**This is a work in progress**.

# Features:
1. User management
	1. Registration
	1. Login
	1. Password reset
	1. Email/account verification
	1. Google account signup
1. Track game statistics
1. Personalized game statistics
1. TODO... more stuff

# TODO
This is a notes section for me personally.
1. Split winners
	- Need to think about this.
1. Tournament "MVP"? How would this be calculated
1. Completing a tournament takes a long time. Figure out why.
1. Rendering tournament view takes a long time. Figure out why.
1. Add footer
1. Create invite system for TournamentGroups. Just like with Tournaments.
1. Setup bugsnag
1. Setup Jira for further feature work
1. Prevent analytics from considering tournaments you did not join
	- everything in tournament_analytics.html
1. Send an email when invited to tournament
1. Add timestamp input for backfilling tournaments (this can override the started_at and completed_at dates?)
1. Add a notes field to the tournament. 
	- That way I can write a note saying: "data is slightly wrong becuase a split elimination occurred between x players or whatver"
1. Google signin issue? Not working for people to sign up with google account (See screenshot saved)
	- Seems to be from opening pokerstats.lol from within another app. Can I fix this easily?

## TODO (after app is fully functional)
1. Optimize everything for mobile. (I think this is already done, but confirm)
	- 99% of the time this is going to be used from a phone.
1. Remove CDNs
	1. Chart.js: tournament_totals.html
	1. base.html
1. Add recaptcha to registration/login https://pypi.org/project/django-recaptcha/
	- Or maybe just delete accounts after X days if they have not be verified?
1. Screenshot tests?
1. Figure out how to make the website timezone aware
	- Probably just need to save the timezone of the user in their profile data and then do a conversion in every view that uses a date.
1. Make admin not automatically join a tournament when they create it.
1. Add splitting feature
1. Shareable invite link to a tournament? If user has no registered then they are prompted to before joining.
1. Create Jira project with an email from whatever domain I end up using.
1. "Guest" feature. Dunno if I really want this it would be very complicated. PRobably something to think about after launch.
	- If someone wanted to track their analytics and the people they were playing with do not use the site.
	- Also for backfilling, not everyone may have registered or something
	- Also need some kind of mechanism for going back into a completed Tournament and assigning a user to a guest. Like if you finished a tournament with a guest you could go back and assign a real user to it
	- Ability to give the Guest a temporary name. Just a string.
1. Backfill a tournament where the eliminations were not tracked and bounties are not enabled.
	- A nice feature would be the ability to backfill a tournament when the eliminations aren't known. Then just backfilled based on how many players rebought?
	- The data wouldn't be great but at least you'd see placement data.
	- I have a spike branch thats incomplete https://github.com/pokerstats/Poker-Stats/tree/backfill-no-bounties-rebuys-enabled
		- Would just need to create a new function instead of using `complete_tournament_for_backfill`. That does not take in elim_dict and instead accepts the dict of rebuys.

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





