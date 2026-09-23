# MySQL Database Setup Guide for MQTT Chat Project

## 1. Environment Overview

| Component | Configuration |
|---|---|
| Database | MySQL Server 8.4 |
| Host | `127.0.0.1` |
| Port | `3307` |
| Database Name | `mqtt_chat` |
| Application User | `mqtt_chat_user` |
| Django Backend | `django.db.backends.mysql` |

> Port `3307` is used because port `3306` is already being used by the existing MariaDB/XAMPP installation.

---

## 2. Install MySQL Server

Install **MySQL Community Server 8.4 LTS** for Windows 64-bit using the MSI installer.

### 2.1 Networking Configuration

Enable TCP/IP and set:

```text
TCP/IP: Enabled
Port: 3307
```

Local database environment:

```text
MariaDB / XAMPP
127.0.0.1:3306

MySQL Server 8.4
127.0.0.1:3307
```

### 2.2 Windows Service

Recommended service name:

```text
MySQL84
```

Enable:

```text
Configure MySQL Server as a Windows Service
```

Optionally enable automatic startup.

### 2.3 Root Account

Create a password for the MySQL `root` account.

```text
Username: root
Password: <your-root-password>
```

Do not store the real root password directly in source code.

### 2.4 Sample Databases

At the **Sample Databases** step, disable:

```text
Create Sakila database
Create World database
```

The MQTT Chat project does not need them.

### 2.5 Apply Configuration

Execute the configuration and ensure these steps succeed:

```text
Initialize Database
Configure Windows Service
Start MySQL Server
Apply Security Settings
Apply Network Configuration
```

---

## 3. Verify MySQL Installation

Open PowerShell:

```powershell
& "C:\Program Files\MySQL\MySQL Server 8.4\bin\mysql.exe" --version
```

Expected:

```text
mysql Ver 8.4.x
```

---

## 4. Connect to MySQL

```powershell
& "C:\Program Files\MySQL\MySQL Server 8.4\bin\mysql.exe" -u root -p -P 3307
```

Enter the root password when prompted.

---

## 5. Verify Server Version

```sql
SELECT VERSION();
```

Expected:

```text
8.4.x
```

It should **not** return:

```text
10.4.32-MariaDB
```

If MariaDB is returned, you are connecting to port `3306` instead of MySQL on `3307`.

---

## 6. Create Project Database

```sql
CREATE DATABASE mqtt_chat
CHARACTER SET utf8mb4
COLLATE utf8mb4_unicode_ci;
```

Verify:

```sql
SHOW DATABASES;
```

---

## 7. Create Application Database User

Create a dedicated account for Django instead of using `root`:

```sql
CREATE USER 'mqtt_chat_user'@'localhost'
IDENTIFIED BY '<your-password>';
```

Example for local development:

```sql
CREATE USER 'mqtt_chat_user'@'localhost'
IDENTIFIED BY '123456';
```

---

## 8. Grant Database Permissions

```sql
GRANT ALL PRIVILEGES
ON mqtt_chat.*
TO 'mqtt_chat_user'@'localhost';

FLUSH PRIVILEGES;
```

Verify:

```sql
SELECT user, host
FROM mysql.user;
```

Expected entry:

```text
mqtt_chat_user | localhost
```

---

## 9. Test Application User

Exit MySQL:

```sql
EXIT;
```

Reconnect:

```powershell
& "C:\Program Files\MySQL\MySQL Server 8.4\bin\mysql.exe" -u mqtt_chat_user -p -P 3307 mqtt_chat
```

If login succeeds, the account is ready for Django.

---

## 10. Install Python MySQL Driver

Activate the virtual environment:

```powershell
.venv\Scripts\Activate.ps1
```

Install dependencies:

```bash
pip install django paho-mqtt mysqlclient
```

Update `requirements.txt`:

```bash
pip freeze > requirements.txt
```

---

## 11. Configure Django Database

Open:

```text
config/settings.py
```

Replace SQLite configuration with:

```python
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": "mqtt_chat",
        "USER": "mqtt_chat_user",
        "PASSWORD": "123456",
        "HOST": "127.0.0.1",
        "PORT": "3307",
        "OPTIONS": {
            "charset": "utf8mb4",
        },
    }
}
```

Connection architecture:

```text
Django
   │
   ▼
127.0.0.1:3307
   │
   ▼
MySQL Server 8.4
   │
   ▼
mqtt_chat
```

---

## 12. Check Django Configuration

```bash
python manage.py check
```

Expected:

```text
System check identified no issues (0 silenced).
```

If Django reports:

```text
MariaDB 10.11 or later is required
```

check that Django is using:

```python
"PORT": "3307"
```

because:

```text
3306 -> MariaDB 10.4 / XAMPP
3307 -> MySQL Server 8.4
```

---

## 13. Run Django Migrations

```bash
python manage.py migrate
```

Django will create its default tables, such as:

```text
auth_group
auth_permission
auth_user
django_admin_log
django_content_type
django_migrations
django_session
```

---

## 14. Verify Database Tables

Connect to MySQL:

```powershell
& "C:\Program Files\MySQL\MySQL Server 8.4\bin\mysql.exe" -u mqtt_chat_user -p -P 3307 mqtt_chat
```

Then:

```sql
SHOW TABLES;
```

Expected tables include:

```text
auth_group
auth_group_permissions
auth_permission
auth_user
auth_user_groups
auth_user_user_permissions
django_admin_log
django_content_type
django_migrations
django_session
```

---

## 15. Test Django Database Connection

```bash
python manage.py shell
```

Then:

```python
from django.db import connection
connection.ensure_connection()
print(connection.connection.get_server_info())
```

Expected:

```text
8.4.x
```

Exit:

```python
exit()
```

---

## 16. Recommended Environment Variable Configuration

Create a `.env` file:

```env
DB_NAME=mqtt_chat
DB_USER=mqtt_chat_user
DB_PASSWORD=123456
DB_HOST=127.0.0.1
DB_PORT=3307
```

Add it to `.gitignore`:

```gitignore
.env
```

Install:

```bash
pip install python-dotenv
```

Then in `config/settings.py`:

```python
import os
from dotenv import load_dotenv

load_dotenv()

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": os.getenv("DB_NAME"),
        "USER": os.getenv("DB_USER"),
        "PASSWORD": os.getenv("DB_PASSWORD"),
        "HOST": os.getenv("DB_HOST"),
        "PORT": os.getenv("DB_PORT"),
        "OPTIONS": {
            "charset": "utf8mb4",
        },
    }
}
```

---

## 17. Final Local Database Architecture

```text
Windows
│
├── XAMPP
│   └── MariaDB 10.4
│       └── 127.0.0.1:3306
│
└── MySQL Server 8.4
    ├── Windows Service: MySQL84
    ├── 127.0.0.1:3307
    └── mqtt_chat
        └── mqtt_chat_user
```

Application architecture:

```text
Chat Client
    │
    │ MQTT
    ▼
Mosquitto :1883
    │
    ▼
Django MQTT Worker
    │
    ▼
ChatService
    │
    ▼
Django ORM
    │
    ▼
MySQL Server 8.4 :3307
    │
    ▼
mqtt_chat
```

---

## 18. Setup Checklist

- [ ] Install MySQL Server 8.4
- [ ] Configure MySQL port `3307`
- [ ] Configure Windows service `MySQL84`
- [ ] Set root password
- [ ] Disable Sakila sample database
- [ ] Disable World sample database
- [ ] Start MySQL Server
- [ ] Verify `SELECT VERSION()` returns MySQL `8.4.x`
- [ ] Create database `mqtt_chat`
- [ ] Create user `mqtt_chat_user`
- [ ] Grant permissions
- [ ] Test login using `mqtt_chat_user`
- [ ] Activate `.venv`
- [ ] Install `mysqlclient`
- [ ] Configure Django `DATABASES`
- [ ] Run `python manage.py check`
- [ ] Run `python manage.py migrate`
- [ ] Verify Django tables in MySQL
- [ ] Add `.env` to `.gitignore`

---

## 19. Useful Commands

Start Django:

```bash
python manage.py runserver
```

Check configuration:

```bash
python manage.py check
```

Create migrations:

```bash
python manage.py makemigrations
```

Apply migrations:

```bash
python manage.py migrate
```

View migration status:

```bash
python manage.py showmigrations
```

Open Django shell:

```bash
python manage.py shell
```

Connect directly to MySQL:

```powershell
& "C:\Program Files\MySQL\MySQL Server 8.4\bin\mysql.exe" -u mqtt_chat_user -p -P 3307 mqtt_chat
```

Check version:

```sql
SELECT VERSION();
```

Check current database:

```sql
SELECT DATABASE();
```

List tables:

```sql
SHOW TABLES;
```
