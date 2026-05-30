from flask import Flask, render_template, request, redirect, url_for, flash, session, abort, g
from datetime import datetime, timedelta, date
import mysql.connector
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from flask_wtf.csrf import CSRFProtect
import re
import os

# Import all database functions from queries.py
from queries import (
    db_cursor,  # needed for context manager? Not directly, but used inside queries
    get_admin_by_username,
    create_admin,
    get_all_admins,
    reset_admin_password,
    delete_admin,
    get_student_by_username,
    get_student_by_id,
    create_student,
    update_student_profile,
    update_student_password,
    delete_student,
    get_all_students,
    get_available_books_for_issue,
    get_book_by_isbn,
    get_book_by_id,
    get_book_details_for_edit,
    add_book,
    update_book,
    delete_book,
    get_all_books_with_details,
    search_books_by_keyword,
    get_books_with_filters,
    update_book_status,
    get_all_categories,
    add_category,
    update_category,
    delete_category,
    get_all_publishers,
    add_publisher,
    update_publisher,
    delete_publisher,
    get_active_loan_count,
    get_active_loans_for_student,
    get_student_borrowing_history,
    get_all_issued_books,
    get_loan_by_id,
    issue_book,
    return_book,
    create_fine,
    make_loan_overdue_demo,
    get_reserved_book_ids_by_student,
    get_student_reservations,
    add_reservation,
    cancel_reservation,
    get_next_pending_reservation,
    fulfill_reservation,
    get_unpaid_fines_total_for_student,
    get_fines_for_student,
    get_outstanding_fines,
    get_total_unpaid_fines,
    mark_fine_paid,
    get_admin_dashboard_stats,
    get_student_dashboard_stats,
    get_overdue_loans,
    get_top_borrowed_books,
    get_books_per_category,
)

app = Flask(__name__)
app.secret_key = os.urandom(24)
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Strict'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=30)

csrf = CSRFProtect(app)

# ---------- Request/response hooks for SQL panel ----------
@app.before_request
def _init_query_log():
    carried = session.pop('pending_queries', [])
    g.queries = list(carried)

@app.after_request
def _carry_query_log(response):
    if response.status_code in (301, 302, 303, 307, 308):
        if getattr(g, 'queries', None):
            session['pending_queries'] = g.queries[-20:]
    return response

@app.context_processor
def inject_queries():
    return {"queries": getattr(g, "queries", [])}

# ---------- Input validation functions ----------
def validate_username(username):
    if not username or len(username) < 3 or len(username) > 20:
        return False
    return bool(re.match(r'^[a-zA-Z0-9_]+$', username))

def validate_password(password):
    if not password or len(password) < 8 or len(password) > 50:
        return False
    return bool(re.match(r'^[\w@#$%^&+=]+$', password))

def validate_isbn(isbn):
    if not isbn or len(isbn) > 13:
        return False
    return bool(re.match(r'^[0-9-]+$', isbn))

def validate_text(text):
    if not text or len(text) > 100:
        return False
    return bool(re.match(r'^[\w\s.,-]+$', text))

def validate_email(email):
    if not email:
        return True
    if len(email) > 100:
        return False
    return bool(re.match(r'^[\w.+-]+@[\w-]+\.[\w.-]+$', email))

def validate_phone(phone):
    if not phone:
        return True
    if len(phone) > 20:
        return False
    return bool(re.match(r'^[\d\s+\-()]+$', phone))

def validate_year(year_str):
    if not year_str:
        return True
    try:
        y = int(year_str)
    except (TypeError, ValueError):
        return False
    return 1400 <= y <= 2100

def validate_short_text(text, max_len=50):
    if not text or len(text) > max_len:
        return False
    return bool(re.match(r'^[\w\s.,&\'/-]+$', text))

def validate_long_text(text, max_len=255):
    if text is None or text == '':
        return True
    return len(text) <= max_len

def parse_optional_int(s):
    if s is None or s == '':
        return None
    try:
        return int(s)
    except (TypeError, ValueError):
        return None

# ---------- Role decorator ----------
def role_required(role):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'role' not in session or session['role'] != role:
                flash('Access denied', 'error')
                return redirect(url_for('index'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# ---------- Error handlers ----------
@app.errorhandler(404)
def page_not_found(e):
    return render_template('error.html', message='Page not found'), 404

@app.errorhandler(500)
def internal_error(e):
    return render_template('error.html', message='Internal server error'), 500

# ---------- Routes ----------
@app.route('/')
def index():
    return render_template('auth.html')

@app.route('/auth')
def auth():
    return render_template('auth.html')

@app.route('/admin_login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if not validate_username(username) or not validate_password(password):
            flash('Invalid username or password format', 'error')
            return redirect(url_for('admin_login'))
        try:
            admin = get_admin_by_username(username)
            if admin and check_password_hash(admin['password'], password):
                session['admin_id'] = admin['id']
                session['role'] = 'admin'
                session.permanent = True
                return redirect(url_for('admin_dashboard'))
            flash('Invalid credentials', 'error')
        except mysql.connector.Error:
            flash('Database error', 'error')
        return redirect(url_for('admin_login'))
    return redirect(url_for('auth', tab='admin'))

@app.route('/student_login', methods=['GET', 'POST'])
def student_login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if not validate_username(username) or not validate_password(password):
            flash('Invalid username or password format', 'error')
            return redirect(url_for('student_login'))
        try:
            student = get_student_by_username(username)
            if student and check_password_hash(student['password'], password):
                session['student_id'] = student['id']
                session['role'] = 'student'
                session.permanent = True
                return redirect(url_for('student_dashboard'))
            flash('Invalid credentials', 'error')
        except mysql.connector.Error:
            flash('Database error', 'error')
        return redirect(url_for('student_login'))
    return redirect(url_for('auth', tab='student'))

@app.route('/student_register', methods=['GET', 'POST'])
def student_register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if not validate_username(username) or not validate_password(password):
            flash('Invalid username or password format', 'error')
            return redirect(url_for('student_register'))
        try:
            hashed = generate_password_hash(password)
            create_student(username, hashed)
            flash('Student registered successfully!', 'success')
            return redirect(url_for('student_login'))
        except mysql.connector.Error:
            flash('Database error', 'error')
        return redirect(url_for('student_register'))
    return redirect(url_for('auth', tab='register'))

@app.route('/admin_dashboard')
@role_required('admin')
def admin_dashboard():
    try:
        stats = get_admin_dashboard_stats()
    except mysql.connector.Error:
        flash('Database error loading stats', 'error')
        stats = {}
    return render_template('admin_dashboard.html', stats=stats)

@app.route('/manage_admins', methods=['GET', 'POST'])
@role_required('admin')
def manage_admins():
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'add':
            username = request.form.get('username')
            password = request.form.get('password')
            if not validate_username(username) or not validate_password(password):
                flash('Invalid username or password format', 'error')
                return redirect(url_for('manage_admins'))
            try:
                hashed = generate_password_hash(password)
                create_admin(username, hashed)
                flash('Admin created successfully!', 'success')
            except mysql.connector.IntegrityError:
                flash('Username already exists.', 'error')
            except mysql.connector.Error:
                flash('Database error', 'error')
            return redirect(url_for('manage_admins'))
        elif action == 'delete':
            target_id = parse_optional_int(request.form.get('id'))
            if target_id is None:
                flash('Invalid admin id', 'error')
                return redirect(url_for('manage_admins'))
            if target_id == session.get('admin_id'):
                flash('You cannot delete the admin account you are logged in as.', 'error')
                return redirect(url_for('manage_admins'))
            try:
                delete_admin(target_id)
                flash('Admin deleted.', 'success')
            except mysql.connector.Error:
                flash('Database error', 'error')
            return redirect(url_for('manage_admins'))
        elif action == 'reset_password':
            target_id = parse_optional_int(request.form.get('id'))
            new_password = request.form.get('new_password')
            if target_id is None or not validate_password(new_password):
                flash('Invalid input', 'error')
                return redirect(url_for('manage_admins'))
            try:
                hashed = generate_password_hash(new_password)
                reset_admin_password(target_id, hashed)
                flash('Password reset.', 'success')
            except mysql.connector.Error:
                flash('Database error', 'error')
            return redirect(url_for('manage_admins'))
    try:
        admins = get_all_admins()
    except mysql.connector.Error:
        flash('Database error', 'error')
        return redirect(url_for('admin_dashboard'))
    return render_template('manage_admins.html', admins=admins)

@app.route('/manage_students', methods=['GET', 'POST'])
@role_required('admin')
def manage_students():
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'add':
            username = request.form.get('username')
            password = request.form.get('password')
            email = request.form.get('email') or None
            phone = request.form.get('phone') or None
            if not validate_username(username) or not validate_password(password):
                flash('Invalid username or password format', 'error')
                return redirect(url_for('manage_students'))
            if not validate_email(email):
                flash('Invalid email', 'error')
                return redirect(url_for('manage_students'))
            if not validate_phone(phone):
                flash('Invalid phone number', 'error')
                return redirect(url_for('manage_students'))
            try:
                hashed = generate_password_hash(password)
                create_student(username, hashed, email, phone)
                flash('Student added successfully!', 'success')
            except mysql.connector.IntegrityError:
                flash('Username or email already exists.', 'error')
            except mysql.connector.Error:
                flash('Database error', 'error')
            return redirect(url_for('manage_students'))
        elif action == 'update':
            student_id = parse_optional_int(request.form.get('id'))
            username = request.form.get('username')
            email = request.form.get('email') or None
            phone = request.form.get('phone') or None
            if student_id is None or not validate_username(username):
                flash('Invalid student data', 'error')
                return redirect(url_for('manage_students'))
            if not validate_email(email):
                flash('Invalid email', 'error')
                return redirect(url_for('manage_students'))
            if not validate_phone(phone):
                flash('Invalid phone number', 'error')
                return redirect(url_for('manage_students'))
            try:
                update_student_profile(student_id, username, email, phone)
                flash('Student profile updated.', 'success')
            except mysql.connector.IntegrityError:
                flash('Username or email already taken.', 'error')
            except mysql.connector.Error:
                flash('Database error', 'error')
            return redirect(url_for('manage_students'))
        elif action == 'reset_password':
            student_id = parse_optional_int(request.form.get('id'))
            new_password = request.form.get('new_password')
            if student_id is None or not validate_password(new_password):
                flash('Invalid input', 'error')
                return redirect(url_for('manage_students'))
            try:
                hashed = generate_password_hash(new_password)
                update_student_password(student_id, hashed)
                flash('Password reset.', 'success')
            except mysql.connector.Error:
                flash('Database error', 'error')
            return redirect(url_for('manage_students'))
        elif action == 'delete':
            student_id = parse_optional_int(request.form.get('id'))
            if student_id is None:
                flash('Invalid student id', 'error')
                return redirect(url_for('manage_students'))
            try:
                delete_student(student_id)
                flash('Student deleted.', 'success')
            except mysql.connector.IntegrityError:
                flash('Cannot delete this student: they have loan records. Remove the loans first.', 'error')
            except mysql.connector.Error:
                flash('Database error', 'error')
            return redirect(url_for('manage_students'))
    try:
        students = get_all_students()
    except mysql.connector.Error:
        flash('Database error', 'error')
        return redirect(url_for('admin_dashboard'))
    return render_template('manage_students.html', students=students)

@app.route('/manage_categories', methods=['GET', 'POST'])
@role_required('admin')
def manage_categories():
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'add':
            name = request.form.get('name')
            description = request.form.get('description') or None
            if not validate_short_text(name, 50):
                flash('Invalid category name', 'error')
                return redirect(url_for('manage_categories'))
            if not validate_long_text(description, 255):
                flash('Description too long (max 255 chars)', 'error')
                return redirect(url_for('manage_categories'))
            try:
                add_category(name, description)
                flash('Category added.', 'success')
            except mysql.connector.IntegrityError:
                flash('Category already exists.', 'error')
            except mysql.connector.Error:
                flash('Database error', 'error')
        elif action == 'edit':
            cat_id = parse_optional_int(request.form.get('id'))
            name = request.form.get('name')
            description = request.form.get('description') or None
            if cat_id is None or not validate_short_text(name, 50):
                flash('Invalid category data', 'error')
                return redirect(url_for('manage_categories'))
            if not validate_long_text(description, 255):
                flash('Description too long (max 255 chars)', 'error')
                return redirect(url_for('manage_categories'))
            try:
                update_category(cat_id, name, description)
                flash('Category updated.', 'success')
            except mysql.connector.IntegrityError:
                flash('Category name already exists.', 'error')
            except mysql.connector.Error:
                flash('Database error', 'error')
        elif action == 'delete':
            cat_id = parse_optional_int(request.form.get('id'))
            if cat_id is None:
                flash('Invalid category id', 'error')
                return redirect(url_for('manage_categories'))
            try:
                delete_category(cat_id)
                flash('Category deleted.', 'success')
            except mysql.connector.Error:
                flash('Database error', 'error')
        return redirect(url_for('manage_categories'))
    try:
        categories = get_all_categories()
    except mysql.connector.Error:
        flash('Database error', 'error')
        return redirect(url_for('admin_dashboard'))
    return render_template('manage_categories.html', categories=categories)

@app.route('/manage_publishers', methods=['GET', 'POST'])
@role_required('admin')
def manage_publishers():
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'add':
            name = request.form.get('name')
            country = request.form.get('country') or None
            year_str = request.form.get('established_year')
            if not validate_short_text(name, 100):
                flash('Invalid publisher name', 'error')
                return redirect(url_for('manage_publishers'))
            if country and not validate_short_text(country, 50):
                flash('Invalid country', 'error')
                return redirect(url_for('manage_publishers'))
            if not validate_year(year_str):
                flash('Established year must be between 1400 and 2100', 'error')
                return redirect(url_for('manage_publishers'))
            year = parse_optional_int(year_str)
            try:
                add_publisher(name, country, year)
                flash('Publisher added.', 'success')
            except mysql.connector.IntegrityError:
                flash('Publisher already exists.', 'error')
            except mysql.connector.Error:
                flash('Database error', 'error')
        elif action == 'edit':
            pub_id = parse_optional_int(request.form.get('id'))
            name = request.form.get('name')
            country = request.form.get('country') or None
            year_str = request.form.get('established_year')
            if pub_id is None or not validate_short_text(name, 100):
                flash('Invalid publisher data', 'error')
                return redirect(url_for('manage_publishers'))
            if country and not validate_short_text(country, 50):
                flash('Invalid country', 'error')
                return redirect(url_for('manage_publishers'))
            if not validate_year(year_str):
                flash('Established year must be between 1400 and 2100', 'error')
                return redirect(url_for('manage_publishers'))
            year = parse_optional_int(year_str)
            try:
                update_publisher(pub_id, name, country, year)
                flash('Publisher updated.', 'success')
            except mysql.connector.IntegrityError:
                flash('Publisher name already exists.', 'error')
            except mysql.connector.Error:
                flash('Database error', 'error')
        elif action == 'delete':
            pub_id = parse_optional_int(request.form.get('id'))
            if pub_id is None:
                flash('Invalid publisher id', 'error')
                return redirect(url_for('manage_publishers'))
            try:
                delete_publisher(pub_id)
                flash('Publisher deleted.', 'success')
            except mysql.connector.Error:
                flash('Database error', 'error')
        return redirect(url_for('manage_publishers'))
    try:
        publishers = get_all_publishers()
    except mysql.connector.Error:
        flash('Database error', 'error')
        return redirect(url_for('admin_dashboard'))
    return render_template('manage_publishers.html', publishers=publishers)

@app.route('/manage_books', methods=['GET', 'POST'])
@role_required('admin')
def manage_books():
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'add':
            title = request.form.get('title')
            author = request.form.get('author')
            isbn = request.form.get('isbn')
            category_id = parse_optional_int(request.form.get('category_id'))
            publisher_id = parse_optional_int(request.form.get('publisher_id'))
            if not validate_text(title) or not validate_text(author) or not validate_isbn(isbn):
                flash('Invalid book details', 'error')
            else:
                try:
                    add_book(title, author, isbn, category_id, publisher_id)
                    flash('Book added successfully!', 'success')
                except mysql.connector.IntegrityError:
                    flash('A book with that ISBN already exists.', 'error')
                except mysql.connector.Error:
                    flash('Database error', 'error')
            return redirect(url_for('manage_books'))
        elif action == 'edit':
            book_id = parse_optional_int(request.form.get('id'))
            title = request.form.get('title')
            author = request.form.get('author')
            isbn = request.form.get('isbn')
            category_id = parse_optional_int(request.form.get('category_id'))
            publisher_id = parse_optional_int(request.form.get('publisher_id'))
            if not validate_text(title) or not validate_text(author) or not validate_isbn(isbn):
                flash('Invalid book details', 'error')
            else:
                try:
                    update_book(book_id, title, author, isbn, category_id, publisher_id)
                    flash('Book updated.', 'success')
                except mysql.connector.IntegrityError:
                    flash('A book with that ISBN already exists.', 'error')
                except mysql.connector.Error:
                    flash('Database error', 'error')
            return redirect(url_for('manage_books'))
        elif action == 'delete':
            book_id = parse_optional_int(request.form.get('id'))
            if book_id is None:
                flash('Invalid book id', 'error')
            else:
                try:
                    delete_book(book_id)
                    flash('Book deleted.', 'success')
                except mysql.connector.IntegrityError:
                    flash('Cannot delete this book: it has loan records. Remove the loans first.', 'error')
                except mysql.connector.Error:
                    flash('Database error', 'error')
            return redirect(url_for('manage_books'))
        else:
            flash('Invalid action', 'error')
            return redirect(url_for('manage_books'))
    q = request.args.get('q', '').strip()
    cat_id = parse_optional_int(request.args.get('cat_id'))
    try:
        books = get_books_with_filters(category_id=cat_id, search_query=q if q else None)
        categories = get_all_categories()
        publishers = get_all_publishers()
    except mysql.connector.Error:
        flash('Database error', 'error')
        return redirect(url_for('admin_dashboard'))
    return render_template('manage_books.html', books=books, categories=categories, publishers=publishers, q=q, selected_cat=cat_id)

@app.route('/manage_loans', methods=['GET', 'POST'])
@role_required('admin')
def manage_loans():
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'issue':
            isbn = request.form.get('isbn')
            student_username = request.form.get('student_username')
            if not validate_isbn(isbn) or not validate_username(student_username):
                flash('Invalid ISBN or student username', 'error')
                return redirect(url_for('manage_loans'))
            try:
                book = get_book_by_isbn(isbn)
                if not book:
                    flash('Book ISBN not found!', 'error')
                    return redirect(url_for('manage_loans'))
                if book['status'] != 'Available':
                    flash('Book is already issued!', 'error')
                    return redirect(url_for('manage_loans'))
                student = get_student_by_username(student_username)
                if not student:
                    flash('Student not found!', 'error')
                    return redirect(url_for('manage_loans'))
                issue_date = date.today().strftime('%Y-%m-%d')
                expiry_date = (date.today() + timedelta(days=14)).strftime('%Y-%m-%d')
                update_book_status(book['id'], 'Issued')
                issue_book(book['id'], student['id'], issue_date, expiry_date)
                flash('Book issued successfully!', 'success')
            except mysql.connector.Error:
                flash('Database error', 'error')
            return redirect(url_for('manage_loans'))
        elif action == 'demo_overdue':
            loan_id = parse_optional_int(request.form.get('loan_id'))
            if loan_id is None:
                flash('Invalid loan ID', 'error')
                return redirect(url_for('manage_loans'))
            try:
                from queries import make_loan_overdue_demo
                new_expiry = (date.today() - timedelta(days=5)).strftime('%Y-%m-%d')
                rows = make_loan_overdue_demo(loan_id, new_expiry)
                if rows:
                    flash(f'Loan #{loan_id} backdated by 5 days for demo.', 'success')
                else:
                    flash('Loan not found or already returned.', 'error')
            except mysql.connector.Error:
                flash('Database error', 'error')
            return redirect(url_for('manage_loans'))
        elif action == 'issue_fine':
            loan_id = parse_optional_int(request.form.get('loan_id'))
            if loan_id is None:
                flash('Invalid loan ID', 'error')
                return redirect(url_for('manage_loans'))
            try:
                from queries import get_loan_by_id, issue_fine_for_loan
                loan = get_loan_by_id(loan_id)
                if not loan or loan['return_date'] is not None:
                    flash('Loan not found or already returned', 'error')
                    return redirect(url_for('manage_loans'))
                days_overdue = (date.today() - loan['expiry_date']).days
                if days_overdue <= 0:
                    flash('Loan is not overdue yet', 'error')
                    return redirect(url_for('manage_loans'))
                if issue_fine_for_loan(loan_id, days_overdue):
                    flash(f'Fine of PKR {days_overdue * 5:.2f} issued for overdue loan.', 'success')
                else:
                    flash('A fine already exists for this loan.', 'warning')
            except mysql.connector.Error:
                flash('Database error', 'error')
            return redirect(url_for('manage_loans'))
        elif action == 'mark_paid':
            fine_id = parse_optional_int(request.form.get('fine_id'))
            if fine_id is None:
                flash('Invalid fine id', 'error')
                return redirect(url_for('manage_loans'))
            try:
                mark_fine_paid(fine_id)
                flash('Fine marked as paid.', 'success')
            except mysql.connector.Error:
                flash('Database error', 'error')
            return redirect(url_for('manage_loans'))
        else:
            flash('Invalid action', 'error')
            return redirect(url_for('manage_loans'))
    q = request.args.get('q', '').strip()
    status_filter = request.args.get('status', 'all')
    try:
        from queries import get_all_loans_with_details, get_outstanding_fines, get_total_unpaid_fines
        loans = get_all_loans_with_details(search=q if q else None, status_filter=status_filter)
        fines = get_outstanding_fines()
        total_unpaid = get_total_unpaid_fines()
        students = get_all_students()
        available_books = get_available_books_for_issue()
    except mysql.connector.Error:
        flash('Database error', 'error')
        return redirect(url_for('admin_dashboard'))
    today = date.today()
    return render_template('manage_loans.html', loans=loans, students=students, available_books=available_books, q=q, status_filter=status_filter, today=today, fines=fines, total_unpaid=total_unpaid)

@app.route('/reports')
@role_required('admin')
def reports():
    try:
        cat_rows = get_books_per_category()
        top_rows = get_top_borrowed_books(10)
        overdue_rows = get_overdue_loans()
    except mysql.connector.Error:
        flash('Database error loading reports', 'error')
        return redirect(url_for('admin_dashboard'))
    return render_template('reports.html', cat_rows=cat_rows, top_rows=top_rows, overdue_rows=overdue_rows)

@app.route('/student_dashboard')
@role_required('student')
def student_dashboard():
    student_id = session['student_id']
    try:
        stats = get_student_dashboard_stats(student_id)
        issued_books = get_active_loans_for_student(student_id)
    except mysql.connector.Error:
        flash('Database error', 'error')
        return redirect(url_for('index'))
    return render_template('student_dashboard.html', issued_books=issued_books, stats=stats)

@app.route('/student_issue_book/<int:book_id>', methods=['POST'])
@role_required('student')
def student_issue_book(book_id):
    student_id = session['student_id']
    try:
        book = get_book_by_id(book_id, for_update=True)
        if not book:
            flash('Book not found', 'error')
            return redirect(url_for('student_catalogue'))
        if book['status'] != 'Available':
            flash('Book is not available', 'error')
            return redirect(url_for('student_catalogue'))
        active_loans = get_active_loans_for_student(student_id)
        if any(loan['book_id'] == book_id for loan in active_loans):
            flash('You already have this book on loan', 'error')
            return redirect(url_for('student_catalogue'))
        if len(active_loans) >= 5:
            flash('Loan limit reached (5 books).', 'error')
            return redirect(url_for('student_catalogue'))
        issue_date = date.today().strftime('%Y-%m-%d')
        expiry_date = (date.today() + timedelta(days=14)).strftime('%Y-%m-%d')
        issue_book(book_id, student_id, issue_date, expiry_date)
        update_book_status(book_id, 'Issued')
        flash('Book issued successfully. Due back in 14 days.', 'success')
    except mysql.connector.Error:
        flash('Database error', 'error')
    return redirect(url_for('student_dashboard'))

@app.route('/student_catalogue')
@role_required('student')
def student_catalogue():
    student_id = session['student_id']
    cat_id = parse_optional_int(request.args.get('cat_id'))
    q = (request.args.get('q') or '').strip()
    try:
        books = get_books_with_filters(category_id=cat_id, search_query=q if q else None)
        categories = get_all_categories()
        my_reserved_ids = get_reserved_book_ids_by_student(student_id)
    except mysql.connector.Error:
        flash('Database error', 'error')
        return redirect(url_for('student_dashboard'))
    for b in books:
        if b['status'] == 'Available':
            b['action_state'] = 'issue'
        elif b['id'] in my_reserved_ids:
            b['action_state'] = 'reserved_by_me'
        elif b['status'] == 'Issued':
            b['action_state'] = 'reserve'
        else:
            b['action_state'] = 'unavailable'
    return render_template('student_catalogue.html', books=books, categories=categories,
                           selected_cat=cat_id, q=q)

@app.route('/reserve_book/<int:book_id>', methods=['POST'])
@role_required('student')
def reserve_book(book_id):
    student_id = session['student_id']
    try:
        book = get_book_by_id(book_id)
        if not book:
            flash('Book not found', 'error')
            return redirect(url_for('student_catalogue'))
        if book['status'] == 'Available':
            flash('This book is available — issue it instead of reserving.', 'error')
            return redirect(url_for('student_catalogue'))
        reservations = get_student_reservations(student_id)
        if any(r['book_id'] == book_id and r['status'] == 'Pending' for r in reservations):
            flash('You already have a pending reservation on this book.', 'error')
            return redirect(url_for('student_catalogue'))
        add_reservation(book_id, student_id)
        flash('Reservation placed.', 'success')
    except mysql.connector.Error:
        flash('Database error', 'error')
    return redirect(url_for('student_catalogue'))

@app.route('/my_history')
@role_required('student')
def my_history():
    student_id = session['student_id']
    try:
        loans = get_student_borrowing_history(student_id)
    except mysql.connector.Error:
        flash('Database error', 'error')
        return redirect(url_for('student_dashboard'))
    return render_template('my_history.html', loans=loans)

@app.route('/my_reservations', methods=['GET', 'POST'])
@role_required('student')
def my_reservations():
    student_id = session['student_id']
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'cancel':
            res_id = parse_optional_int(request.form.get('id'))
            if res_id is None:
                flash('Invalid reservation id', 'error')
                return redirect(url_for('my_reservations'))
            try:
                cancel_reservation(res_id, student_id)
                flash('Reservation cancelled.', 'success')
            except mysql.connector.Error:
                flash('Database error', 'error')
        return redirect(url_for('my_reservations'))
    try:
        reservations = get_student_reservations(student_id)
    except mysql.connector.Error:
        flash('Database error', 'error')
        return redirect(url_for('student_dashboard'))
    return render_template('my_reservations.html', reservations=reservations)

@app.route('/my_fines')
@role_required('student')
def my_fines():
    student_id = session['student_id']
    try:
        fines = get_fines_for_student(student_id)
        total_unpaid = get_unpaid_fines_total_for_student(student_id)
    except mysql.connector.Error:
        flash('Database error', 'error')
        return redirect(url_for('student_dashboard'))
    return render_template('my_fines.html', fines=fines, total_unpaid=total_unpaid)

@app.route('/student/return_book/<int:issued_book_id>', methods=['POST'])
@role_required('student')
def student_return_book(issued_book_id):
    student_id = session['student_id']
    try:
        loan = get_loan_by_id(issued_book_id, for_update=True)
        if not loan:
            flash('Loan not found.', 'error')
            return redirect(url_for('student_dashboard'))
        if loan['student_id'] != student_id:
            flash('You can only return your own loans.', 'error')
            return redirect(url_for('student_dashboard'))
        if loan['return_date'] is not None:
            flash('This loan has already been returned.', 'error')
            return redirect(url_for('student_dashboard'))
        return_date = date.today()
        return_book(issued_book_id, return_date)
        update_book_status(loan['book_id'], 'Available')
        days_late = (return_date - loan['expiry_date']).days
        if days_late > 0:
            amount = days_late * 5.00
            create_fine(issued_book_id, amount)
            flash(f'Returned {days_late} day(s) late. Fine: PKR {amount:.2f}.', 'error')
        else:
            flash('Book returned on time. No fine.', 'success')
        # Check for pending reservation
        next_res = get_next_pending_reservation(loan['book_id'])
        if next_res:
            fulfill_reservation(next_res['id'])
    except mysql.connector.Error:
        flash('Database error', 'error')
    return redirect(url_for('student_dashboard'))

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully', 'success')
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)
