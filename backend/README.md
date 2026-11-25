# Backend

Django 5.2 LTS and MySQL implementation of the second, third and fourth deliverables. The templates use the prototype's CSS, fonts and images from `../assets`, and every date is shown in Colombia time (America/Bogota).

## Requirements

- Python 3.12 or newer.
- MySQL 8.0 or newer, or MariaDB 10.5 or newer. It was developed on MariaDB 10.11 and CI runs on MySQL 8.4.
- On Linux and macOS, the client headers that `mysqlclient` compiles against (`pkg-config` and `libmysqlclient-dev` on Debian and Ubuntu). On Windows, pip installs a prebuilt wheel.

## Setup

1. Create the database and a user for it:

   ```sql
   CREATE DATABASE festival_voting CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
   CREATE USER 'festival_app'@'localhost' IDENTIFIED BY 'choose-a-password';
   GRANT ALL PRIVILEGES ON festival_voting.* TO 'festival_app'@'localhost';
   GRANT ALL PRIVILEGES ON test_festival_voting.* TO 'festival_app'@'localhost';
   ```

   The second grant lets Django create and drop the test database.

2. Create a virtual environment and install the dependencies:

   ```
   cd backend
   python -m venv .venv
   .venv\Scripts\activate          # Windows
   source .venv/bin/activate       # Linux and macOS
   pip install -r requirements.txt
   ```

3. Copy `.env.example` to `.env` and set `DJANGO_SECRET_KEY` and `DB_PASSWORD`. This prints a new secret key:

   ```
   python -c "import secrets; print(secrets.token_urlsafe(50))"
   ```

4. Create the tables, load the sample data and create an administrator account:

   ```
   python manage.py migrate
   python manage.py load_demo_data
   python manage.py createsuperuser
   ```

5. Start the server with `python manage.py runserver` and open http://127.0.0.1:8000. The admin is at http://127.0.0.1:8000/admin/ and the site header links to it when you sign in with a staff account.

`load_demo_data` can run again at any time. It updates the same rows and moves the poll dates so that three polls stay open, one upcoming and one closed. Two of the open polls are in Música, so the one-vote-per-category rule can be tried, and the third is in Piloneras y vestuario. The command also casts sample votes in the closed poll and in the two Música polls, a tenth of the prototype's, from 90 accounts without a usable password, so nobody can sign in with them. Running it again adds no new votes. Real voters sign up from the site.

## Environment variables

| Variable | Purpose | Default |
| --- | --- | --- |
| `DJANGO_SECRET_KEY` | Signs sessions and tokens | Required |
| `DJANGO_DEBUG` | `true` for local development | `false` |
| `DJANGO_ALLOWED_HOSTS` | Comma-separated host names the site answers to | `127.0.0.1,localhost` |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | Comma-separated origins allowed to post forms, needed behind a proxy | Empty |
| `DB_NAME`, `DB_USER`, `DB_PASSWORD` | Database credentials | Required |
| `DB_HOST`, `DB_PORT` | Database server | `127.0.0.1`, `3306` |

Settings read these variables from the environment first and then from `backend/.env`. With `DJANGO_DEBUG` off, session and CSRF cookies are only sent over HTTPS, so a local run over plain HTTP needs `DJANGO_DEBUG=true`.

## Tests and checks

```
python manage.py test
pip install ruff
ruff check .
ruff format --check .
```

The tests create `test_festival_voting`, run against it and drop it at the end. ESLint for the two scripts in `static/js` runs from the repository root with `npm run lint`.

## Pages

| URL | Page |
| --- | --- |
| `/` | Current edition, its open polls and its categories |
| `/editions/` | All editions |
| `/editions/<year>/` | Categories of an edition |
| `/categories/` | Redirects to the categories of the current edition |
| `/categories/<id>/` | Polls of a category |
| `/polls/` | Polls of the current edition, filtered with `?status=open`, `upcoming` or `closed` |
| `/polls/<slug>/` | Options and rules of a poll |
| `/polls/<slug>/results/` | Results of a poll, under its visibility setting |
| `/polls/<slug>/vote/` | Step 1: choose an option (signed in) |
| `/polls/<slug>/vote/confirm/` | Step 2: GET shows the choice, POST stores the vote |
| `/votes/<receipt>/` | Step 3: the receipt, visible only to its voter |
| `/my-votes/` | Votes of the signed-in voter |
| `/api/categories/` | Categories, polls and options as JSON (GET only) |
| `/accounts/sign-up/`, `/accounts/sign-in/` | Account forms |
| `/accounts/sign-out/` | Ends the session (POST only) |
| `/admin/` | Django admin |

Drafts, polls in inactive categories and inactive categories return 404, also on the voting and results pages. The voting pages send visitors who are not signed in to the sign-in form and bring them back afterwards.

## Voting rule

A voter gets one vote per category in each edition, whatever the number of polls in the category. The form refuses a vote when the poll is upcoming or closed, when the option belongs to another poll and when the voter already voted in the category. The unique constraint `one_vote_per_voter_category_edition` in MySQL backs the same rule when two requests arrive at once, and the view answers both with the same message.

## Results

Each poll has a results visibility setting. With `live`, anyone sees the count once the poll opens; with `after_close`, once it closes, also when it is closed early; with `hidden`, only staff members see it. Staff members always see the count, with a notice while the public cannot. When the setting does not allow it, the page shows when the results will be published and does not run the count query.

In the admin, the poll list has a vote column, and the poll form shows the votes of each option with links to the results page and to a CSV export (`/admin/festival/poll/<id>/results.csv`). The log entries list, under Administración, shows every change made in the admin and cannot be edited.

## JSON API

`GET /api/categories/` returns the active categories of every edition with their published polls and options. Drafts and inactive categories are left out, dates are in Colombia time and any other method gets a 405. A response from the sample data, trimmed to one poll and two options:

```json
{
  "count": 3,
  "categories": [
    {
      "id": 1,
      "name": "Música",
      "description": "Canciones y agrupaciones de la edición.",
      "edition": {"number": 60, "year": 2027, "name": "Festival de la Leyenda Vallenata"},
      "polls": [
        {
          "slug": "cancion-favorita-del-publico",
          "title": "Canción favorita del público",
          "status": "open",
          "opens_at": "2026-11-02T08:00:00-05:00",
          "closes_at": "2026-11-13T20:00:00-05:00",
          "url": "http://127.0.0.1:8000/polls/cancion-favorita-del-publico/",
          "options": [
            {"id": 1, "name": "Canción A", "detail": "Aire: paseo"},
            {"id": 2, "name": "Canción B", "detail": "Aire: merengue"}
          ]
        }
      ]
    }
  ]
}
```

## Data model

```mermaid
erDiagram
    EDITION ||--o{ CATEGORY : has
    CATEGORY ||--o{ POLL : groups
    POLL ||--o{ OPTION : offers
    USER ||--o{ VOTE : casts
    OPTION ||--o{ VOTE : receives
    CATEGORY ||--o{ VOTE : "counts in"
    EDITION ||--o{ VOTE : "counts in"
    EDITION {
        int number
        int year
        date starts_on
        date ends_on
    }
    CATEGORY {
        string name
        int position
        bool is_active
    }
    POLL {
        string title
        string slug
        datetime opens_at
        datetime closes_at
        bool is_published
        bool closed_early
        string results_visibility
    }
    OPTION {
        string name
        string detail
        int position
    }
    VOTE {
        string receipt
        datetime cast_at
    }
```

The user model (`accounts.User`) replaces Django's default one: it has no username, signs in with a unique email and stores `privacy_accepted_at`, the moment the person accepted the personal data policy when signing up.

A vote keeps its edition and category next to the option, copied from the option when it is cast, because the unique constraint on voter, edition and category needs those columns in the same table. Its foreign keys use `PROTECT`, so nothing a vote depends on can be deleted.

## Layout

```
config/       Settings, URLs and the WSGI entry point
accounts/     User model and manager, forms, the sign-in limit, views and admin
festival/     Models, admin, public, voting and results views, the JSON API, the CSV export, template filters and the load_demo_data command
templates/    Base layout, public pages, account forms, the 404 page and the admin override
static/js/    Mobile menu, message dismissal and page transition handling
```
