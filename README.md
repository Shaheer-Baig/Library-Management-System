# Library Management System

A full-featured web application for managing library operations - books, students, loans, fines, reservations, and reports. Built with Flask (Python) and MySQL, featuring role-based access for admins and students, along with robust security measures.

## Table of Contents

- [Overview](#overview)
- [Features](#features)
  - [Admin Features](#admin-features)
  - [Student Features](#student-features)
- [Security Features](#security-features)
- [Technology Stack](#technology-stack)
- [Installation & Setup](#installation--setup)
  - [Prerequisites](#prerequisites)
  - [Step-by-Step Guide](#step-by-step-guide)
- [Database Setup](#database-setup)
- [Running the Application](#running-the-application)
- [Default Credentials](#default-credentials)
- [Project Structure](#project-structure)
- [Acknowledgments](#acknowledgments)

---

## Overview

The **Library Management System** is a web‑based solution that streamlines library workflows: book cataloguing, student management, issuing/returning books, automatic fine calculation, and reservation handling. It features two distinct user roles:

- **Admin** - full control over books, students, loans, fines, categories, publishers, and system reports.
- **Student** - browse the catalogue, borrow books, reserve unavailable titles, view personal history and fines.

The system uses a relational database (MySQL) with a clean separation of SQL logic (`queries.py`) from the Flask routes and frontend (`app.py`). It includes inline editing on all management tables, tabbed interfaces for unified workflows, and a responsive design using Tailwind CSS.

---

## Features

### Admin Features

- **Dashboard** - key statistics (total books, available, issued, students, active loans, overdue loans, total unpaid fines).
- **Manage Categories** - add, edit, delete book categories (inline editing).
- **Manage Publishers** - add, edit, delete publishers (inline editing).
- **Manage Admins** - create new admin accounts, reset passwords, delete admins (can't delete own account).
- **Manage Students** - add students, edit profiles (username, email, phone), reset passwords, delete students.
- **Manage Books** - add new books, search/filter by title/author/category, inline editing of all fields (except status), delete books.
- **Manage Loans & Fines** - issue books to students, filter loans (all/active/returned), view fine details, mark fines as paid, issue fines for overdue loans, demo tool to backdate loans.
- **Reports** - tabbed view of:
  - Books per category
  - Top 10 borrowed books
  - Overdue loans (with days overdue)
- **Authentication** - unified login/register page with tabs (Admin Login, Student Login, Student Register).
- **Session Security** - 30‑minute timeout, HTTP‑only cookies, SameSite=Strict.

### Student Features

- **Dashboard** - view active loans count, pending reservations, unpaid fines, lifetime borrowed count.
- **Browse Catalogue** - filter by category, search by title/author, see real‑time status (Available/Issued).
- **Issue Available Books** - one‑click borrowing (limit 5 concurrent loans).
- **Reserve Issued Books** - place a reservation; when returned, the reservation is automatically fulfilled.
- **Return Books** - return borrowed books; late returns generate a fine (PKR 5/day).
- **My History** - complete borrowing history with loan status (Active/Late/On time).
- **My Reservations** - list pending, fulfilled, or cancelled reservations; cancel pending reservations.
- **My Fines** - list fines with payment status, total unpaid amount.
- **Secure Registration** - create a new student account.

---

## Security Features

The application follows industry‑standard security practices to protect against common web vulnerabilities:

| Threat | Mitigation |
|--------|-------------|
| **SQL Injection** | All database queries use **parameterized statements** via `mysql.connector` (e.g., `cur.execute("SELECT ... WHERE id = %s", (id,))`). No raw string concatenation. |
| **Cross‑Site Scripting (XSS)** | All user‑supplied data is escaped in templates using Jinja2’s `| e` filter. Inputs are validated with regular expressions. |
| **CSRF (Cross‑Site Request Forgery)** | Flask‑WTF generates unique CSRF tokens for every POST form; tokens are validated automatically. |
| **Password Storage** | Passwords are hashed using **Werkzeug’s `generate_password_hash`** (scrypt by default) - never stored as plain text. |
| **Session Hijacking** | Session cookies are marked `HttpOnly` and `SameSite=Strict`. Session lifetime is 30 minutes. In production, `SESSION_COOKIE_SECURE = True` should be enabled (requires HTTPS). |
| **Role‑Based Access Control (RBAC)** | A custom `@role_required` decorator restricts routes to admin or student roles. Unauthorized access redirects to the home page. |
| **Input Validation** | All form inputs (username, password, ISBN, email, phone, year, etc.) are validated with regular expressions and length limits. |
| **Error Handling** | Custom 404 and 500 error pages prevent leakage of stack traces or internal details. |

---

## Technology Stack

| Layer       | Technology                                                      |
|-------------|-----------------------------------------------------------------|
| Backend     | Python 3.13+, Flask (micro‑framework)                          |
| Database    | MySQL (with `mysql-connector-python`)                          |
| Frontend    | HTML5, Tailwind CSS (via CDN), vanilla JavaScript              |
| Security    | Flask‑WTF (CSRF), Werkzeug (password hashing)                  |
| Logging     | Custom SQL query logger (logs to `query_logs/queries.log`)     |

---

## Installation & Setup

### Prerequisites

- Python 3.13 or higher
- MySQL server (local or remote)
- `pip` (Python package manager)

### Step-by-Step Guide

1. **Clone the repository**

```bash
git clone https://github.com/Shaheer-Baig/Library-Management-System.git
cd Library-Management-System
```

2. **Create a virtual environment**

```bash
python -m venv venv

# Linux/macOS:
source venv/bin/activate

# Windows:
venv\Scripts\activate
```

3. **Install dependencies**

```bash
pip install -r requirements.txt
```

4. **Set up the MySQL database**
   - Start your MySQL server.
   - Create the database and tables by running the provided `setup.sql` script:

 ```bash
 mysql -u root -p < setup.sql
 ```

   - The script **drops** an existing `library_db` database, recreates it, and populates it with:
     - 16 categories
     - 25+ publishers (including local ones from Pakistan, India, Bangladesh)
     - ~150 books
     - 8 student accounts + 1 admin account
     - Extensive demo loans, fines, reservations.

5. **Configure database connection**

	- Edit `config.py` (or set environment variables):

```python
MYSQL_HOST = "localhost"
MYSQL_USER = "root"
MYSQL_PASSWORD = "yourpassword"
MYSQL_DB = "library_db"
```

6. **Run the application**

```bash
python app.py
```

- The Flask development server will start at `http://127.0.0.1:5000`.

---

## Database Setup

The system uses a MySQL database named `library_db` with the following tables:

- `admins` - administrator accounts.
- `students` - student accounts (username, password hash, email, phone).
- `categories` - book categories (e.g., Fiction, Science, Novels, Poetry).
- `publishers` - book publishers (name, country, established year).
- `books` - catalogue (title, author, ISBN, category & publisher foreign keys, status, added_at).
- `issued_books` - loan records (book_id, student_id, issue_date, expiry_date, return_date).
- `fines` - late‑return fines (issued_book_id, amount, paid, created_at, paid_at).
- `reservations` - pending/fulfilled/cancelled reservations.

Foreign keys enforce referential integrity, and appropriate indexes improve query performance.

The `setup.sql` script (run once) creates the schema and seeds all data, including realistic demo transactions.

---

## Running the Application

After completing installation:

1. Ensure MySQL is running.
2. Activate the virtual environment.
3. Run `python app.py`.
4. Open your browser to `http://localhost:5000`.

### Default Credentials

| Role    | Username | Password      |
|---------|----------|---------------|
| Admin   | admin    | admin@123     |
| Student | yasir    | yasir@798     |
| Student | shaheer  | shaheer@330   |
| Student | kiran    | kiran@342     |
| Student | ahmed    | ahmed@123     |
| Student | fatima   | fatima@456    |
| Student | rahul    | rahul@789     |
| Student | saima    | saima@101     |
| Student | bilal    | bilal@202     |

*Note: All student passwords are the same as the ones listed in `setup.sql` (hashed).*

---

## Project Structure

```
Library-Management-System/
├── app.py                  # Flask routes, validation, session handling
├── queries.py              # All database functions (SQL queries)
├── config.py               # MySQL connection settings
├── requirements.txt        # Python dependencies
├── setup.sql               # Complete database schema + seed data
├── templates/              # HTML templates (Jinja2)
│   ├── base.html
│   ├── auth.html           # Unified login/register (tabs)
│   ├── admin_dashboard.html
│   ├── manage_admins.html
│   ├── manage_students.html
│   ├── manage_categories.html
│   ├── manage_publishers.html
│   ├── manage_books.html
│   ├── manage_loans.html
│   ├── reports.html
│   ├── student_dashboard.html
│   ├── student_catalogue.html
│   ├── my_history.html
│   ├── my_reservations.html
│   ├── my_fines.html
│   ├── error.html
│   └── _sql_panel.html      # Debug SQL panel (visible on all pages)
├── static/                  # Static assets (CSS, images)
│   └── images/
├── query_logs/              # Log file (queries.log) - created automatically
└── README.md                # This file
```

---

## Acknowledgments

- **Tailwind CSS** for rapid styling.
- **Flask** and its extensions for a clean, secure web framework.
- **MySQL** for reliable relational database storage.
- All contributors and open‑source libraries used in this project.

---

## Troubleshooting

- If you get the error `Database Error`, when running `app.py` after sometime.
- To fix this issue, please run the following commands in the order.

```
sudo mkdir -p /run/mysqld
sudo chown mysql:mysql /run/mysqld
sudo chmod 755 /run/mysqld
sudo service mysql restart

mysql -u root -p -e "DROP DATABASE IF EXISTS library_db;"
mysql -u root -p -e "CREATE DATABASE library_db;"
mysql -u root -p library_db < setup.sql
```

---
