# NexaRDP Demo Storefront

A small Flask + SQLite demo for manual RDP order handling:
- Public plan storefront
- Customer registration/login and order history
- Admin login and order management
- Admin can change status (Pending / Processing / Completed / Cancelled) and add a customer-facing note
- No automatic provisioning and no payment gateway

## Run locally (Ubuntu)

```bash
sudo apt update
sudo apt install -y python3-venv python3-pip
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
export APP_SECRET="$(python3 -c 'import secrets; print(secrets.token_hex(32))')"
export ADMIN_USERNAME="admin"
export ADMIN_PASSWORD="REPLACE_WITH_A_LONG_UNIQUE_PASSWORD"
gunicorn --bind 127.0.0.1:8000 app:app
```

Visit `http://127.0.0.1:8000` on the server (use an SSH tunnel for local testing), or put it behind Nginx and HTTPS.

## AWS EC2 deployment outline

Do not overwrite an existing site until you confirm its setup. Upload this project to a new directory, install dependencies in a virtual environment, and run Gunicorn behind Nginx with TLS. Keep port 8000 private; expose only 80/443 publicly and restrict SSH to your own IP. Use a long unique `APP_SECRET` and `ADMIN_PASSWORD`; never commit secrets. Back up `rdp_demo.db`. This is a demo starter, not a production-audited commerce system.

Admin: `/admin/login`
Customer: `/register` then `/login`
Plan prices/specs are demo placeholders in `app.py`; change them before showing to customers.

## Important security notes

- No payment collection is implemented. This avoids storing payment screenshots or sensitive payment data in this starter.
- Admin password is supplied through environment variables and hashed in SQLite at startup.
- For production, add CSRF protection, rate limiting, password reset, email verification, audit logging, database backups, HTTPS, and security review before accepting real customer orders.
