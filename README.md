# NewsDesk — M07T05 Consolidation Capstone

This consolidation is based on the **M06T08 News Application**, which Michael
confirmed had passed review on 6 October 2026. The earlier sticky-notes additions
are not the basis of this project. The application was imported from the coursework
repository, then enhanced through the required local `docs` and `container` branches.
Both branches are retained and merged into `main`; each of the three documented
Python scripts has its own commit on `docs`.

## Quick start with Docker

Install Docker Desktop (or Docker Engine with Compose on Linux), then:

```sh
git clone https://github.com/mpapp87/newsdesk-consolidation.git
cd newsdesk-consolidation
cp .env.docker.example .env
```

Windows PowerShell users can use `Copy-Item .env.docker.example .env`.
Generate four independent private values by running the following command four
times, then paste them into `DJANGO_SECRET_KEY`, `DB_PASSWORD`, `DB_ROOT_PASSWORD`,
and `APPROVAL_API_KEY` in `.env`:

```sh
python -c "import secrets; print(secrets.token_hex(32))"
```

Use `python3` or `py` if that is your local Python command. If Python is not
installed, each value can instead be generated with:

```sh
docker run --rm python:3.12-slim python -c "import secrets; print(secrets.token_hex(32))"
```

Do not use the placeholder values. `.env` is excluded from Git and Docker builds.

```sh
docker compose up --build -d
docker compose exec web python manage.py createsuperuser
```

Open <http://localhost:8000>. MariaDB starts first, then Django applies migrations
and starts the threaded development server. Register normal role accounts at
`/register/`. Inspect logs with `docker compose logs db web`. Stop using
`docker compose down`; the named database volume persists. Do not add `-v` unless
intentionally deleting the database. If you change database passwords after the
first run, update the database account as well; changing `.env` alone does not
change an existing MariaDB volume's credentials.

The default Docker configuration prints email in the container logs. It does not
send email. To deliver real notifications, obtain SMTP settings from your provider,
edit the email variables in `.env`, select the SMTP backend, and recreate the web
service with `docker compose up -d --force-recreate web`. Use a new article when
testing real delivery. The approval callback works internally at
`http://127.0.0.1:8000/api/approved/` with your private service key.

This is a local development demonstration, bound to localhost, using debug mode.
A public deployment requires a production server, HTTPS, static-file hosting,
restricted host names, and verified editor accounts.

## Consolidation documentation and verification

Open `docs/_build/html/index.html` from a downloaded checkout to read the generated
Sphinx guide and API reference. Built HTML is committed as explicitly required by
M07T05; build caches, virtual environments, secrets and database dumps are ignored.
To rebuild, activate your virtual environment, then run:

```sh
python -m pip install -r requirements-docs.txt
python -m sphinx -W --keep-going -b html docs docs/_build/html
```

The `docs` branch includes individual commits for `news/roles.py`,
`news/services.py`, and `accounts/models.py`, followed by Sphinx source and HTML.
The `container` branch starts from the baseline and adds Docker/MariaDB files.
The Git history records separate merges of both branches.

The GitHub Actions workflow `.github/workflows/container-check.yml` builds this
checkout on a separate Ubuntu machine, starts MariaDB and Django, checks the HTTP
response and migrations, runs the test suite against MariaDB, and builds Sphinx.
It generates disposable secrets at runtime and does not send real email.
See the repository's Actions tab for the actual run result.

The native virtual-environment setup and full application guide follow below.

A Django news application with reader, journalist and editor roles, editorial approval, newsletters, subscriptions, token-authenticated APIs and email notifications. It uses **MySQL or MariaDB** for normal operation.

The full [requirements and design checklist](docs/requirements.md) maps this submission to the task brief.

## What changed for resubmission

- News templates live in `news/templates/news/`. Shared layout and registration/login templates remain in the project-level `templates/` directory.
- Every project class, method and function has a docstring, following [PEP 257](https://peps.python.org/pep-0257/). Sphinx extracts the application reference from these docstrings.
- MySQL/MariaDB replaces SQLite in the normal settings. `mysqlclient` is a required dependency.
- SMTP settings come from environment variables. Approved articles email subscribed readers, with a retry path for delivery failures.
- Registration requires a role, synchronizes Django permission groups, and enforces permissions in HTML and API views.
- A compatible custom User preserves existing accounts. Newsletters, all required article API endpoints, DRF serializers and the Requests-based approval API integration are included.

## Roles and publication workflow

| Role | Permissions |
| --- | --- |
| Reader | Read approved articles and newsletters, comment, save stories, subscribe to journalists and publishers. |
| Journalist | Submit articles, view own drafts, edit/delete own articles. Create/edit/delete own newsletters. Cannot approve articles or edit another journalist's work. |
| Editor | View all submissions, edit/delete articles, approve publication and retry failed email deliveries. Create newsletters and manage all newsletters. Cannot submit articles as a journalist. |

All visitors can browse approved articles and search external headlines. Drafts are visible only to their journalist and editors. Editing any approved story returns it to the review queue. Readers cannot fetch draft details, bookmark them or comment on them by posting a URL directly.

**Publishers are organizations, not login accounts.** A Django administrator creates publishers and assigns journalist and editor members through `/admin/`. A journalist can select only a publisher they belong to, or leave it blank to write independently. Editors review all publishers and independent submissions in this capstone.

For the assessed registration workflow, users can choose any of the three roles, including editor. This does not grant Django staff or superuser status. A public production deployment should add editorial staff verification before allowing self-selected editor privileges.

### Try the complete journey

1. Register separate Reader, Journalist and Editor accounts (use different browser sessions or log out between them).
2. As a reader, open **Subscriptions**, choose a journalist and/or publisher, and save. Supply a working email when registering.
3. As a journalist, choose **Submit article**. The submission appears in **Newsroom**, but not the public feed.
4. As an editor, open **Newsroom**, open the draft, then choose **Approve and notify readers**.
5. The article appears publicly. Each matching reader receives a separate email containing the summary and article link. Following both its author and publisher does not duplicate that reader's notification.
6. If SMTP fails, approval remains saved and the page reports the failure. Fix SMTP configuration, restart the app, then choose **Retry email/API delivery** on that article as an editor.

Notifications are tracked once per article and reader; reapproval after editing does not resend to readers already notified. Unsubscribed or inactive readers are skipped on retry. As with ordinary SMTP delivery, a process crash after mail is accepted but before its database update can result in a duplicate; this is not an exactly-once mail transport.

## Get this project

Clone the public consolidation repository:

```bash
git clone https://github.com/mpapp87/newsdesk-consolidation.git
cd newsdesk-consolidation
```

For a GitHub ZIP download, extract it and open the directory containing `manage.py`.

## Setup: Python and dependencies

Use Python 3.12 or later supported by Django 5.2. Open a terminal **in this task's folder**, beside `manage.py`.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
```

On Windows, use `py -3.12 -m venv .venv` and `.venv\Scripts\activate` instead. Avoid running the macOS system Python or launching `manage.py` without a management command.

Install MySQL client build prerequisites **before** installing requirements:

- macOS with Homebrew: `brew install mariadb pkg-config`, then `brew services start mariadb`. Set `export PKG_CONFIG_PATH="$(brew --prefix mariadb)/lib/pkgconfig"` before installing Python dependencies if pkg-config cannot find the client. If using only `mysql-client`, set `PKG_CONFIG_PATH="$(brew --prefix mysql-client)/lib/pkgconfig"` when building `mysqlclient`.
- Ubuntu/Debian: `sudo apt update`, then `sudo apt install mariadb-server libmariadb-dev libmariadb-dev-compat build-essential pkg-config python3-dev` and `sudo systemctl start mariadb`.
- Windows: install MariaDB Server (or MySQL Server) and use a Python version with a matching `mysqlclient` wheel. Consult the [mysqlclient installation guide](https://github.com/PyMySQL/mysqlclient) if a native build is needed.

```bash
python -m pip install -r requirements.txt
```

Django 5.2 supports MySQL 8.0.11+ and MariaDB 10.5+. This consolidation repository's automated checks run against MariaDB 10.11. See [Django database notes](https://docs.djangoproject.com/en/5.2/ref/databases/).

## Create the database

Log into MySQL/MariaDB as its administrator, for example `mariadb -u root -p` (or `mysql -u root -p` with MySQL), and run:

```sql
CREATE DATABASE newsdesk CHARACTER SET utf8mb4;
CREATE USER 'newsdesk'@'localhost' IDENTIFIED BY 'replace-with-a-local-password';
GRANT ALL PRIVILEGES ON newsdesk.* TO 'newsdesk'@'localhost';
```

For tests, also grant access to the separate test database:

```sql
GRANT ALL PRIVILEGES ON test_newsdesk.* TO 'newsdesk'@'localhost';
```

Exit the SQL client with `EXIT;`. Create a private `.env` beside `manage.py`.
On macOS/Linux:

```bash
cp -n .env.example .env
open -e .env  # macOS; on Linux use nano .env
```

On Windows PowerShell:

```powershell
if (!(Test-Path .env)) { Copy-Item .env.example .env }
notepad .env
```

Replace `DB_PASSWORD` with the password used in CREATE USER, and set DB_NAME,
DB_USER, DB_HOST and DB_PORT to the matching connection values. Save the file.
The normal application always uses MySQL/MariaDB; there is no SQLite fallback.
If you prefer terminal variables, the equivalent is:

```bash
export DB_NAME='newsdesk'
export DB_USER='newsdesk'
export DB_PASSWORD='replace-with-a-local-password'
export DB_HOST='127.0.0.1'
export DB_PORT='3306'
```

For a remote database, configure the database account's allowed client host appropriately. In PowerShell the equivalent is `$env:DB_NAME = 'newsdesk'`, and so on. The application loads `.env` with python-dotenv. Existing process variables take precedence. Never commit real credentials. Restart the server after editing `.env`.

## Configure email

Edit the email lines in `.env` with the SMTP settings supplied by your provider.
Use the setting names shown below without the `export ` prefix in that file.
Alternatively, set them in the terminal:

```bash
export EMAIL_HOST='smtp.your-provider.example'
export EMAIL_PORT='587'
export EMAIL_HOST_USER='your-smtp-user'
export EMAIL_HOST_PASSWORD='your-smtp-password-or-app-password'
export EMAIL_USE_TLS='true'
export EMAIL_USE_SSL='false'
export DEFAULT_FROM_EMAIL='NewsDesk <your-verified-sender@example.com>'
export SITE_URL='http://127.0.0.1:8000'
```

Use a verified sender address. For implicit TLS on port 465, set `EMAIL_USE_SSL=true` and `EMAIL_USE_TLS=false`; do not enable both. `SITE_URL` is the reader-accessible base URL included in emails. SMTP is enabled by default, with a 10-second timeout.

For a local demonstration without SMTP, explicitly choose:

```bash
export EMAIL_BACKEND='django.core.mail.backends.console.EmailBackend'
```

This prints messages in the terminal **instead of delivering them**. Such notifications are marked sent by the console backend; use a new article to test real SMTP after switching back. Unset `EMAIL_BACKEND` to restore SMTP. Tests use an in-memory email backend and send no real messages.

## Configure the approval API integration

Generate two distinct secrets by running this command twice:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Put one value in `DJANGO_SECRET_KEY` and the other in `APPROVAL_API_KEY` in `.env`.
Both are local secrets; do not upload them. For local use, keep:

```dotenv
SITE_URL=http://127.0.0.1:8000
APPROVAL_API_URL=http://127.0.0.1:8000/api/approved/
```

Run Django with its normal threaded development server (do not use `--nothreading`).
An approval makes a real `requests.post` to that endpoint with a separate service
key. The receiver validates approval state and records one receipt per article.
A failed API call does not undo publication; repeat the approval action after fixing
configuration. Production deployments need enough workers to handle the callback
and HTTPS for both external clients and the approval receiver.

## Apply migrations and start

For an existing database, follow **Updating an existing installation** below first.
For a fresh database:

```bash
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Open `http://127.0.0.1:8000/`. Use `/register/` to create normal role accounts. The superuser administers publishers and profiles at `/admin/`; it does not automatically act as an editor in the newsroom. If needed, add an Editor profile for that account in administration.

### Updating an existing installation

Back up the old database first. **For an existing installation created with
Django's built-in `auth.User`, run this bridge command before any normal migration:**

```bash
python manage.py migrate accounts --settings=news_project.legacy_upgrade_settings
python manage.py migrate
```

The bridge records the compatible custom-user migration while `auth.User` remains
active, reusing the existing `auth_user`, group and permission join tables. It does
not copy passwords or renumber accounts. Do not fake migrations or delete tables.
New installations use normal `python manage.py migrate` and do not need the bridge.
A legacy `auth.user` fixture should be imported while using the legacy settings;
then run the bridge and normal migrations. These migrations retain articles, comments and bookmarks. Existing authors receive the Journalist role; other existing accounts receive Reader. Old articles enter the approval queue so they must be reviewed by an editor before appearing publicly. Administrators can change profiles explicitly.

Changing database settings does not transfer an existing SQLite file. If it contains data you need, use the **previous version and its SQLite configuration** to export before switching:

```bash
python manage.py dumpdata --natural-foreign --natural-primary --exclude contenttypes --exclude auth.permission --exclude sessions --indent 2 > newsdesk-backup.json
```

Keep this backup private. On the new MySQL installation, migrate only to the old news schema first, import the fixture, then apply the role migration (do this before creating new users):

```bash
python manage.py migrate auth --settings=news_project.legacy_upgrade_settings
python manage.py migrate news 0001 --settings=news_project.legacy_upgrade_settings
python manage.py loaddata /path/to/newsdesk-backup.json --settings=news_project.legacy_upgrade_settings
python manage.py migrate accounts --settings=news_project.legacy_upgrade_settings
python manage.py migrate
```

If you already migrated before importing an old fixture, assign profiles for the imported users in Django admin. No SQLite export is necessary for a fresh installation.

## Tests and documentation

With MySQL/MariaDB running and test database privileges granted:

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test
```

A separate, explicit test-only SQLite configuration is available for fast unit tests on machines without a database server:

```bash
python manage.py test --settings=news_project.test_settings
```

This does not change normal startup or replace the MySQL/MariaDB assessment setup. Tests also cover token authentication, API role permissions, newsletter CRUD, subscription feed isolation, approval POST authentication and idempotency. Tests cover registration for all roles, ownership and access denial, draft visibility, approval, subscriptions, private deduplicated notifications, SMTP failures/retries, template placement, browsing, comments, bookmarks and the mocked external API.

Build the Sphinx reference:

```bash
python -m pip install -r requirements-docs.txt
python -m sphinx -W --keep-going -b html docs docs/_build/html
```

Open `docs/_build/html/index.html`. The documentation configuration initializes Django with test settings to import models without a live database.

## Structure and routes

```text
accounts/               compatible custom User and its bridge migration
news_project/           project settings and root URLs
news/                   models, forms, role checks, views, services, tests
news/migrations/        schema and existing-account role migrations
news/templates/news/    application-owned news templates
news/static/news/       custom stylesheet
templates/base.html     shared site layout
templates/registration/ login and registration templates
docs/                   Sphinx configuration and reference source
```

Main routes: `/`, `/register/`, `/accounts/login/`, `/dashboard/`, `/article/new/`, `/article/<id>/`, `/subscriptions/`, `/saved/`, `/external/`, `/admin/`. API routes and newsletter routes are listed below. State-changing approval, comment, bookmark and logout actions require POST and CSRF tokens. The external headlines service uses the Hacker News Algolia API with a timeout and graceful error handling.

For deployment, set a private `DJANGO_SECRET_KEY`, set `DJANGO_DEBUG=false`, configure `DJANGO_ALLOWED_HOSTS`, use HTTPS, and serve collected static files with an appropriate server. Never commit databases, email passwords or exported account fixtures.


## REST API walkthrough

Register accounts in the browser first. API clients must obtain a token using
`POST /api/token/` with `username` and `password`. On macOS/Linux, this command
prompts privately for the password and prints the returned token (keep it private):

```bash
read -r -p "Username: " NEWS_USER
read -r -s -p "Password: " NEWS_PASSWORD; echo
curl -sS -X POST http://127.0.0.1:8000/api/token/ --data-urlencode "username=$NEWS_USER" --data-urlencode "password=$NEWS_PASSWORD"
unset NEWS_PASSWORD
```

The above prompts use Bash (`bash` first if needed). Paste the returned token into
an environment variable without saving it to your repository:

```bash
read -r -s -p "API token: " NEWS_TOKEN; echo
curl -H "Authorization: Token $NEWS_TOKEN" http://127.0.0.1:8000/api/articles/
```

| Method | Endpoint | Role / behavior |
| --- | --- | --- |
| GET / POST | `/api/articles/` | All roles list approved articles; only journalists create drafts. |
| GET | `/api/articles/subscribed/` | Current reader's followed journalists/publishers, approved only. |
| GET / PUT / PATCH / DELETE | `/api/articles/<id>/` | Read visible stories; owning journalist/editor edits or deletes. |
| POST | `/api/articles/<id>/approve/` | Editors only; email subscribers and log via Requests. |
| POST | `/api/approved/` | Service key required; idempotent receipt for an approved article. |
| GET / POST | `/api/newsletters/` | Read newsletters; journalists/editors create. |
| GET / PUT / PATCH / DELETE | `/api/newsletters/<id>/` | Read; owning journalist/editor manages. |
| GET | `/api/publishers/` | Authenticated roles retrieve organizations and memberships. |

Create a draft using a journalist token:

```bash
curl -X POST http://127.0.0.1:8000/api/articles/ -H "Authorization: Token $NEWS_TOKEN" -H 'Content-Type: application/json' -d '{"title":"First report","summary":"Short overview","content":"Full report","category":"world"}'
```

Use the returned `id` in detail/update/delete/approval URLs. A reader POST returns
403; missing or invalid tokens return 401; invalid content returns 400. Submitted
`author` and `approved` values cannot grant ownership or approval. PUT/PATCH returns
an approved article to draft. Readers still have access to all approved stories via
`/api/articles/`; only the subscribed endpoint filters to their own follows.

Newsletters can also be created and managed through **Newsletters** in the navbar.
Choose approved articles and save. If an article returns to draft later, it disappears
from the newsletter's reader view until approved again.

## Final manual verification

Use a working database and reader email. Subscribe a reader, submit as a journalist,
and approve as an editor. Check the reader inbox/spam folder and verify that approval
reports successful API logging (`api_logged: true` for API approval). Repeat approval:
existing reader notifications and API receipts must not duplicate. Test a newsletter
as a reader and confirm that reader edit/create requests are denied. Automated tests
mock SMTP and HTTP; they do not claim that a real provider delivered a message.
