from flask import Flask, render_template, request, redirect, url_for, flash, session, abort
from datetime import datetime, timedelta
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from flask_wtf.csrf import CSRFProtect
import re
import os

app = Flask(__name__)
app.secret_key = os.urandom(24)  # Secure random key
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Strict'
# Note: Set SESSION_COOKIE_SECURE = True in production with HTTPS
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=30)  # Session timeout

csrf = CSRFProtect(app)

# Input Validation
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

# Database Initialization
def init_db():
    with sqlite3.connect('library.db') as conn:
        cursor = conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS admins (id INTEGER PRIMARY KEY, username TEXT, password TEXT)''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS students (id INTEGER PRIMARY KEY, username TEXT, password TEXT)''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS books (id INTEGER PRIMARY KEY, title TEXT, author TEXT, isbn TEXT, status TEXT DEFAULT 'Available')''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS issued_books (id INTEGER PRIMARY KEY, book_id INTEGER, student_id INTEGER, issue_date TEXT, expiry_date TEXT, return_date TEXT)''')
        # Insert default admin
        hashed_password = generate_password_hash('231330@shaheer')
        cursor.execute('INSERT OR IGNORE INTO admins (username, password) VALUES (?, ?)', ('shaheer', hashed_password))
        conn.commit()

# Role-based access control decorator
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

# Custom Error Handlers
@app.errorhandler(404)
def page_not_found(e):
    return render_template('error.html', message='Page not found'), 404

@app.errorhandler(500)
def internal_error(e):
    return render_template('error.html', message='Internal server error'), 500

# Landing Page
@app.route('/')
def index():
    return render_template('index.html')

# Admin Login
@app.route('/admin_login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if not validate_username(username) or not validate_password(password):
            flash('Invalid username or password format', 'error')
            return redirect(url_for('admin_login'))
        try:
            with sqlite3.connect('library.db') as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT * FROM admins WHERE username = ?', (username,))
                admin = cursor.fetchone()
                if admin and check_password_hash(admin[2], password):
                    session['admin_id'] = admin[0]
                    session['role'] = 'admin'
                    session.permanent = True
                    return redirect(url_for('admin_dashboard'))
                flash('Invalid credentials', 'error')
        except sqlite3.Error:
            flash('Database error', 'error')
    return render_template('admin_login.html')

# Admin Dashboard
@app.route('/admin_dashboard')
@role_required('admin')
def admin_dashboard():
    return render_template('admin_dashboard.html')

# Create Admin
@app.route('/create_admin', methods=['GET', 'POST'])
@role_required('admin')
def create_admin():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if not validate_username(username) or not validate_password(password):
            flash('Invalid username or password format', 'error')
            return redirect(url_for('create_admin'))
        try:
            hashed_password = generate_password_hash(password)
            with sqlite3.connect('library.db') as conn:
                cursor = conn.cursor()
                cursor.execute('INSERT INTO admins (username, password) VALUES (?, ?)', (username, hashed_password))
                conn.commit()
                flash('Admin created successfully!', 'success')
            return redirect(url_for('admin_login'))
        except sqlite3.Error:
            flash('Database error', 'error')
    return render_template('create_admin.html')

# Add Book
@app.route('/add_book', methods=['GET', 'POST'])
@role_required('admin')
def add_book():
    if request.method == 'POST':
        title = request.form.get('title')
        author = request.form.get('author')
        isbn = request.form.get('isbn')
        if not validate_text(title) or not validate_text(author) or not validate_isbn(isbn):
            flash('Invalid book details', 'error')
            return redirect(url_for('add_book'))
        try:
            with sqlite3.connect('library.db') as conn:
                cursor = conn.cursor()
                cursor.execute('INSERT INTO books (title, author, isbn) VALUES (?, ?, ?)', (title, author, isbn))
                conn.commit()
                flash('Book added successfully!', 'success')
            return redirect(url_for('admin_dashboard'))
        except sqlite3.Error:
            flash('Database error', 'error')
    return render_template('add_book.html')

# View Books
@app.route('/view_books')
@role_required('admin')
def view_books():
    try:
        with sqlite3.connect('library.db') as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM books')
            books = cursor.fetchall()
        return render_template('view_books.html', books=books)
    except sqlite3.Error:
        flash('Database error', 'error')
        return redirect(url_for('admin_dashboard'))

# Issue Book (Admin)
@app.route('/issue_book', methods=['GET', 'POST'])
@role_required('admin')
def issue_book():
    if request.method == 'POST':
        isbn = request.form.get('isbn')
        student_username = request.form.get('student_username')
        if not validate_isbn(isbn) or not validate_username(student_username):
            flash('Invalid ISBN or student username', 'error')
            return redirect(url_for('issue_book'))
        try:
            issue_date = datetime.now().strftime('%Y-%m-%d')
            expiry_date = (datetime.now() + timedelta(days=14)).strftime('%Y-%m-%d')
            with sqlite3.connect('library.db') as conn:
                cursor = conn.cursor()
                # Verify book exists and is available
                cursor.execute('SELECT id, status FROM books WHERE isbn = ?', (isbn,))
                book = cursor.fetchone()
                if not book:
                    flash('Book ISBN not found!', 'error')
                    return redirect(url_for('issue_book'))
                book_id, status = book
                if status != 'Available':
                    flash('Book is already issued!', 'error')
                    return redirect(url_for('issue_book'))
                # Verify student exists
                cursor.execute('SELECT id FROM students WHERE username = ?', (student_username,))
                student = cursor.fetchone()
                if not student:
                    flash('Student username not found!', 'error')
                    return redirect(url_for('issue_book'))
                student_id = student[0]
                # Issue the book
                cursor.execute('UPDATE books SET status = "Issued" WHERE id = ?', (book_id,))
                cursor.execute('INSERT INTO issued_books (book_id, student_id, issue_date, expiry_date) VALUES (?, ?, ?, ?)',
                               (book_id, student_id, issue_date, expiry_date))
                conn.commit()
                flash('Book issued successfully!', 'success')
            return redirect(url_for('admin_dashboard'))
        except sqlite3.Error:
            flash('Database error', 'error')
    try:
        with sqlite3.connect('library.db') as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT username FROM students')
            students = cursor.fetchall()
            cursor.execute('SELECT isbn, title FROM books WHERE status = "Available"')
            books = cursor.fetchall()
        return render_template('issue_book.html', students=students, books=books)
    except sqlite3.Error:
        flash('Database error', 'error')
        return redirect(url_for('admin_dashboard'))

# View Issued Books
@app.route('/view_issued_books')
@role_required('admin')
def view_issued_books():
    try:
        with sqlite3.connect('library.db') as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT ib.id, b.title, s.username, ib.issue_date, ib.expiry_date, ib.return_date FROM issued_books ib JOIN books b ON ib.book_id = b.id JOIN students s ON ib.student_id = s.id')
            issued_books = cursor.fetchall()
        return render_template('view_issued_books.html', issued_books=issued_books)
    except sqlite3.Error:
        flash('Database error', 'error')
        return redirect(url_for('admin_dashboard'))

# View Students
@app.route('/view_students')
@role_required('admin')
def view_students():
    try:
        with sqlite3.connect('library.db') as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM students')
            students = cursor.fetchall()
        return render_template('view_students.html', students=students)
    except sqlite3.Error:
        flash('Database error', 'error')
        return redirect(url_for('admin_dashboard'))

# Student Register
@app.route('/student_register', methods=['GET', 'POST'])
def student_register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if not validate_username(username) or not validate_password(password):
            flash('Invalid username or password format', 'error')
            return redirect(url_for('student_register'))
        try:
            hashed_password = generate_password_hash(password)
            with sqlite3.connect('library.db') as conn:
                cursor = conn.cursor()
                cursor.execute('INSERT INTO students (username, password) VALUES (?, ?)', (username, hashed_password))
                conn.commit()
                flash('Student registered successfully!', 'success')
            return redirect(url_for('student_login'))
        except sqlite3.Error:
            flash('Database error', 'error')
    return render_template('student_register.html')

# Student Login
@app.route('/student_login', methods=['GET', 'POST'])
def student_login():
    if request.method == 'POST':
        username = request.form.get('username')  # Fixed: Correctly fetch username
        password = request.form.get('password')
        if not validate_username(username) or not validate_password(password):
            flash('Invalid username or password format', 'error')
            return redirect(url_for('student_login'))
        try:
            with sqlite3.connect('library.db') as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT * FROM students WHERE username = ?', (username,))
                student = cursor.fetchone()
                if student and check_password_hash(student[2], password):
                    session['student_id'] = student[0]
                    session['role'] = 'student'
                    session.permanent = True
                    return redirect(url_for('student_dashboard'))
                flash('Invalid credentials', 'error')
        except sqlite3.Error:
            flash('Database error', 'error')
    return render_template('student_login.html')

# Student Dashboard
@app.route('/student_dashboard')
@role_required('student')
def student_dashboard():
    student_id = session['student_id']
    try:
        with sqlite3.connect('library.db') as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT ib.id, b.title, ib.issue_date, ib.expiry_date, ib.return_date FROM issued_books ib JOIN books b ON ib.book_id = b.id WHERE ib.student_id = ?', (student_id,))
            issued_books = cursor.fetchall()
        return render_template('student_dashboard.html', issued_books=issued_books)
    except sqlite3.Error:
        flash('Database error', 'error')
        return redirect(url_for('index'))

# Search Books (For both Admin and Student)
@app.route('/search_books', methods=['GET', 'POST'])
def search_books():
    if 'role' not in session:
        flash('Access denied', 'error')
        return redirect(url_for('index'))
    if request.method == 'POST':
        search_query = request.form.get('search_query')
        if not validate_text(search_query):
            flash('Invalid search query', 'error')
            return redirect(url_for('search_books'))
        try:
            with sqlite3.connect('library.db') as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT * FROM books WHERE title LIKE ? OR author LIKE ? OR isbn LIKE ?',
                               (f'%{search_query}%', f'%{search_query}%', f'%{search_query}%'))
                books = cursor.fetchall()
            return render_template('search_books.html', books=books)
        except sqlite3.Error:
            flash('Database error', 'error')
    return render_template('search_books.html', books=[])

# Issue Book (Student)
@app.route('/student/issue_book/<int:book_id>', methods=['POST'])
@role_required('student')
def student_issue_book(book_id):
    student_id = session['student_id']
    try:
        issue_date = datetime.now().strftime('%Y-%m-%d')
        expiry_date = (datetime.now() + timedelta(days=14)).strftime('%Y-%m-%d')
        with sqlite3.connect('library.db') as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT status FROM books WHERE id = ?', (book_id,))
            status = cursor.fetchone()
            if not status:
                flash('Book not found!', 'error')
                return redirect(url_for('student_dashboard'))
            if status[0] == 'Available':
                cursor.execute('UPDATE books SET status = "Issued" WHERE id = ?', (book_id,))
                cursor.execute('INSERT INTO issued_books (book_id, student_id, issue_date, expiry_date) VALUES (?, ?, ?, ?)',
                               (book_id, student_id, issue_date, expiry_date))
                conn.commit()
                flash('Book issued successfully!', 'success')
            else:
                flash('Book is already issued!', 'error')
        return redirect(url_for('student_dashboard'))
    except sqlite3.Error:
        flash('Database error', 'error')
        return redirect(url_for('student_dashboard'))

# Return Book (Student)
@app.route('/student/return_book/<int:issued_book_id>', methods=['POST'])
@role_required('student')
def student_return_book(issued_book_id):
    try:
        return_date = datetime.now().strftime('%Y-%m-%d')
        with sqlite3.connect('library.db') as conn:
            cursor = conn.cursor()
            cursor.execute('UPDATE issued_books SET return_date = ? WHERE id = ?', (return_date, issued_book_id))
            cursor.execute('UPDATE books SET status = "Available" WHERE id = (SELECT book_id FROM issued_books WHERE id = ?)', (issued_book_id,))
            conn.commit()
            flash('Book returned successfully!', 'success')
        return redirect(url_for('student_dashboard'))
    except sqlite3.Error:
        flash('Database error', 'error')
        return redirect(url_for('student_dashboard'))

# Logout
@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully', 'success')
    return redirect(url_for('index'))

if __name__ == '__main__':
    init_db()
    app.run(debug=True)