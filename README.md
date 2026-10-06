# NewsDesk — M07T05 Consolidation Capstone

This consolidation includes the updated M06T08 News Application from
[newsdesk-app](https://github.com/mpapp87/newsdesk-app), source commit
`0f69ebafb03a977c095b55985d06a1d858d530fa`.
It includes editor-managed publishers, unique registration emails, independent
author publication, clearer newsroom actions and article-level subscriptions.

The original local Git history, separate per-script documentation commits,
`docs` and `container` branches, Docker configuration and generated Sphinx HTML
are preserved. The application has been synchronized and the documentation rebuilt.
This preparation does not establish a successful course review of the updated News
Application; obtain that review before requesting the consolidation review.

## Quick start with Docker — independent setup

This route does not require the virtual-environment steps below or a previous clone.

1. Install Git and Docker Desktop (or Docker Engine with the Compose plugin on Linux).
2. Open Docker Desktop and wait until the engine says it is running. On Linux,
   start the Docker service. Keep Docker running throughout these steps.
3. Open a terminal and verify the prerequisites:

```sh
git --version
docker info
docker compose version
```

If `docker info` cannot connect, start Docker and resolve that error before continuing.

4. Clone this repository and enter the new checkout:

```sh
git clone https://github.com/mpapp87/newsdesk-consolidation.git
cd newsdesk-consolidation
cp .env.docker.example .env
```

Windows PowerShell users can use `Copy-Item .env.docker.example .env`.

5. Generate four independent private values by running the following Docker command four
times, then paste them into `DJANGO_SECRET_KEY`, `DB_PASSWORD`, `DB_ROOT_PASSWORD`,
and `APPROVAL_API_KEY` in `.env`:

```sh
docker run --rm python:3.12-slim python -c "import secrets; print(secrets.token_hex(32))"
```

Do not use the placeholder values. `.env` is excluded from Git and Docker builds.

6. Build and start the services. No host Python or manually installed database is needed:

```sh
docker compose up --build -d
```

Open <http://localhost:8000>. MariaDB starts first, then Django applies migrations
and starts the threaded development server. Register Reader, Journalist and Editor accounts at
`/register/`. Editors create publishers through **Publishers**. An optional
maintenance account can be created with `docker compose exec web python manage.py createsuperuser`; it is not required for publishing. Inspect logs with `docker compose logs db web`. Stop using
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

## Application workflow

- Register with a unique email and choose Reader, Journalist or Editor. Email
  matching ignores case and surrounding whitespace. No role gets Django staff access.
- Editors open **Publishers**, create an organization and select its registered
  journalists. They can later rename it and update its journalist membership.
  Each editor manages only their own publishers. Django admin is for maintenance.
- Journalists select one of their publishers when submitting a story, or leave
  Publisher blank for independent work. Publisher submissions require an editor
  belonging to that publisher; unrelated editors cannot manage or approve them.
- Independent work is saved as a private draft. Its author chooses **Publish article**
  when ready, with no editor approval. Editing published content makes it a draft
  again; the independent author republishes, or the publisher editor approves it.
- **Newsroom** has underlined headlines and an explicit **Open article and actions**
  link. Article pages expose the permitted Edit, Delete and Publish actions.
- Readers subscribe through **Subscriptions** or directly on a published article.
  They can follow its journalist, its publisher, or both; notification recipients
  are deduplicated. Article subscription buttons also allow unsubscribing.
- Successful publication does not display a retry button once email processing
  and API logging have completed. **Retry pending delivery** appears only when
  an email remains unsent or the publication log has not been recorded.
- Readers can comment and save published stories. Journalists and editors curate
  newsletters; drafts are excluded from reader-visible newsletter content.

## Review walkthrough

1. Register an Editor and a Journalist in separate browser sessions.
2. As Editor, open Publishers and create an organization with that Journalist.
3. Register a Reader with a different email, and subscribe to the Journalist or
   Publisher through Subscriptions.
4. As Journalist, save a publisher story. As its Editor, open Newsroom and approve
   it. Verify the Reader can now see it and the configured mail backend receives
   the notification. An unrelated Editor must not see the publisher draft.
5. As Journalist, save another story with no Publisher. Open it and click Publish
   article. It should be visible immediately without involving an Editor.
6. As Reader, subscribe or unsubscribe directly on either published article.
7. Attempt registration with an existing email in different letter case; the form
   should reject it without creating another account.

## Manual setup with a virtual environment — independent setup

Use this route instead of Docker. Install Git and Python 3.12, then clone the project:

```sh
git clone https://github.com/mpapp87/newsdesk-consolidation.git
cd newsdesk-consolidation
```

If this repository is already cloned, enter that existing checkout instead.
The following steps install a local database and Python environment.

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

Django 5.2 supports MySQL 8.0.11+ and MariaDB 10.5+. This repository's automated checks run against MariaDB 10.11. See [Django database notes](https://docs.djangoproject.com/en/5.2/ref/databases/).

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

For an existing database, follow **Updating an existing installation** below first. The new email migration stops if duplicate addresses exist: correct those account emails through Django admin maintenance, then rerun migration. It never deletes or merges accounts. Empty legacy emails remain allowed, but registration always requires a unique nonempty address.
For a fresh database:

```bash
python manage.py migrate
python manage.py runserver
```

Open `http://127.0.0.1:8000/`. Use `/register/` to create normal role accounts. Register Editor and Journalist accounts through `/register/`. Editors create publishers and manage journalist membership through **Publishers** in the main navigation. Django admin is only for maintenance; it is not needed for application workflows.

For optional maintenance access, create a superuser with `python manage.py createsuperuser`. Normal publishing does not require this account.

### Updating an existing installation

Back up the old database first. **For an existing installation created with
Django's built-in `auth.User`, run this bridge command before any normal migration:**

```bash
python manage.py migrate accounts 0001 --settings=news_project.legacy_upgrade_settings
python manage.py migrate
```

The bridge records the compatible custom-user migration while `auth.User` remains
active, reusing the existing `auth_user`, group and permission join tables. It does
not copy passwords or renumber accounts. Do not fake migrations or delete tables.
New installations use normal `python manage.py migrate` and do not need the bridge.
A legacy `auth.user` fixture should be imported while using the legacy settings;
then run the bridge and normal migrations. These migrations retain articles, comments and bookmarks. Existing authors receive the Journalist role; other existing accounts receive Reader. Old articles become drafts; independent authors publish their own, while publisher editors approve publisher submissions. Administrators can change profiles explicitly.

Changing database settings does not transfer an existing SQLite file. If it contains data you need, use the **previous version and its SQLite configuration** to export before switching:

```bash
python manage.py dumpdata --natural-foreign --natural-primary --exclude contenttypes --exclude auth.permission --exclude sessions --indent 2 > newsdesk-backup.json
```

Keep this backup private. On the new MySQL installation, migrate only to the old news schema first, import the fixture, then apply the role migration (do this before creating new users):

```bash
python manage.py migrate auth --settings=news_project.legacy_upgrade_settings
python manage.py migrate news 0001 --settings=news_project.legacy_upgrade_settings
python manage.py loaddata /path/to/newsdesk-backup.json --settings=news_project.legacy_upgrade_settings
python manage.py migrate accounts 0001 --settings=news_project.legacy_upgrade_settings
python manage.py migrate
```

If you already migrated before importing an old fixture, assign profiles for the imported users in Django admin. No SQLite export is necessary for a fresh installation.

## Tests

With MariaDB running and the test database grant from the setup above:

```sh
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test --noinput
```

For an isolated unit test run without a database server:

```sh
python manage.py test --settings=news_project.test_settings --noinput
```

The SQLite setting is test-only. Normal operation uses MySQL/MariaDB. Tests cover
publisher creation and ownership, email uniqueness, independent and publisher
publication, access denial, notifications and retry state, subscriptions, API
permissions, newsletters and legacy migrations. External SMTP/HTTP is mocked in
unit tests; test success does not assert real email delivery.

## API

Obtain a token with `POST /api/token/` using your username and password. Send
`Authorization: Token <your-private-token>` in subsequent API requests.
Never commit a token or password.

| Method | Path | Use |
| --- | --- | --- |
| GET / POST | `/api/articles/` | List published stories; journalists create drafts |
| GET | `/api/articles/subscribed/` | Current reader's subscription feed |
| GET / PUT / PATCH / DELETE | `/api/articles/<id>/` | Read or manage permitted stories |
| POST | `/api/articles/<id>/approve/` | Publisher editor approves, or independent author publishes |
| POST | `/api/approved/` | Service-key protected, idempotent publication receipt |
| GET / POST | `/api/newsletters/` | Read or create newsletters |
| GET / PUT / PATCH / DELETE | `/api/newsletters/<id>/` | Read or manage newsletters |
| GET | `/api/publishers/` | Read publisher identities and membership |

The approval URL is retained for existing API clients and applies both publication
rules. Clients cannot spoof author or approval flags when creating/editing articles.
Publication sends queued notifications and calls the receiver through Requests.
Retries do not resend completed reader notifications. A crash after SMTP accepts
mail but before recording its result can still cause a duplicate.

