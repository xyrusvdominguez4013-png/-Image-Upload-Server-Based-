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
git clone https://github.com/xyrusvdominguez4013-png/-Image-Upload-Server-Based-.git
cd -Image-Upload-Server-Based-
```

## 3. Run the dependency-checking installer

`install.sh` detects what's already installed and only installs what's
missing, so it's safe to re-run after a partial failure.

```bash
chmod +x install.sh
sudo ./install.sh
```

It checks for / installs as needed:

| Dependency | Purpose |
|---|---|
| `python3`, `python3-venv`, `python3-pip` | Runtime + virtual environment |
| `libjpeg-dev`, `zlib1g-dev`, `libwebp-dev` | Pillow's native image codecs |
| `mysql-server` | Database (MySQL 8) |
| `apache2` | Web server |
| `libapache2-mod-wsgi-py3` | Runs Flask under Apache |
| `git` | Version control |

It then creates a Python virtual environment in `venv/`, installs
`requirements.txt` into it, and copies `.env.example` to `.env`.

## 4. Configure MySQL

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

## 5. Configure `.env`

Edit `.env` (created from `.env.example` by `install.sh`):

```bash
nano .env
```

Set at minimum:

```
SECRET_KEY=<a long random value, e.g. `python3 -c "import secrets; print(secrets.token_hex(32))"`>
DATABASE_URL=mysql+pymysql://image_demo_user:CHANGE_ME@localhost:3306/image_storage_demo
```

## 6. Run database migrations

```bash
source venv/bin/activate
export FLASK_APP=run.py
flask db init        # first time only
flask db migrate -m "Initial schema"
flask db upgrade
```

## 7. Smoke-test with the Flask dev server

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
so the paths baked into the `.conf`/`.wsgi` files line up, e.g.:

```bash
sudo mkdir -p /var/www
sudo cp -r ~/-Image-Upload-Server-Based- /var/www/image-storage-demo
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

* **`ModuleNotFoundError` under Apache** — the `python-path` in
  `WSGIDaemonProcess` (in the `.conf` file) or the venv path in the
  `.wsgi` file doesn't match your actual install location.
* **413 on upload** — file exceeds `MAX_CONTENT_LENGTH` (10 MB) or
  Apache's `LimitRequestBody` in the vhost config; keep both in sync.
* **`Access denied for user`** — re-check the `DATABASE_URL` credentials
  in `.env` against what you created in step 4.
* **Static files 404 under Apache but work with `flask run`** — confirm
  the `Alias /static` path in the vhost config points at
  `app/static`, not the project root.
