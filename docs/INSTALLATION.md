# Installation Guide

Target platform: **Ubuntu Server 24.04 LTS**, running inside Oracle
VirtualBox (preferred) or VMware Workstation.

## 1. Provision the VM

1. Create a new VM (2 vCPU / 4 GB RAM / 20 GB disk is plenty for the demo).
2. Install Ubuntu Server 24.04 LTS from the official ISO.
3. Enable OpenSSH during install (or `sudo apt install openssh-server`
   afterward) so you can work from your host machine's terminal.
4. `sudo apt update && sudo apt upgrade -y`

## 2. Get the code onto the VM

```bash
sudo apt install -y git
git clone https://github.com/xyrusvdominguez4013-png/image-storage-demo.git
cd image-storage-demo
```

## 3. Run the all-in-one installer

`install.sh` is idempotent (safe to re-run after a partial failure) and
does everything end to end:

1. Checks/installs each system dependency (skipping anything already
   present).
2. Provisions the MySQL database and application user, generating a
   random password.
3. Writes a working `.env` (`SECRET_KEY`, `DATABASE_URL`, and the
   `UPLOAD_FOLDER`/`LOG_FILE` paths, pointed at wherever you actually
   cloned the repo — not a hardcoded location).
4. Runs Flask-Migrate against the real database.
5. Runs an end-to-end smoke test (uploads a real image through both
   storage methods, verifies every page and both retrieval routes, and
   confirms the validator rejects a bad file) against a **disposable
   throwaway database** that's dropped afterward — your real database and
   `uploads/` folder are never touched by test data.
6. Hands file ownership back to the user who ran `sudo`, so `flask run`
   works immediately afterward without permission errors.

Every step prints a colored PASS/FAIL line, with a summary at the end:

```bash
chmod +x install.sh
sudo ./install.sh
```

Flags:

| Flag | Effect |
|---|---|
| `--skip-smoke-test` | Skip step 5 (useful on repeat runs where you don't want the extra time/DB churn). |
| `--skip-db` | Skip MySQL provisioning and migration entirely — use this if you're pointing at an external/managed MySQL instance; set `DATABASE_URL` in `.env` yourself afterward, then run `flask db upgrade` manually. |

It checks for / installs as needed:

| Dependency | Purpose |
|---|---|
| `python3`, `python3-venv` (+ the exact `python3.X-venv` for your installed version), `python3-pip` | Runtime + virtual environment |
| `libjpeg-dev`, `zlib1g-dev`, `libwebp-dev` | Pillow's native image codecs |
| `mysql-server` | Database (MySQL 8) |
| `apache2` | Web server |
| `libapache2-mod-wsgi-py3` | Runs Flask under Apache |
| `git` | Version control |

If a failure occurs partway through, fix the reported issue and re-run
`sudo ./install.sh` — it picks up where it left off rather than redoing
completed steps. Two things it defends against automatically:

* **Interrupted dpkg/apt state** (common on freshly-provisioned VM
  images) — it runs `dpkg --configure -a` as a safe preflight repair
  before installing anything.
* **The apt/dpkg lock being held by `unattended-upgrades`** (which runs
  automatically after boot) — instead of failing immediately, it waits
  (up to 5 minutes) for the lock to free up.

After a successful run, skip straight to **step 7** below — the database
is already created, migrated, and verified.

## 4. Manual database setup (only if you used `--skip-db`)

```bash
sudo mysql
```

```sql
CREATE DATABASE image_storage_demo CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'image_demo_user'@'localhost' IDENTIFIED BY 'CHANGE_ME';
GRANT ALL PRIVILEGES ON image_storage_demo.* TO 'image_demo_user'@'localhost';
FLUSH PRIVILEGES;
EXIT;
```

Apply the schema (or use Flask-Migrate, step 6):

```bash
mysql -u image_demo_user -p image_storage_demo < database/schema.sql
mysql -u image_demo_user -p image_storage_demo < database/seed.sql   # optional demo rows
```

## 5. Manual `.env` review (only if you used `--skip-db`)

`install.sh` writes `SECRET_KEY`, `DATABASE_URL`, `UPLOAD_FOLDER`, and
`LOG_FILE` for you automatically on a normal run. If you used
`--skip-db`, set `DATABASE_URL` yourself:

```bash
nano .env
```

```
DATABASE_URL=mysql+pymysql://image_demo_user:CHANGE_ME@localhost:3306/image_storage_demo
```

## 6. Manual migration (only if you used `--skip-db`)

```bash
source venv/bin/activate
export FLASK_APP=run.py
flask db upgrade
```

## 7. Try it with the Flask dev server

```bash
source venv/bin/activate
flask run --host 0.0.0.0 --port 5000
```

Visit `http://<vm-ip>:5000` from your host machine's browser and confirm
the home page loads, then try both upload flows.

## 8. Deploy with Apache + mod_wsgi

```bash
sudo cp deployment/apache/image-storage-demo.conf /etc/apache2/sites-available/
sudo a2ensite image-storage-demo
sudo a2enmod wsgi
sudo a2dissite 000-default   # optional, avoids the default site clashing
sudo systemctl reload apache2
```

Edit `deployment/apache/image-storage-demo.wsgi` if your project path or
Python version differs from `/var/www/image-storage-demo` /
`python3.12`, and update `ServerName` in the `.conf` file to match your
VM's hostname or IP.

If you deployed the code somewhere other than the repo you cloned into,
move (or symlink) the project directory to `/var/www/image-storage-demo`
so the paths baked into the `.conf`/`.wsgi` files line up, then re-run
the installer from the new location (it's idempotent and will simply
reuse your existing database credentials):

```bash
sudo mkdir -p /var/www
sudo cp -r ~/image-storage-demo /var/www/image-storage-demo
cd /var/www/image-storage-demo && sudo ./install.sh
```

Visit `http://<vm-ip>/` — Apache should now be serving the app via
mod_wsgi, with static files served directly by Apache per the `Alias
/static` directive in the vhost config.

## 9. Alternative: Nginx + Gunicorn

If you prefer not to use Apache/mod_wsgi:

```bash
source venv/bin/activate
gunicorn -w 3 -b 127.0.0.1:8000 "run:app"
```

then reverse-proxy `127.0.0.1:8000` from Nginx and serve `app/static/`
and `uploads/` (via the app, not directly) as described in the Apache
vhost above.

## 10. Troubleshooting

* **`install.sh` fails on "dpkg was interrupted"** — this shouldn't
  happen anymore (the script repairs it automatically as a preflight
  step), but if apt itself is in a genuinely broken state beyond a
  simple `dpkg --configure -a`, run that command manually and re-run
  `sudo ./install.sh`.
* **`install.sh` hangs on "apt/dpkg lock is held..."** — `unattended-upgrades`
  is mid-update; the script waits up to 5 minutes automatically. If it
  times out, check `sudo systemctl status unattended-upgrades` and retry
  once it's finished.
* **`ModuleNotFoundError` under Apache** — the `python-path` in
  `WSGIDaemonProcess` (in the `.conf` file) or the venv path in the
  `.wsgi` file doesn't match your actual install location.
* **413 on upload** — file exceeds `MAX_CONTENT_LENGTH` (10 MB) or
  Apache's `LimitRequestBody` in the vhost config; keep both in sync.
* **`Access denied for user`** — re-check the `DATABASE_URL` credentials
  in `.env`; if you used the automatic installer, re-run `sudo
  ./install.sh` and it will reuse (not rotate) the existing password.
* **Static files 404 under Apache but work with `flask run`** — confirm
  the `Alias /static` path in the vhost config points at
  `app/static`, not the project root.
* **Permission denied running `flask run` after `sudo ./install.sh`** —
  shouldn't happen (the installer hands ownership back to the invoking
  user automatically); if it does, run `sudo chown -R $USER:$USER .`
  from the project directory.
