# Task 20 requirements and design

## Functional requirements

The application registers readers, journalists and editors; assigns Django groups;
protects drafts; supports article and newsletter CRUD; stores publisher memberships;
and lets readers subscribe to publishers and journalists. Editor approval queues
private subscriber email and posts the article ID to `/api/approved/` with Requests.
Token-authenticated clients can list approved articles, retrieve one, retrieve their
own subscriptions, create as journalists, and update/delete as owners or editors.

## Data design and normalization

`accounts.User` extends AbstractUser and retains the legacy `auth_user` table and
passwords. A one-to-one Profile stores one role and M2M subscription joins, avoiding
repeated subscriber lists. Role-specific user properties expose these relationships
or None when inapplicable; empty M2M joins represent no subscription in SQL.
Article.author and Newsletter.author are reverse user relationships. Publisher has
separate journalist and editor joins because a person may serve several publishers.
Article.body is exposed as `content`, and published_at as `created_at` in the API,
preserving existing database data. Newsletter.articles is a normalized M2M join.
PublicationEmail records delivery per article/reader; ApprovedArticleLog records
one idempotent API receipt per article. Foreign keys preserve referential integrity.

## Access and UI design

A shared navigation bar exposes Home, Newsletters, role-appropriate Newsroom or
Subscriptions, and logout. Journalists submit drafts; editors approve from the
newsroom. Readers see only approved article content, including inside newsletters.
Forms validate publisher membership. Role checks occur on the server as well as in
menus. Publisher organizations are created by an administrator; they are not a
fourth public login role. Editors can review across the application, while publisher
editor membership records their organizational affiliations.

## Nonfunctional requirements

Normal startup uses MySQL/MariaDB with UTF-8 and strict SQL mode. Django validates
passwords, escapes templates, enforces CSRF on session writes and validates API
input with DRF serializers. Request timeouts and explicit retry paths prevent
unavailable SMTP/API services from rolling back approved articles. Credentials are
loaded from an ignored .env file. Sphinx builds from documented Python classes and
functions. Automated tests cover successful and denied role actions, subscriptions,
newsletters, approval side effects and preserved data during migrations.

## Feedback checklist

- News templates: `news/templates/news/`; registration remains project-level.
- Docstrings: all added classes/functions/methods, including migration operations.
- Database: MySQL/MariaDB is the normal backend; separate SQLite settings are test-only.
- Email: SMTP configuration, subscribed reader notifications, failures and retries.
- Registration: required Reader/Journalist/Editor role, synchronized Django groups.
- Additional brief requirements: newsletters, custom user, token APIs, four DRF
  serializers, Requests POST to the local approval API, automated API tests.

External SMTP credentials and a running database/server are local setup requirements.
Mocked tests do not prove delivery to a real inbox. See the README for manual checks.
