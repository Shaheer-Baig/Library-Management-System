import os
import logging
from contextlib import contextmanager
from datetime import datetime
import mysql.connector
from flask import g, has_app_context

# ---------- Configuration ----------
MYSQL_HOST = os.environ.get("MYSQL_HOST", "localhost")
MYSQL_USER = os.environ.get("MYSQL_USER", "root")
MYSQL_PASSWORD = os.environ.get("MYSQL_PASSWORD", "root")
MYSQL_DB = os.environ.get("MYSQL_DB", "library_db")

# ---------- Logging setup for SQL queries ----------
_LOG_DIR = "logs"
_LOG_FILE = os.path.join(_LOG_DIR, "queries.log")
os.makedirs(_LOG_DIR, exist_ok=True)

_logger = logging.getLogger("lms.sql")
if not _logger.handlers:
    _logger.setLevel(logging.INFO)
    _fmt = logging.Formatter("[%(asctime)s] %(message)s")
    _fh = logging.FileHandler(_LOG_FILE, encoding="utf-8")
    _fh.setFormatter(_fmt)
    _logger.addHandler(_fh)
    _logger.propagate = False

# ---------- Database connection ----------
def get_conn():
    return mysql.connector.connect(
        host=MYSQL_HOST,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        database=MYSQL_DB,
    )

# ---------- Logging cursor wrapper ----------
class LoggingCursor:
    def __init__(self, cursor):
        object.__setattr__(self, "_cursor", cursor)

    def _render(self, fallback_query):
        rendered = getattr(self._cursor, "statement", None)
        if isinstance(rendered, bytes):
            rendered = rendered.decode("utf-8", errors="replace")
        return rendered or fallback_query

    def _record(self, rendered):
        _logger.info(rendered)
        if has_app_context():
            queries = getattr(g, "queries", None)
            if queries is None:
                queries = []
                g.queries = queries
            queries.append({
                "sql": rendered,
                "rowcount": self._cursor.rowcount,
                "ts": datetime.now().isoformat(),
            })

    def execute(self, query, params=None):
        result = self._cursor.execute(query, params)
        self._record(self._render(query))
        return result

    def executemany(self, query, seq):
        result = self._cursor.executemany(query, seq)
        self._record(self._render(query))
        return result

    def __getattr__(self, name):
        return getattr(self._cursor, name)

    def __iter__(self):
        return iter(self._cursor)

# ---------- Context manager for DB cursor ----------
@contextmanager
def db_cursor():
    conn = get_conn()
    cur = conn.cursor(dictionary=True)
    wrapped = LoggingCursor(cur)
    try:
        yield wrapped
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()

# ============================================================
# ALL DATABASE QUERIES (backend)
# ============================================================

# ----- Admins -----
def get_admin_by_username(username):
    with db_cursor() as cur:
        cur.execute("SELECT * FROM admins WHERE username = %s", (username,))
        return cur.fetchone()

def create_admin(username, hashed_password):
    with db_cursor() as cur:
        cur.execute("INSERT INTO admins (username, password) VALUES (%s, %s)",
                    (username, hashed_password))

def get_all_admins():
    with db_cursor() as cur:
        cur.execute("SELECT id, username, created_at FROM admins ORDER BY id")
        return cur.fetchall()

def reset_admin_password(admin_id, hashed_password):
    with db_cursor() as cur:
        cur.execute("UPDATE admins SET password = %s WHERE id = %s",
                    (hashed_password, admin_id))

def delete_admin(admin_id):
    with db_cursor() as cur:
        cur.execute("DELETE FROM admins WHERE id = %s", (admin_id,))

# ----- Students -----
def get_student_by_username(username):
    with db_cursor() as cur:
        cur.execute("SELECT * FROM students WHERE username = %s", (username,))
        return cur.fetchone()

def get_student_by_id(student_id):
    with db_cursor() as cur:
        cur.execute("SELECT id, username, email, phone, created_at FROM students WHERE id = %s",
                    (student_id,))
        return cur.fetchone()

def create_student(username, hashed_password, email=None, phone=None):
    with db_cursor() as cur:
        cur.execute(
            "INSERT INTO students (username, password, email, phone) VALUES (%s, %s, %s, %s)",
            (username, hashed_password, email, phone)
        )

def update_student_profile(student_id, username, email, phone):
    with db_cursor() as cur:
        cur.execute(
            "UPDATE students SET username = %s, email = %s, phone = %s WHERE id = %s",
            (username, email, phone, student_id)
        )

def update_student_password(student_id, hashed_password):
    with db_cursor() as cur:
        cur.execute("UPDATE students SET password = %s WHERE id = %s",
                    (hashed_password, student_id))

def delete_student(student_id):
    with db_cursor() as cur:
        cur.execute("DELETE FROM students WHERE id = %s", (student_id,))

def get_all_students():
    with db_cursor() as cur:
        cur.execute("SELECT id, username, email, phone, created_at FROM students ORDER BY id")
        return cur.fetchall()

# ----- Books -----
def get_available_books_for_issue():
    with db_cursor() as cur:
        cur.execute("SELECT isbn, title FROM books WHERE status = 'Available'")
        return cur.fetchall()

def get_book_by_isbn(isbn):
    with db_cursor() as cur:
        cur.execute("SELECT id, status FROM books WHERE isbn = %s", (isbn,))
        return cur.fetchone()

def get_book_by_id(book_id, for_update=False):
    with db_cursor() as cur:
        if for_update:
            cur.execute("SELECT id, status FROM books WHERE id = %s FOR UPDATE", (book_id,))
        else:
            cur.execute("SELECT id, status FROM books WHERE id = %s", (book_id,))
        return cur.fetchone()

def get_book_details_for_edit(book_id):
    with db_cursor() as cur:
        cur.execute(
            """
            SELECT b.id, b.title, b.author, b.isbn,
                   b.category_id, b.publisher_id, b.status
            FROM books b WHERE b.id = %s
            """,
            (book_id,)
        )
        return cur.fetchone()

def add_book(title, author, isbn, category_id, publisher_id):
    with db_cursor() as cur:
        cur.execute(
            """
            INSERT INTO books (title, author, isbn, category_id, publisher_id)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (title, author, isbn, category_id, publisher_id)
        )

def update_book(book_id, title, author, isbn, category_id, publisher_id):
    with db_cursor() as cur:
        cur.execute(
            """
            UPDATE books
            SET title = %s, author = %s, isbn = %s,
                category_id = %s, publisher_id = %s
            WHERE id = %s
            """,
            (title, author, isbn, category_id, publisher_id, book_id)
        )

def delete_book(book_id):
    with db_cursor() as cur:
        cur.execute("DELETE FROM books WHERE id = %s", (book_id,))

def get_all_books_with_details():
    with db_cursor() as cur:
        cur.execute(
            """
            SELECT b.id, b.title, b.author, b.isbn, b.status,
                   c.name AS category_name, p.name AS publisher_name
            FROM books b
            LEFT JOIN categories c ON b.category_id = c.id
            LEFT JOIN publishers p ON b.publisher_id = p.id
            ORDER BY b.id
            """
        )
        return cur.fetchall()

def search_books_by_keyword(keyword):
    with db_cursor() as cur:
        cur.execute(
            """
            SELECT * FROM books
            WHERE title LIKE %s OR author LIKE %s OR isbn LIKE %s
            """,
            (f'%{keyword}%', f'%{keyword}%', f'%{keyword}%')
        )
        return cur.fetchall()

def get_books_with_filters(category_id=None, publisher_id=None, search_query=None):
    sql = """
        SELECT b.id, b.title, b.author, b.isbn, b.status,
               b.category_id, b.publisher_id,
               COALESCE(c.name, 'Uncategorized') AS category,
               COALESCE(p.name, 'Unknown Publisher') AS publisher
        FROM books b
        LEFT JOIN categories c ON b.category_id = c.id
        LEFT JOIN publishers p ON b.publisher_id = p.id
        WHERE 1=1
    """
    params = []
    if category_id is not None:
        sql += " AND b.category_id = %s"
        params.append(category_id)
    if publisher_id is not None:
        sql += " AND b.publisher_id = %s"
        params.append(publisher_id)
    if search_query:
        sql += " AND (b.title LIKE %s OR b.author LIKE %s)"
        like = f'%{search_query}%'
        params.extend([like, like])
    sql += " ORDER BY b.id"
    with db_cursor() as cur:
        cur.execute(sql, tuple(params))
        return cur.fetchall()

def update_book_status(book_id, new_status):
    with db_cursor() as cur:
        cur.execute("UPDATE books SET status = %s WHERE id = %s", (new_status, book_id))

# ----- Categories -----
def get_all_categories():
    with db_cursor() as cur:
        cur.execute("SELECT id, name, description FROM categories ORDER BY id")
        return cur.fetchall()

def add_category(name, description):
    with db_cursor() as cur:
        cur.execute("INSERT INTO categories (name, description) VALUES (%s, %s)",
                    (name, description))

def update_category(category_id, name, description):
    with db_cursor() as cur:
        cur.execute("UPDATE categories SET name = %s, description = %s WHERE id = %s",
                    (name, description, category_id))

def delete_category(category_id):
    with db_cursor() as cur:
        cur.execute("DELETE FROM categories WHERE id = %s", (category_id,))

# ----- Publishers -----
def get_all_publishers():
    with db_cursor() as cur:
        cur.execute("SELECT id, name, country, established_year FROM publishers ORDER BY id")
        return cur.fetchall()

def add_publisher(name, country, established_year):
    with db_cursor() as cur:
        cur.execute(
            "INSERT INTO publishers (name, country, established_year) VALUES (%s, %s, %s)",
            (name, country, established_year)
        )

def update_publisher(publisher_id, name, country, established_year):
    with db_cursor() as cur:
        cur.execute(
            "UPDATE publishers SET name = %s, country = %s, established_year = %s WHERE id = %s",
            (name, country, established_year, publisher_id)
        )

def delete_publisher(publisher_id):
    with db_cursor() as cur:
        cur.execute("DELETE FROM publishers WHERE id = %s", (publisher_id,))

# ----- Issued books / Loans -----
def get_all_loans_with_details(search=None, status_filter='all'):
    sql = """
        SELECT ib.id, b.title, s.username,
               ib.issue_date, ib.expiry_date, ib.return_date,
               CASE
                   WHEN f.id IS NOT NULL THEN TRUE
                   ELSE FALSE
               END AS fine_exists,
               COALESCE(f.paid, FALSE) AS fine_paid
        FROM issued_books ib
        JOIN books b ON ib.book_id = b.id
        JOIN students s ON ib.student_id = s.id
        LEFT JOIN fines f ON f.issued_book_id = ib.id
        WHERE 1=1
    """
    params = []
    if search:
        sql += " AND (b.title LIKE %s OR s.username LIKE %s)"
        like = f'%{search}%'
        params.extend([like, like])
    if status_filter == 'active':
        sql += " AND ib.return_date IS NULL"
    elif status_filter == 'returned':
        sql += " AND ib.return_date IS NOT NULL"
    sql += " ORDER BY ib.id DESC"
    with db_cursor() as cur:
        cur.execute(sql, tuple(params))
        return cur.fetchall()

def issue_fine_for_loan(loan_id, days_overdue, rate_per_day=5.00):
    with db_cursor() as cur:
        cur.execute("SELECT id FROM fines WHERE issued_book_id = %s", (loan_id,))
        if cur.fetchone(): return False
        amount = days_overdue * rate_per_day
        cur.execute(
            "INSERT INTO fines (issued_book_id, amount, paid) VALUES (%s, %s, FALSE)",
            (loan_id, amount)
        )
        return True

def issue_fine_for_returned_loan(loan_id, days_late, rate_per_day=5.00):
    with db_cursor() as cur:
        cur.execute("SELECT id FROM fines WHERE issued_book_id = %s", (loan_id,))
        if cur.fetchone():
            return False
        amount = days_late * rate_per_day
        cur.execute(
            "INSERT INTO fines (issued_book_id, amount, paid) VALUES (%s, %s, FALSE)",
            (loan_id, amount)
        )
        return True

def get_active_loan_count(student_id):
    with db_cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) AS n FROM issued_books WHERE student_id = %s AND return_date IS NULL",
            (student_id,)
        )
        return cur.fetchone()['n']

def get_active_loans_for_student(student_id):
    with db_cursor() as cur:
        cur.execute(
            """
            SELECT ib.id, ib.book_id, b.title, ib.issue_date, ib.expiry_date, ib.return_date
            FROM issued_books ib
            JOIN books b ON ib.book_id = b.id
            WHERE ib.student_id = %s AND ib.return_date IS NULL
            ORDER BY ib.issue_date DESC
            """,
            (student_id,)
        )
        return cur.fetchall()

def get_student_borrowing_history(student_id):
    with db_cursor() as cur:
        cur.execute(
            """
            SELECT ib.id, b.title, b.author, ib.issue_date, ib.expiry_date, ib.return_date,
                   CASE
                     WHEN ib.return_date IS NULL THEN 'Active'
                     WHEN ib.return_date > ib.expiry_date THEN 'Late'
                     ELSE 'On time'
                   END AS loan_state
            FROM issued_books ib
            JOIN books b ON ib.book_id = b.id
            WHERE ib.student_id = %s
            ORDER BY ib.issue_date DESC
            """,
            (student_id,)
        )
        return cur.fetchall()

def get_all_issued_books():
    with db_cursor() as cur:
        cur.execute(
            """
            SELECT ib.id, b.title, s.username, ib.issue_date, ib.expiry_date, ib.return_date
            FROM issued_books ib
            JOIN books b ON ib.book_id = b.id
            JOIN students s ON ib.student_id = s.id
            """
        )
        return cur.fetchall()

def get_loan_by_id(loan_id, for_update=False):
    with db_cursor() as cur:
        if for_update:
            cur.execute(
                "SELECT id, book_id, student_id, expiry_date, return_date FROM issued_books WHERE id = %s FOR UPDATE",
                (loan_id,)
            )
        else:
            cur.execute(
                "SELECT id, book_id, student_id, expiry_date, return_date FROM issued_books WHERE id = %s",
                (loan_id,)
            )
        return cur.fetchone()

def issue_book(book_id, student_id, issue_date, expiry_date):
    with db_cursor() as cur:
        cur.execute(
            "INSERT INTO issued_books (book_id, student_id, issue_date, expiry_date) VALUES (%s, %s, %s, %s)",
            (book_id, student_id, issue_date, expiry_date)
        )

def return_book(loan_id, return_date):
    with db_cursor() as cur:
        cur.execute("UPDATE issued_books SET return_date = %s WHERE id = %s", (return_date, loan_id))

def create_fine(issued_book_id, amount):
    with db_cursor() as cur:
        cur.execute(
            "INSERT INTO fines (issued_book_id, amount) VALUES (%s, %s)",
            (issued_book_id, amount)
        )

def make_loan_overdue_demo(loan_id, new_expiry_date):
    with db_cursor() as cur:
        cur.execute(
            "UPDATE issued_books SET expiry_date = %s WHERE id = %s AND return_date IS NULL",
            (new_expiry_date, loan_id)
        )
        return cur.rowcount

# ----- Reservations -----
def get_reserved_book_ids_by_student(student_id):
    with db_cursor() as cur:
        cur.execute(
            "SELECT book_id FROM reservations WHERE student_id = %s AND status = 'Pending'",
            (student_id,)
        )
        return {row['book_id'] for row in cur.fetchall()}

def get_student_reservations(student_id):
    with db_cursor() as cur:
        cur.execute(
            """
            SELECT r.id, r.book_id, b.title, b.author, r.reserved_at, r.status
            FROM reservations r
            JOIN books b ON r.book_id = b.id
            WHERE r.student_id = %s
            ORDER BY r.reserved_at DESC
            """,
            (student_id,)
        )
        return cur.fetchall()

def add_reservation(book_id, student_id):
    with db_cursor() as cur:
        cur.execute(
            "INSERT INTO reservations (book_id, student_id, status) VALUES (%s, %s, 'Pending')",
            (book_id, student_id)
        )

def cancel_reservation(reservation_id, student_id):
    with db_cursor() as cur:
        cur.execute(
            "UPDATE reservations SET status = 'Cancelled' WHERE id = %s AND student_id = %s AND status = 'Pending'",
            (reservation_id, student_id)
        )

def get_next_pending_reservation(book_id):
    with db_cursor() as cur:
        cur.execute(
            "SELECT id FROM reservations WHERE book_id = %s AND status = 'Pending' ORDER BY reserved_at ASC LIMIT 1",
            (book_id,)
        )
        return cur.fetchone()

def fulfill_reservation(reservation_id):
    with db_cursor() as cur:
        cur.execute("UPDATE reservations SET status = 'Fulfilled' WHERE id = %s", (reservation_id,))

# ----- Fines -----
def get_unpaid_fines_total_for_student(student_id):
    with db_cursor() as cur:
        cur.execute(
            """
            SELECT COALESCE(SUM(f.amount), 0) AS total
            FROM fines f
            JOIN issued_books ib ON f.issued_book_id = ib.id
            WHERE ib.student_id = %s AND f.paid = FALSE
            """,
            (student_id,)
        )
        return cur.fetchone()['total']

def get_fines_for_student(student_id):
    with db_cursor() as cur:
        cur.execute(
            """
            SELECT f.id, b.title, f.amount, f.paid, f.created_at, f.paid_at
            FROM fines f
            JOIN issued_books ib ON f.issued_book_id = ib.id
            JOIN books b ON ib.book_id = b.id
            WHERE ib.student_id = %s
            ORDER BY f.created_at DESC
            """,
            (student_id,)
        )
        return cur.fetchall()

def get_outstanding_fines():
    with db_cursor() as cur:
        cur.execute(
            """
            SELECT f.id AS fine_id, s.username AS student, b.title AS book,
                   f.amount, f.created_at, ib.expiry_date, ib.return_date
            FROM fines f
            JOIN issued_books ib ON f.issued_book_id = ib.id
            JOIN students s ON ib.student_id = s.id
            JOIN books b ON ib.book_id = b.id
            WHERE f.paid = FALSE
            ORDER BY f.created_at DESC
            """
        )
        return cur.fetchall()

def get_total_unpaid_fines():
    with db_cursor() as cur:
        cur.execute("SELECT COALESCE(SUM(amount), 0) AS total FROM fines WHERE paid = FALSE")
        return cur.fetchone()['total']

def mark_fine_paid(fine_id):
    with db_cursor() as cur:
        cur.execute(
            "UPDATE fines SET paid = TRUE, paid_at = CURRENT_TIMESTAMP WHERE id = %s",
            (fine_id,)
        )

# ----- Statistics & Reports -----
def get_admin_dashboard_stats():
    stats = {}
    with db_cursor() as cur:
        cur.execute("SELECT COUNT(*) AS n FROM books")
        stats['total_books'] = cur.fetchone()['n']
        cur.execute("SELECT COUNT(*) AS n FROM books WHERE status = 'Available'")
        stats['available_books'] = cur.fetchone()['n']
        cur.execute("SELECT COUNT(*) AS n FROM books WHERE status = 'Issued'")
        stats['issued_books_count'] = cur.fetchone()['n']
        cur.execute("SELECT COUNT(*) AS n FROM students")
        stats['total_students'] = cur.fetchone()['n']
        cur.execute("SELECT COUNT(*) AS n FROM issued_books WHERE return_date IS NULL")
        stats['active_loans'] = cur.fetchone()['n']
        cur.execute("SELECT COUNT(*) AS n FROM issued_books WHERE return_date IS NULL AND expiry_date < CURDATE()")
        stats['overdue_loans'] = cur.fetchone()['n']
        cur.execute("SELECT COALESCE(SUM(amount), 0) AS total FROM fines WHERE paid = FALSE")
        stats['unpaid_fines_total'] = cur.fetchone()['total']
    return stats

def get_student_dashboard_stats(student_id):
    stats = {}
    with db_cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) AS n FROM issued_books WHERE student_id = %s AND return_date IS NULL",
            (student_id,)
        )
        stats['active_loans_count'] = cur.fetchone()['n']
        cur.execute(
            "SELECT COUNT(*) AS n FROM reservations WHERE student_id = %s AND status = 'Pending'",
            (student_id,)
        )
        stats['pending_reservations_count'] = cur.fetchone()['n']
        cur.execute(
            """
            SELECT COALESCE(SUM(f.amount), 0) AS total
            FROM fines f
            JOIN issued_books ib ON f.issued_book_id = ib.id
            WHERE ib.student_id = %s AND f.paid = FALSE
            """,
            (student_id,)
        )
        stats['unpaid_fines_total'] = cur.fetchone()['total']
        cur.execute(
            "SELECT COUNT(*) AS n FROM issued_books WHERE student_id = %s",
            (student_id,)
        )
        stats['total_borrowed_lifetime'] = cur.fetchone()['n']
    return stats

def get_overdue_loans():
    with db_cursor() as cur:
        cur.execute(
            """
            SELECT ib.id AS loan_id, s.username AS student, b.title AS book,
                   b.isbn, ib.issue_date, ib.expiry_date,
                   DATEDIFF(CURDATE(), ib.expiry_date) AS days_overdue
            FROM issued_books ib
            JOIN students s ON ib.student_id = s.id
            JOIN books b ON ib.book_id = b.id
            WHERE ib.return_date IS NULL AND ib.expiry_date < CURDATE()
            ORDER BY days_overdue DESC
            """
        )
        return cur.fetchall()

def get_top_borrowed_books(limit=10):
    with db_cursor() as cur:
        cur.execute(
            """
            SELECT b.id, b.title, b.author, COUNT(ib.id) AS times_borrowed
            FROM books b
            LEFT JOIN issued_books ib ON ib.book_id = b.id
            GROUP BY b.id, b.title, b.author
            ORDER BY times_borrowed DESC, b.title ASC
            LIMIT %s
            """,
            (limit,)
        )
        return cur.fetchall()

def get_books_per_category():
    with db_cursor() as cur:
        cur.execute(
            """
            SELECT COALESCE(c.name, 'Uncategorised') AS category, COUNT(b.id) AS book_count
            FROM books b
            LEFT JOIN categories c ON b.category_id = c.id
            GROUP BY c.id, c.name
            ORDER BY book_count DESC
            """
        )
        return cur.fetchall()
