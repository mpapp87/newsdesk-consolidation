NewsDesk user guide
===================

NewsDesk is the passed M06T08 News Application, consolidated with Sphinx
documentation and a Docker development environment for M07T05.

Installation
------------

For a native installation, use Python 3.12, create a virtual environment and
install ``requirements.txt``. Install MySQL/MariaDB and its client development
libraries first. Copy ``.env.example`` to ``.env`` and provide private database,
Django, SMTP and approval service settings. Apply migrations and start Django::

   python manage.py migrate
   python manage.py createsuperuser
   python manage.py runserver

The root README contains platform-specific database setup and commands.

For Docker, copy ``.env.docker.example`` to ``.env`` and replace each placeholder
with a private generated secret. Start the web and MariaDB services::

   docker compose up --build -d
   docker compose exec web python manage.py createsuperuser

Visit http://localhost:8000. Docker Compose waits for MariaDB, then the web
container applies migrations before starting the development server. Database
data persists in a named Docker volume. Stop with ``docker compose down``;
do not add ``-v`` unless intentionally deleting that database.

Publishing a story
------------------

1. Register separate Reader, Journalist and Editor accounts.
2. As a reader, subscribe to a journalist or publisher under Subscriptions.
3. As a journalist, submit an article. It remains a draft in the Newsroom.
4. As an editor, open the draft and approve it.
5. Readers can now read, save, and comment on the published story.

The Docker demonstration uses console email by default. Read messages in
``docker compose logs web``; no real email is delivered in this mode.
To test real delivery, configure an SMTP provider in ``.env`` and select
``django.core.mail.backends.smtp.EmailBackend``. Restart the web service.
Use a new article because console-delivered notifications are marked sent.

Publishers and newsletters
--------------------------

A Django administrator creates publishers and assigns journalist/editor members
in ``/admin/``. Independent journalists can leave the publisher blank. Journalists
manage their own newsletters, while editors can manage all newsletters. Only
approved articles appear to readers.

API clients
-----------

Obtain a token through ``POST /api/token/`` and send it as
``Authorization: Token <your-token>``. Tokens and passwords are private.
``/api/articles/`` lists visible articles; journalists can create drafts.
``/api/articles/subscribed/`` is the reader's subscription feed. Editors can
approve through ``POST /api/articles/<id>/approve/``. The README documents
the full endpoint list and role restrictions.

Verification and troubleshooting
--------------------------------

Run ``docker compose exec web python manage.py check`` to check configuration.
Run ``docker compose logs db web`` if startup fails. Ensure local port 8000 is
free, Docker is running, and the generated database passwords match.

Fast unit tests use explicit test-only SQLite settings::

   python manage.py test --settings=news_project.test_settings

Normal operation always uses MySQL/MariaDB. Tests against a real database need
permission to create the ``test_newsdesk`` database. See the README for grants.

Build these docs with ``pip install -r requirements-docs.txt`` followed by::

   python -m sphinx -W --keep-going -b html docs docs/_build/html

Open ``docs/_build/html/index.html``. The committed HTML is included for reviewers;
virtual environments, secrets, database dumps, and build caches are excluded.

Deployment limits
-----------------

The supplied Docker setup is a local coursework demonstration using Django's
development server and debug mode. Internet deployment requires a production
server, HTTPS, proper static-file serving, restricted host names and verified
editor registration. Never publish real ``.env`` files or account data.
