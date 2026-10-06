NewsDesk user guide
======================

This M07T05 consolidation includes the corrected M06T08 News Application from
``mpapp87/newsdesk-app`` at commit ``0f69ebafb03a977c095b55985d06a1d858d530fa``.
The updated application still needs a successful course review before requesting
consolidation review. These instructions describe the implemented behavior.

Docker installation: complete independent route
--------------------------------------------------

1. Install Git and Docker Desktop, or Docker Engine with Compose on Linux.
2. Open Docker Desktop and wait for the engine to run. On Linux, start Docker.
3. Verify that Docker is available before proceeding::

      git --version
      docker info
      docker compose version

4. Clone the project and prepare configuration::

      git clone https://github.com/mpapp87/newsdesk-consolidation.git
      cd newsdesk-consolidation
      cp .env.docker.example .env

   In PowerShell use ``Copy-Item .env.docker.example .env``.
5. Run this command four times to generate four different private values::

      docker run --rm python:3.12-slim python -c "import secrets; print(secrets.token_hex(32))"

   Put them in ``DJANGO_SECRET_KEY``, ``DB_PASSWORD``, ``DB_ROOT_PASSWORD`` and
   ``APPROVAL_API_KEY`` in ``.env``. Never commit this file or reuse placeholders.
6. Build and start the services::

      docker compose up --build -d

Visit http://localhost:8000. This route requires no host Python installation,
manual database installation or virtual environment. MariaDB becomes healthy
before Django applies migrations and starts the threaded development server.
Register normal role accounts in the app. Optional maintenance access can be
created with ``docker compose exec web python manage.py createsuperuser``.

Data persists in a named Docker volume. Stop with ``docker compose down``;
do not add ``-v`` unless intentionally deleting that database. Changing ``.env``
passwords does not change accounts in an existing database volume.

Manual installation: separate alternative
--------------------------------------------

Install Git, Python 3.12 and MariaDB/MySQL with client development libraries.
Start the database service. From a new terminal, clone the application::

   git clone https://github.com/mpapp87/newsdesk-consolidation.git
   cd newsdesk-consolidation
   python3.12 -m venv .venv
   source .venv/bin/activate
   python -m pip install -r requirements.txt

On Windows use ``py -3.12 -m venv .venv`` and ``.venv\Scripts\activate``.
Create the ``newsdesk`` database and a dedicated database user, using the
platform-specific instructions and SQL grants in the root README. Copy
``.env.example`` to ``.env`` and provide private database, Django, SMTP and
approval-service settings. Then run::

   python manage.py migrate
   python manage.py runserver

Visit http://127.0.0.1:8000. This alternative does not use Docker. The README also
explains the staged upgrade for legacy databases using Django's original user
model. Back up existing data first. If duplicate legacy emails block migration,
correct those account addresses through maintenance and retry. No accounts or
subscriptions are automatically deleted or merged.

Accounts and publishers
--------------------------

Register Reader, Journalist and Editor accounts with distinct email addresses.
Email matching ignores case and surrounding whitespace; database uniqueness
also protects simultaneous registration requests. Legacy accounts with no email
remain supported, but new public registrations require an email.

Editors open **Publishers** in the navigation, create an organization and select
registered journalists. They can rename their organization and update membership
there. A creating editor automatically belongs to the publisher. Other editors
cannot take over the organization. Django admin is reserved for maintenance;
it is not required to create publishers or publish articles.

Publishing a story
---------------------

For a publisher story:

1. An editor creates the publisher and assigns registered journalists.
2. A journalist selects that publisher and saves an article.
3. An editor belonging to that publisher opens **Newsroom**, opens the article
   using its underlined headline or action link, and chooses **Approve and publish**.
4. Readers can read, save, comment and subscribe directly on the article.

For independent work:

1. A journalist leaves Publisher blank and saves a private draft.
2. After editing, its author chooses **Publish article**.
3. The article becomes public without an editor's approval.

Other journalists and editors cannot publish an independent author's draft.
Editing published content returns it to draft: an independent author republishes
it, while a publisher story returns for that publisher's editor approval.

Subscriptions and delivery status
------------------------------------

Readers follow journalists or publishers using **Subscriptions** or the buttons
on a published article. Article buttons also allow unsubscribing. These operations
change only the chosen source and preserve other subscriptions. Following both
sources does not duplicate a reader's tracked publication notification.

Publication commits before external delivery. **Retry pending delivery** appears
only if an email is still unsent or the publication receipt has not been recorded.
Completed notifications are not resent on retry. When both processing steps are
complete, the page says **No retry is needed** and hides the retry button.

Docker uses console email by default. Read messages in ``docker compose logs web``;
no real email is delivered in this mode. For real delivery, configure an SMTP
provider in ``.env`` and select ``django.core.mail.backends.smtp.EmailBackend``.
Recreate the web service with ``docker compose up -d --force-recreate web``.
Use a new article because console-processed notifications are already marked sent.

Newsletters and API clients
------------------------------

Journalists manage their own newsletters; editors can curate newsletters. Only
published articles appear in reader-visible newsletters. Obtain an API token
through ``POST /api/token/`` and send ``Authorization: Token <your-token>``.
Tokens and passwords are private.

``/api/articles/`` lists published articles and allows journalists to create drafts.
``/api/articles/subscribed/`` returns the current reader's subscription feed.
``POST /api/articles/<id>/approve/`` applies the same publication rules as HTML:
assigned publisher editors approve publisher stories; independent authors publish
their own stories. The existing URL is retained for client compatibility. The
README lists all endpoints. The server rejects forged authorship and approval flags.

Verification and troubleshooting
-----------------------------------

The committed GitHub workflow builds Docker on a separate Ubuntu machine, runs
HTTP and migration checks, runs the tests against MariaDB, and builds Sphinx with
warnings treated as errors. Tests cover access boundaries, duplicate registration,
safe migrations, publisher management, independent publishing and subscriptions.
They mock external delivery and do not prove receipt by a real email provider.

Use ``docker compose logs db web`` if startup fails. Ensure Docker is running,
port 8000 is free, and the configured passwords match the database accounts.
Run ``docker compose exec web python manage.py check`` for Django checks.
For fast isolated tests::

   docker compose exec web python manage.py test --settings=news_project.test_settings --noinput

For native MariaDB tests, grant the test database privilege described in the README
and run ``python manage.py test --noinput`` in the activated environment.
Normal operation always uses MySQL/MariaDB; SQLite settings are test-only.

Rebuild documentation in the activated native environment::

   python -m pip install -r requirements-docs.txt
   python -m sphinx -W --keep-going -b html docs docs/_build/html

Open ``docs/_build/html/index.html``. Generated HTML is committed for reviewers;
virtual environments, secrets, database dumps and build caches are excluded.

Deployment limits
--------------------

This is a local coursework demonstration using Django's development server.
Public deployment needs a production server, HTTPS, proper static-file serving,
restricted hosts and verified editor registration. Never publish private settings
or account data. An SMTP crash after acceptance but before recording success can
still cause a duplicate; notification tracking is not an exactly-once transport.
