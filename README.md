# IT Service Desk — role-based version

A Flask + SQLite academic project for ticket tracking with server-enforced role permissions.

## Roles and permissions

- **Employee:** create tickets, see/search/filter only tickets they submitted. New tickets are assigned Medium priority. Employees cannot update status/priority or delete tickets.
- **Support agent:** see/search/filter all tickets, create tickets, update ticket status and priority. Cannot create accounts or delete tickets.
- **Administrator:** all ticket access, delete tickets, create employee/agent accounts, and activate/deactivate non-admin accounts.
- Account creation is restricted to the administrator. Public registration is disabled.

All POST forms use CSRF protection. Passwords are stored as password hashes, not plaintext. Access checks are enforced in Flask routes, not only by hiding interface controls.

## Run locally (Windows)

Install Python 3.11+ and run these commands in this project folder:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
$env:SECRET_KEY = python -c "import secrets; print(secrets.token_hex(32))"
$env:ADMIN_USERNAME = "admin"
$env:ADMIN_PASSWORD = "Use-A-Unique-Password-Of-At-Least-12-Chars"
$env:ADMIN_FULL_NAME = "Project Administrator"
python app.py
```

Then open http://127.0.0.1:5000. The first launch creates the initial admin account only when `ADMIN_USERNAME` and `ADMIN_PASSWORD` are set and no admin account exists. Use a unique password; do not reuse the example above. If PowerShell rejects the activation script, you can install/run with `python -m pip install -r requirements.txt` and `python app.py` without activating the virtual environment.

## Deploy to Render

1. Commit and push these updated project files to your GitHub repository.
2. In Render, open your existing Web Service and set the **Build Command** to `pip install -r requirements.txt` and **Start Command** to `gunicorn app:app`.
3. In **Environment**, add these variables before signing in:
   - `SECRET_KEY`: a long random secret (generate one locally with `python -c "import secrets; print(secrets.token_hex(32))"`).
   - `ADMIN_USERNAME`: your chosen admin username, e.g. `admin`.
   - `ADMIN_PASSWORD`: a unique password of at least 12 characters.
   - `ADMIN_FULL_NAME`: your display name.
   - `COOKIE_SECURE`: `true` on the HTTPS Render website.
4. Deploy. Visit `/login` and sign in using the admin credentials from the environment variables. Then use **Manage accounts** to create employee and support-agent accounts.
5. Keep `SECRET_KEY` stable between deployments. Never commit credentials or secrets to GitHub.

### Database persistence warning

SQLite is stored at `service_desk.db` by default. On hosting platforms with ephemeral filesystems, this database may be lost on redeploy/restart. For reliable production persistence, attach a persistent disk and set `DATABASE_PATH` to a path on that disk, or migrate to a managed PostgreSQL database. A persistent disk may require a paid hosting plan; verify the current Render plan capabilities before relying on it. Existing old tickets are retained by the schema migration when the same database file remains available, but old tickets without a user owner are visible only to admin/agent accounts.

## Security scope and limitations

This is a student demonstration, not a hardened production service. Use HTTPS, a strong stable `SECRET_KEY`, unique strong passwords, restricted deployment access, and persistent storage. There is no password reset, email verification, rate limiting, audit log, MFA, or user self-service password change yet. Admin account bootstrap uses environment variables only when no admin exists. If you change the bootstrap variables after the first admin has been created, that will not change the existing admin password.
