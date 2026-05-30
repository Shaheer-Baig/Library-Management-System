-- =====================================================================
-- Library Management System - Full Setup Script
-- =====================================================================
-- Runs in one shot:
--   PART 1 - Schema       : creates all tables, constraints & indexes
--   PART 2 - Seed         : categories, publishers, admin, students
--   PART 3 - Book Catalog : ~150 curated real books across 10 genres
--   PART 4 - Demo Data    : sample loans, fines & reservations
--   PART 5 - Verification : summary queries to confirm everything loaded
--
-- =====================================================================
-- Now includes:
--   - ~150 books (international + South Asian authors)
--   - 15+ publishers (including Pakistan, India, Bangladesh)
--   - 16 categories (Novels, Poetry, Mystery, Romance, Sci-Fi, Self-Help added)
--   - 8 student accounts (with working passwords)
--   - Extended demo loans, fines, reservations
-- =====================================================================
-- Usage:
--   mysql -u root -p < setup.sql
--   (or on Windows)  Get-Content setup.sql | mysql -u root -p
--
-- Credentials after setup:
--   Admin   ->  admin   / admin@123
--   Student ->  yasir   / yasir@798
--   Student ->  shaheer / shaheer@330
--   Student ->  kiran   / kiran@342
-- =====================================================================

-- =====================================================================
-- PART 1 - SCHEMA
-- =====================================================================
-- Creates the full relational schema with:
--   + PRIMARY KEYs       (AUTO_INCREMENT surrogate keys)
--   + FOREIGN KEYs       (explicit ON DELETE / ON UPDATE rules)
--   + UNIQUE constraints (usernames, ISBN, emails)
--   + NOT NULL           (required fields)
--   + CHECK constraints  (date ordering, non-negative amounts, year ranges)
--   + DEFAULT values     (CURRENT_TIMESTAMP, status flags)
--   + ENUM types         (controlled vocabularies)
--   + INDEXes            (FK columns + frequently-filtered columns)
-- =====================================================================

DROP DATABASE IF EXISTS library_db;
CREATE DATABASE library_db
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;
USE library_db;

-- 1.1: categories - book categories (Fiction, Non-Fiction, Science, Sci-Fi)
CREATE TABLE categories (
    id           INT          AUTO_INCREMENT PRIMARY KEY,
    name         VARCHAR(50)  NOT NULL UNIQUE,
    description  VARCHAR(255) NULL
) ENGINE=InnoDB;

-- 1.2: publishers - book publishers
CREATE TABLE publishers (
    id                INT          AUTO_INCREMENT PRIMARY KEY,
    name              VARCHAR(100) NOT NULL UNIQUE,
    country           VARCHAR(50)  NULL,
    established_year  SMALLINT     NULL,
    CONSTRAINT chk_publishers_year
        CHECK (established_year IS NULL
               OR established_year BETWEEN 1400 AND 2100)
) ENGINE=InnoDB;

-- 1.3: admins - library administrators
CREATE TABLE admins (
    id          INT           AUTO_INCREMENT PRIMARY KEY,
    username    VARCHAR(20)   NOT NULL UNIQUE,
    password    VARCHAR(255)  NOT NULL,          -- werkzeug scrypt hash
    created_at  DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- 1.4: students - library members
CREATE TABLE students (
    id          INT           AUTO_INCREMENT PRIMARY KEY,
    username    VARCHAR(20)   NOT NULL UNIQUE,
    password    VARCHAR(255)  NOT NULL,
    email       VARCHAR(100)  NULL UNIQUE,
    phone       VARCHAR(20)   NULL,
    created_at  DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- 1.5: books - book catalogue
--      + category_id  FK -> categories : SET NULL on delete     --> (removing a category unlinks its books, does not delete them)
--      + publisher_id FK -> publishers : SET NULL on delete     --> (removing a category unlinks its publisher, does not delete them)
-- ---------------------------------------------------------------------
CREATE TABLE books (
    id            INT          AUTO_INCREMENT PRIMARY KEY,
    title         VARCHAR(150) NOT NULL,
    author        VARCHAR(100) NOT NULL,
    isbn          VARCHAR(20)  NOT NULL UNIQUE,
    category_id   INT          NULL,
    publisher_id  INT          NULL,
    status        ENUM('Available','Issued','Reserved') NOT NULL DEFAULT 'Available',
    added_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_books_category
        FOREIGN KEY (category_id)  REFERENCES categories(id)
        ON DELETE SET NULL ON UPDATE CASCADE,
    CONSTRAINT fk_books_publisher
        FOREIGN KEY (publisher_id) REFERENCES publishers(id)
        ON DELETE SET NULL ON UPDATE CASCADE,
    INDEX idx_books_category  (category_id),
    INDEX idx_books_publisher (publisher_id),
    INDEX idx_books_status    (status)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- 1.6: issued_books - loan records (book issued to a student)
--      + RESTRICT on book / student delete: cannot delete either while a loan record exists
--      + CHECK constraints enforce sane date ordering
-- ---------------------------------------------------------------------
CREATE TABLE issued_books (
    id           INT   AUTO_INCREMENT PRIMARY KEY,
    book_id      INT   NOT NULL,
    student_id   INT   NOT NULL,
    issue_date   DATE  NOT NULL,
    expiry_date  DATE  NOT NULL,
    return_date  DATE  NULL,
    CONSTRAINT fk_loans_book
        FOREIGN KEY (book_id)    REFERENCES books(id)
        ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_loans_student
        FOREIGN KEY (student_id) REFERENCES students(id)
        ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT chk_loan_expiry  CHECK (expiry_date  >= issue_date),
    CONSTRAINT chk_loan_return  CHECK (return_date IS NULL OR return_date >= issue_date),
    INDEX idx_loans_book    (book_id),
    INDEX idx_loans_student (student_id),
    INDEX idx_loans_expiry  (expiry_date),
    INDEX idx_loans_open    (return_date)   -- speeds up "currently borrowed" queries
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- 1.7: fines - late-return fines
--      + One fine per loan (UNIQUE on issued_book_id)
--      + CASCADE: deleting a loan also removes its fine
-- ---------------------------------------------------------------------
CREATE TABLE fines (
    id              INT           AUTO_INCREMENT PRIMARY KEY,
    issued_book_id  INT           NOT NULL UNIQUE,
    amount          DECIMAL(8,2)  NOT NULL,
    paid            BOOLEAN       NOT NULL DEFAULT FALSE,
    created_at      DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    paid_at         DATETIME      NULL,
    CONSTRAINT fk_fines_loan
        FOREIGN KEY (issued_book_id) REFERENCES issued_books(id)
        ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT chk_fines_amount   CHECK (amount >= 0),
    CONSTRAINT chk_fines_paid_at  CHECK ((paid = FALSE AND paid_at IS NULL) OR (paid = TRUE  AND paid_at IS NOT NULL)),
    INDEX idx_fines_paid (paid)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- 1.8: reservations - student reserves a currently-issued book
--      + CASCADE on both FKs: removing a book or student also removes their pending reservations
-- ---------------------------------------------------------------------
CREATE TABLE reservations (
    id           INT       AUTO_INCREMENT PRIMARY KEY,
    book_id      INT       NOT NULL,
    student_id   INT       NOT NULL,
    reserved_at  DATETIME  NOT NULL DEFAULT CURRENT_TIMESTAMP,
    status       ENUM('Pending','Fulfilled','Cancelled')
                 NOT NULL DEFAULT 'Pending',
    CONSTRAINT fk_reservations_book
        FOREIGN KEY (book_id)    REFERENCES books(id)
        ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_reservations_student
        FOREIGN KEY (student_id) REFERENCES students(id)
        ON DELETE CASCADE ON UPDATE CASCADE,
    INDEX idx_reservations_status  (status),
    INDEX idx_reservations_book    (book_id),
    INDEX idx_reservations_student (student_id)
) ENGINE=InnoDB;

-- =====================================================================
-- PART 2 - SEEDING DATA
-- =====================================================================

-- 2.1: Categories (Total = 16)
INSERT INTO categories (name, description) VALUES
    ('Uncategorised', 'Default bucket for unclassified items'),
    ('Fiction',       'Novels and imaginative literature'),
    ('Non-Fiction',   'Factual works, essays, biographies'),
    ('Science',       'Books on physical, biological, and applied sciences'),
    ('Technology',    'Computing, engineering, and tech reference'),
    ('History',       'Historical accounts and analyses'),
    ('Mathematics',   'Pure and applied mathematics'),
    ('Biography',     'Memoirs and life stories'),
    ('Children',      'Books written for younger readers'),
    ('Reference',     'Encyclopedias, dictionaries, manuals'),
    ('Novels',        'Literary works of fiction, often full-length'),
    ('Poetry',        'Verse and poetic works'),
    ('Mystery',       'Crime, detective, and whodunit stories'),
    ('Romance',       'Love stories and romantic fiction'),
    ('Science Fiction','Futuristic, technological, and space-based fiction'),
    ('Self-Help',     'Personal development, psychology, and improvement');

-- 2.2: Publishers (Total = 20)
INSERT INTO publishers (name, country, established_year) VALUES
    ('Unknown Publisher',          'Heavens',        2080),
    ('Penguin Random House',       'USA',            2013),
    ('HarperCollins',              'USA',            1989),
    ('Dover Publications',         'USA',            1941),
    ('Princeton University Press', 'USA',            1905),
    ('Oxford University Press',    'United Kingdom', 1586),
    ('Cambridge University Press', 'United Kingdom', 1534),
    ('Harvard University Press',   'USA',            1913),
    ('OReilly Media',              'USA',            1978),
    ('Pearson',                    'United Kingdom', 1844),
    ('Macmillan',                  'United Kingdom', 1843),
    ('Springer',                   'Germany',        1842),
    ('McGraw-Hill',                'USA',            1888),
    ('Ilqa Publications',          'Pakistan',       1986),
    ('Sang-e-Meel Publications',   'Pakistan',       1966),
    ('Paramount Books',            'Pakistan',       1980),
    ('Jugnoo Publications',        'Pakistan',       2005),
    ('Oxford University Press Pakistan', 'Pakistan', 1952),
    ('Penguin Random House India', 'India',          1985),
    ('Westland Publications',      'India',          1962),
    ('HarperCollins India',        'India',          1992),
    ('Aleph Book Company',         'India',          2010),
    ('Speaking Tiger Publishing',  'India',          2014),
    ('Ananda Publishers',          'India',          1957),
    ('The University Press Limited','Bangladesh',    1975),
    ('Bangla Academy',             'Bangladesh',     1955),
    ('Somoy Prokashan',            'Bangladesh',     2000),
    ('Mowla Brothers',             'Bangladesh',     1954);

-- 2.3: Admin account
INSERT INTO admins (username, password) VALUES
    ('admin', 'scrypt:32768:8:1$VbrpqybpaiEdYw2c$2497742011ec4921c571e5e4eb64c15e2488b73053e610141261c685b4be145efa167e2b38e71b109c88d20395075f7fa40d4302381fc78d367347763ede2cec');

-- ---------------------------------------------------------------------
-- 2.4: Student accounts Passwords: 
--      yasir   / yasir@798
--      shaheer / shaheer@330
--      kiran   / kiran@342
--      ahmed   / ahmed@123
--      fatima  / fatima@456
--      rahul   / rahul@789
--      saima   / saima@101
--      bilal   / bilal@202
-- ---------------------------------------------------------------------
INSERT INTO students (username, password) VALUES
    ('yasir',   'scrypt:32768:8:1$vrzzV6V9CsZWmxhp$d19cc8dd8309ae58de3933489fe83b320b982a52cbf1ce453d558a18554b5d4ee80bfcc751d6b3c77b55195db1adec94a03ca49e84507dd7ca037288da0f8977'),
    ('shaheer', 'scrypt:32768:8:1$VsphJhDqB6Ooaby0$c048934f4293e790f7e4e2b8a438a6cc2a3136bb50c05a0fc73970a55519576e55335d3f78f47ffdfd2644edc8a3464fb26a8074975d5a991bfcaf5e40374071'),
    ('kiran',   'scrypt:32768:8:1$TW6gXqBMuhJ4nf3W$4104183dc6fcaf13d29f2243b4d14c382626e8275f730ce87bcc80d02220c8ec403b1e102c6e7ea043c390231d429cfe22c4af2e890708d363cdf48f3e32db98'),
    ('ahmed',   'scrypt:32768:8:1$yvUJtg4jyQcDLZ7P$8f36bf677bceba563afc0c2ba75e5b3dc128cf4d87a0f621ae4656a14b85deb54f6b380c7d69cb1d435ec091b16ab713ae033e6b7b5bdf36fb0d778c8327ae4b'),
    ('fatima',  'scrypt:32768:8:1$p7DPVetbbvM2sOiP$3a2f03b3122c3437c3c7c7e74276db1b359096b8a5088a8087e009ee729dbecf46cda09298b1a0fec83ae94174e2644aa03d5a0f7f25d6b636f8b00c0d54a16b'),
    ('rahul',   'scrypt:32768:8:1$DGRo0mXCPSsiXtkp$859afe0acd91b83aad44c42655deda0e3c1c7a1ed6e4dde4b7678fcdfb0f22fd9d44564555bc9eb01727b90bf2da994c01b1d545b376e3c5d2debf3cc9ee5374'),
    ('saima',   'scrypt:32768:8:1$P7dmCjYGHGcFUxBB$220c0121e463b63588ee1b1c068aed977d90508e089a977ca6d1f61718690d1e8ea1bcd22be7c0c20de93d6c0d1ece570357078afa976852a40d52cb750c8516'),
    ('bilal',   'scrypt:32768:8:1$6UzUiy8u1DzmaYSD$185a4e4a7082b4055e61d1ebd23e7e02fd3e7d018f58e1b255e8a6aea2b10ee2a63cba0cdafc7ccef4761a958b6b119a8e0282986cc23fdb6edd490aba2e84ec');

-- =====================================================================
-- PART 3 - BOOK CATALOG (~150 books)
-- =====================================================================

INSERT INTO books (title, author, isbn, category_id, publisher_id, status) VALUES

-- ==== Fiction (Total = 10) ====
('1984', 'George Orwell', '9780451524935', (SELECT id FROM categories WHERE name = 'Fiction'), (SELECT id FROM publishers WHERE name = 'Penguin Random House'), 'Available'),
('To Kill a Mockingbird', 'Harper Lee', '9780061120084', (SELECT id FROM categories WHERE name = 'Fiction'), (SELECT id FROM publishers WHERE name = 'HarperCollins'), 'Available'),
('The Great Gatsby', 'F. Scott Fitzgerald', '9780743273565', (SELECT id FROM categories WHERE name = 'Fiction'), (SELECT id FROM publishers WHERE name = 'Penguin Random House'), 'Available'),
('Pride and Prejudice', 'Jane Austen', '9780141439518', (SELECT id FROM categories WHERE name = 'Fiction'), (SELECT id FROM publishers WHERE name = 'Penguin Random House'), 'Available'),
('Animal Farm', 'George Orwell', '9780451526342', (SELECT id FROM categories WHERE name = 'Fiction'), (SELECT id FROM publishers WHERE name = 'Penguin Random House'), 'Available'),
('Brave New World', 'Aldous Huxley', '9780060850524', (SELECT id FROM categories WHERE name = 'Fiction'), (SELECT id FROM publishers WHERE name = 'HarperCollins'), 'Available'),
('The Catcher in the Rye', 'J.D. Salinger', '9780316769488', (SELECT id FROM categories WHERE name = 'Fiction'), (SELECT id FROM publishers WHERE name = 'Penguin Random House'), 'Available'),
('Moby Dick', 'Herman Melville', '9781503280786', (SELECT id FROM categories WHERE name = 'Fiction'), (SELECT id FROM publishers WHERE name = 'Pearson'), 'Available'),
('War and Peace', 'Leo Tolstoy', '9780199232765', (SELECT id FROM categories WHERE name = 'Fiction'), (SELECT id FROM publishers WHERE name = 'Oxford University Press'), 'Available'),
('The Alchemist', 'Paulo Coelho', '9780062502174', (SELECT id FROM categories WHERE name = 'Fiction'), (SELECT id FROM publishers WHERE name = 'HarperCollins'), 'Available'),

-- ==== Non-Fiction (Total = 10) ====
('Sapiens: A Brief History of Humankind', 'Yuval Noah Harari', '9780062316097', (SELECT id FROM categories WHERE name = 'Non-Fiction'), (SELECT id FROM publishers WHERE name = 'HarperCollins'), 'Available'),
('Educated', 'Tara Westover', '9780399590504', (SELECT id FROM categories WHERE name = 'Non-Fiction'), (SELECT id FROM publishers WHERE name = 'Penguin Random House'), 'Available'),
('Thinking, Fast and Slow', 'Daniel Kahneman', '9780374533557', (SELECT id FROM categories WHERE name = 'Non-Fiction'), (SELECT id FROM publishers WHERE name = 'Macmillan'), 'Available'),
('Becoming', 'Michelle Obama', '9781524763138', (SELECT id FROM categories WHERE name = 'Non-Fiction'), (SELECT id FROM publishers WHERE name = 'Penguin Random House'), 'Available'),
('The Immortal Life of Henrietta Lacks', 'Rebecca Skloot', '9781400052189', (SELECT id FROM categories WHERE name = 'Non-Fiction'), (SELECT id FROM publishers WHERE name = 'Macmillan'), 'Available'),
('The Wright Brothers', 'David McCullough', '9781476728742', (SELECT id FROM categories WHERE name = 'Non-Fiction'), (SELECT id FROM publishers WHERE name = 'Penguin Random House'), 'Available'),
('The Second Sex', 'Simone de Beauvoir', '9780679749514', (SELECT id FROM categories WHERE name = 'Non-Fiction'), (SELECT id FROM publishers WHERE name = 'Penguin Random House'), 'Available'),
('Homo Deus', 'Yuval Noah Harari', '9780062464316', (SELECT id FROM categories WHERE name = 'Non-Fiction'), (SELECT id FROM publishers WHERE name = 'HarperCollins'), 'Available'),
('The Art of War', 'Sun Tzu', '9781590302259', (SELECT id FROM categories WHERE name = 'Non-Fiction'), (SELECT id FROM publishers WHERE name = 'Penguin Random House'), 'Available'),
('Outliers', 'Malcolm Gladwell', '9780316017930', (SELECT id FROM categories WHERE name = 'Non-Fiction'), (SELECT id FROM publishers WHERE name = 'Penguin Random House'), 'Available'),

-- ==== Science (Total = 10) ====
('A Brief History of Time', 'Stephen Hawking', '9780553380163', (SELECT id FROM categories WHERE name = 'Science'), (SELECT id FROM publishers WHERE name = 'Penguin Random House'), 'Available'),
('The Selfish Gene', 'Richard Dawkins', '9780198788607', (SELECT id FROM categories WHERE name = 'Science'), (SELECT id FROM publishers WHERE name = 'Oxford University Press'), 'Available'),
('Cosmos', 'Carl Sagan', '9780345539434', (SELECT id FROM categories WHERE name = 'Science'), (SELECT id FROM publishers WHERE name = 'Penguin Random House'), 'Available'),
('The Gene', 'Siddhartha Mukherjee', '9781476733524', (SELECT id FROM categories WHERE name = 'Science'), (SELECT id FROM publishers WHERE name = 'Penguin Random House'), 'Available'),
('The Elegant Universe', 'Brian Greene', '9780375708114', (SELECT id FROM categories WHERE name = 'Science'), (SELECT id FROM publishers WHERE name = 'Macmillan'), 'Available'),
('The Double Helix', 'James Watson', '9780743216302', (SELECT id FROM categories WHERE name = 'Science'), (SELECT id FROM publishers WHERE name = 'Penguin Random House'), 'Available'),
('Silent Spring', 'Rachel Carson', '9780618249060', (SELECT id FROM categories WHERE name = 'Science'), (SELECT id FROM publishers WHERE name = 'HarperCollins'), 'Available'),
('The Origin of Species', 'Charles Darwin', '9781509827695', (SELECT id FROM categories WHERE name = 'Science'), (SELECT id FROM publishers WHERE name = 'Macmillan'), 'Available'),
('The Man Who Knew Infinity', 'Robert Kanigel', '9780671638489', (SELECT id FROM categories WHERE name = 'Science'), (SELECT id FROM publishers WHERE name = 'Penguin Random House'), 'Available'),
('The Future of Humanity', 'Michio Kaku', '9780385542760', (SELECT id FROM categories WHERE name = 'Science'), (SELECT id FROM publishers WHERE name = 'Penguin Random House'), 'Available'),

-- ==== Technology (Total = 10) ====
('Clean Code', 'Robert C. Martin', '9780132350884', (SELECT id FROM categories WHERE name = 'Technology'), (SELECT id FROM publishers WHERE name = 'Pearson'), 'Available'),
('The Pragmatic Programmer', 'Andrew Hunt, David Thomas', '9780135957059', (SELECT id FROM categories WHERE name = 'Technology'), (SELECT id FROM publishers WHERE name = 'Pearson'), 'Available'),
('Design Patterns', 'Gamma, Helm, Johnson, Vlissides', '9780201633610', (SELECT id FROM categories WHERE name = 'Technology'), (SELECT id FROM publishers WHERE name = 'Pearson'), 'Available'),
('Introduction to Algorithms', 'Cormen, Leiserson, Rivest, Stein', '9780262033848', (SELECT id FROM categories WHERE name = 'Technology'), (SELECT id FROM publishers WHERE name = 'Macmillan'), 'Available'),
('Computer Networks', 'Andrew S. Tanenbaum', '9780132126953', (SELECT id FROM categories WHERE name = 'Technology'), (SELECT id FROM publishers WHERE name = 'Pearson'), 'Available'),
('Database System Concepts', 'Silberschatz, Korth, Sudarshan', '9780078022159', (SELECT id FROM categories WHERE name = 'Technology'), (SELECT id FROM publishers WHERE name = 'McGraw-Hill'), 'Available'),
('Artificial Intelligence: A Modern Approach', 'Russell, Norvig', '9780136042594', (SELECT id FROM categories WHERE name = 'Technology'), (SELECT id FROM publishers WHERE name = 'Pearson'), 'Available'),
('The Mythical Man-Month', 'Frederick Brooks', '9780201835953', (SELECT id FROM categories WHERE name = 'Technology'), (SELECT id FROM publishers WHERE name = 'Pearson'), 'Available'),
('Code: The Hidden Language', 'Charles Petzold', '9780735611313', (SELECT id FROM categories WHERE name = 'Technology'), (SELECT id FROM publishers WHERE name = 'OReilly Media'), 'Available'),
('The C Programming Language', 'Kernighan, Ritchie', '9780131103627', (SELECT id FROM categories WHERE name = 'Technology'), (SELECT id FROM publishers WHERE name = 'Pearson'), 'Available'),

-- ==== History (Total = 10) ====
('Guns, Germs, and Steel', 'Jared Diamond', '9780393354324', (SELECT id FROM categories WHERE name = 'History'), (SELECT id FROM publishers WHERE name = 'Pearson'), 'Available'),
('A People''s History of the United States', 'Howard Zinn', '9780062397348', (SELECT id FROM categories WHERE name = 'History'), (SELECT id FROM publishers WHERE name = 'HarperCollins'), 'Available'),
('The Silk Roads', 'Peter Frankopan', '9781101912379', (SELECT id FROM categories WHERE name = 'History'), (SELECT id FROM publishers WHERE name = 'Penguin Random House'), 'Available'),
('The History of the Ancient World', 'Susan Wise Bauer', '9780393059748', (SELECT id FROM categories WHERE name = 'History'), (SELECT id FROM publishers WHERE name = 'Macmillan'), 'Available'),
('Postwar', 'Tony Judt', '9780143037750', (SELECT id FROM categories WHERE name = 'History'), (SELECT id FROM publishers WHERE name = 'Penguin Random House'), 'Available'),
('The Swerve', 'Stephen Greenblatt', '9780393343403', (SELECT id FROM categories WHERE name = 'History'), (SELECT id FROM publishers WHERE name = 'Macmillan'), 'Available'),
('The Conquest of New Spain', 'Bernal Diaz', '9780140441239', (SELECT id FROM categories WHERE name = 'History'), (SELECT id FROM publishers WHERE name = 'Penguin Random House'), 'Available'),
('India After Gandhi', 'Ramachandra Guha', '9780060958589', (SELECT id FROM categories WHERE name = 'History'), (SELECT id FROM publishers WHERE name = 'HarperCollins'), 'Available'),
('Pakistan: A Hard Country', 'Anatol Lieven', '9781610390231', (SELECT id FROM categories WHERE name = 'History'), (SELECT id FROM publishers WHERE name = 'Penguin Random House'), 'Available'),
('Bangladesh: A Legacy of Blood', 'Anthony Mascarenhas', '9780340196201', (SELECT id FROM categories WHERE name = 'History'), (SELECT id FROM publishers WHERE name = 'Pearson'), 'Available'),

-- ==== Mathematics (Total = 10) ====
('Calculus: Early Transcendentals', 'James Stewart', '9781285740621', (SELECT id FROM categories WHERE name = 'Mathematics'), (SELECT id FROM publishers WHERE name = 'Pearson'), 'Available'),
('Linear Algebra Done Right', 'Sheldon Axler', '9783319110790', (SELECT id FROM categories WHERE name = 'Mathematics'), (SELECT id FROM publishers WHERE name = 'Springer'), 'Available'),
('The Princeton Companion to Mathematics', 'Gowers et al.', '9780691118802', (SELECT id FROM categories WHERE name = 'Mathematics'), (SELECT id FROM publishers WHERE name = 'Princeton University Press'), 'Available'),
('How to Solve It', 'George Polya', '9780691164076', (SELECT id FROM categories WHERE name = 'Mathematics'), (SELECT id FROM publishers WHERE name = 'Penguin Random House'), 'Available'),
('Godel, Escher, Bach', 'Douglas Hofstadter', '9780465026562', (SELECT id FROM categories WHERE name = 'Mathematics'), (SELECT id FROM publishers WHERE name = 'Macmillan'), 'Available'),
('The Art of Mathematics', 'Bela Bollobas', '9781107636185', (SELECT id FROM categories WHERE name = 'Mathematics'), (SELECT id FROM publishers WHERE name = 'Cambridge University Press'), 'Available'),
('Measurement', 'Paul Lockhart', '9780674057555', (SELECT id FROM categories WHERE name = 'Mathematics'), (SELECT id FROM publishers WHERE name = 'Harvard University Press'), 'Available'),
('A Mathematician''s Apology', 'G.H. Hardy', '9780521427067', (SELECT id FROM categories WHERE name = 'Mathematics'), (SELECT id FROM publishers WHERE name = 'Cambridge University Press'), 'Available'),
('The Drunkard''s Walk', 'Leonard Mlodinow', '9780307275174', (SELECT id FROM categories WHERE name = 'Mathematics'), (SELECT id FROM publishers WHERE name = 'Penguin Random House'), 'Available'),
('Number Theory', 'George Andrews', '9780486682525', (SELECT id FROM categories WHERE name = 'Mathematics'), (SELECT id FROM publishers WHERE name = 'Dover Publications'), 'Available'),

-- ==== Biography (Total = 10) ====
('Steve Jobs', 'Walter Isaacson', '9781451648539', (SELECT id FROM categories WHERE name = 'Biography'), (SELECT id FROM publishers WHERE name = 'Macmillan'), 'Available'),
('The Diary of a Young Girl', 'Anne Frank', '9780553296983', (SELECT id FROM categories WHERE name = 'Biography'), (SELECT id FROM publishers WHERE name = 'Penguin Random House'), 'Available'),
('Long Walk to Freedom', 'Nelson Mandela', '9780316548182', (SELECT id FROM categories WHERE name = 'Biography'), (SELECT id FROM publishers WHERE name = 'Macmillan'), 'Available'),
('The Autobiography of Malcolm X', 'Malcolm X', '9780345350688', (SELECT id FROM categories WHERE name = 'Biography'), (SELECT id FROM publishers WHERE name = 'Penguin Random House'), 'Available'),
('Einstein', 'Walter Isaacson', '9780743264747', (SELECT id FROM categories WHERE name = 'Biography'), (SELECT id FROM publishers WHERE name = 'Macmillan'), 'Available'),
('I Am Malala', 'Malala Yousafzai', '9780316322423', (SELECT id FROM categories WHERE name = 'Biography'), (SELECT id FROM publishers WHERE name = 'Penguin Random House'), 'Available'),
('The Story of My Experiments with Truth', 'Mahatma Gandhi', '9780807059098', (SELECT id FROM categories WHERE name = 'Biography'), (SELECT id FROM publishers WHERE name = 'Penguin Random House'), 'Available'),
('Jinnah: India-Partition-Independence', 'Jaswant Singh', '9788129112415', (SELECT id FROM categories WHERE name = 'Biography'), (SELECT id FROM publishers WHERE name = 'Penguin Random House India'), 'Available'),
('Sheikh Mujibur Rahman: The Unfinished Memoirs', 'Sheikh Mujibur Rahman', '9789845062082', (SELECT id FROM categories WHERE name = 'Biography'), (SELECT id FROM publishers WHERE name = 'The University Press Limited'), 'Available'),
('Wings of Fire', 'A.P.J. Abdul Kalam', '9788173711466', (SELECT id FROM categories WHERE name = 'Biography'), (SELECT id FROM publishers WHERE name = 'Dover Publications'), 'Available'),

-- ==== Children (Total = 10) ====
('Charlotte''s Web', 'E. B. White', '9780064400558', (SELECT id FROM categories WHERE name = 'Children'), (SELECT id FROM publishers WHERE name = 'HarperCollins'), 'Available'),
('Where the Wild Things Are', 'Maurice Sendak', '9780064431781', (SELECT id FROM categories WHERE name = 'Children'), (SELECT id FROM publishers WHERE name = 'HarperCollins'), 'Available'),
('The Very Hungry Caterpillar', 'Eric Carle', '9780399226908', (SELECT id FROM categories WHERE name = 'Children'), (SELECT id FROM publishers WHERE name = 'Penguin Random House'), 'Available'),
('Green Eggs and Ham', 'Dr. Seuss', '9780394800165', (SELECT id FROM categories WHERE name = 'Children'), (SELECT id FROM publishers WHERE name = 'Penguin Random House'), 'Available'),
('Goodnight Moon', 'Margaret Wise Brown', '9780694003617', (SELECT id FROM categories WHERE name = 'Children'), (SELECT id FROM publishers WHERE name = 'HarperCollins'), 'Available'),
('The Tale of Peter Rabbit', 'Beatrix Potter', '9780723247708', (SELECT id FROM categories WHERE name = 'Children'), (SELECT id FROM publishers WHERE name = 'Penguin Random House'), 'Available'),
('Matilda', 'Roald Dahl', '9780142410370', (SELECT id FROM categories WHERE name = 'Children'), (SELECT id FROM publishers WHERE name = 'Penguin Random House'), 'Available'),
('The Little Prince', 'Antoine de Saint-Exupery', '9780156012195', (SELECT id FROM categories WHERE name = 'Children'), (SELECT id FROM publishers WHERE name = 'HarperCollins'), 'Available'),
('Alice''s Adventures in Wonderland', 'Lewis Carroll', '9780486275437', (SELECT id FROM categories WHERE name = 'Children'), (SELECT id FROM publishers WHERE name = 'Penguin Random House'), 'Available'),
('The Hobbit', 'J.R.R. Tolkien', '9780547928227', (SELECT id FROM categories WHERE name = 'Children'), (SELECT id FROM publishers WHERE name = 'HarperCollins'), 'Available'),

-- ==== Reference (Total = 10) ====
('Oxford English Dictionary', 'Oxford University Press', '9780199571123', (SELECT id FROM categories WHERE name = 'Reference'), (SELECT id FROM publishers WHERE name = 'Oxford University Press'), 'Available'),
('The Cambridge Encyclopedia', 'David Crystal', '9780521823913', (SELECT id FROM categories WHERE name = 'Reference'), (SELECT id FROM publishers WHERE name = 'Cambridge University Press'), 'Available'),
('Encyclopaedia Britannica', 'Various', '9780852294732', (SELECT id FROM categories WHERE name = 'Reference'), (SELECT id FROM publishers WHERE name = 'Unknown Publisher'), 'Available'),
('The Elements of Style', 'Strunk, White', '9780205309023', (SELECT id FROM categories WHERE name = 'Reference'), (SELECT id FROM publishers WHERE name = 'Pearson'), 'Available'),
('Chicago Manual of Style', 'University of Chicago', '9780226104201', (SELECT id FROM categories WHERE name = 'Reference'), (SELECT id FROM publishers WHERE name = 'Unknown Publisher'), 'Available'),
('Roget''s Thesaurus', 'Peter Roget', '9780140515039', (SELECT id FROM categories WHERE name = 'Reference'), (SELECT id FROM publishers WHERE name = 'Penguin Random House'), 'Available'),
('World Almanac', 'Sarah Janssen', '9781600572234', (SELECT id FROM categories WHERE name = 'Reference'), (SELECT id FROM publishers WHERE name = 'Unknown Publisher'), 'Available'),
('The Merriam-Webster Dictionary', 'Merriam-Webster', '9780877792956', (SELECT id FROM categories WHERE name = 'Reference'), (SELECT id FROM publishers WHERE name = 'Unknown Publisher'), 'Available'),
('The Oxford Companion to English Literature', 'Margaret Drabble', '9780198662440', (SELECT id FROM categories WHERE name = 'Reference'), (SELECT id FROM publishers WHERE name = 'Oxford University Press'), 'Available'),
('CRC Handbook of Chemistry and Physics', 'CRC Press', '9781498761145', (SELECT id FROM categories WHERE name = 'Reference'), (SELECT id FROM publishers WHERE name = 'Unknown Publisher'), 'Available'),

-- ==== Novels (Total = 10) ====
('Moth Smoke', 'Mohsin Hamid', '9780312420901', (SELECT id FROM categories WHERE name = 'Novels'), (SELECT id FROM publishers WHERE name = 'Penguin Random House'), 'Available'),
('The Reluctant Fundamentalist', 'Mohsin Hamid', '9780151013043', (SELECT id FROM categories WHERE name = 'Novels'), (SELECT id FROM publishers WHERE name = 'Penguin Random House'), 'Available'),
('The God of Small Things', 'Arundhati Roy', '9780812979657', (SELECT id FROM categories WHERE name = 'Novels'), (SELECT id FROM publishers WHERE name = 'Penguin Random House India'), 'Available'),
('A Suitable Boy', 'Vikram Seth', '9780060786526', (SELECT id FROM categories WHERE name = 'Novels'), (SELECT id FROM publishers WHERE name = 'HarperCollins'), 'Available'),
('The White Tiger', 'Aravind Adiga', '9781416562603', (SELECT id FROM categories WHERE name = 'Novels'), (SELECT id FROM publishers WHERE name = 'Macmillan'), 'Available'),
('Midnight''s Children', 'Salman Rushdie', '9780812976533', (SELECT id FROM categories WHERE name = 'Novels'), (SELECT id FROM publishers WHERE name = 'Penguin Random House'), 'Available'),
('A Golden Age', 'Tahmima Anam', '9780061478741', (SELECT id FROM categories WHERE name = 'Novels'), (SELECT id FROM publishers WHERE name = 'HarperCollins'), 'Available'),
('The Good Muslim', 'Tahmima Anam', '9780061478765', (SELECT id FROM categories WHERE name = 'Novels'), (SELECT id FROM publishers WHERE name = 'HarperCollins'), 'Available'),
('Sea of Poppies', 'Amitav Ghosh', '9780312428594', (SELECT id FROM categories WHERE name = 'Novels'), (SELECT id FROM publishers WHERE name = 'Penguin Random House'), 'Available'),
('The Glass Palace', 'Amitav Ghosh', '9780375758775', (SELECT id FROM categories WHERE name = 'Novels'), (SELECT id FROM publishers WHERE name = 'Penguin Random House'), 'Available'),

-- ==== Poetry (Total = 10) ====
('The Essential Rumi', 'Jalal ad-Din Rumi', '9780062509593', (SELECT id FROM categories WHERE name = 'Poetry'), (SELECT id FROM publishers WHERE name = 'HarperCollins'), 'Available'),
('The Waste Land', 'T.S. Eliot', '9780156948777', (SELECT id FROM categories WHERE name = 'Poetry'), (SELECT id FROM publishers WHERE name = 'Penguin Random House'), 'Available'),
('Leaves of Grass', 'Walt Whitman', '9780194505271', (SELECT id FROM categories WHERE name = 'Poetry'), (SELECT id FROM publishers WHERE name = 'Oxford University Press'), 'Available'),
('The Complete Poems of Emily Dickinson', 'Emily Dickinson', '9780316184137', (SELECT id FROM categories WHERE name = 'Poetry'), (SELECT id FROM publishers WHERE name = 'Penguin Random House'), 'Available'),
('Shah Jo Risalo', 'Shah Abdul Latif Bhittai', '9789693515684', (SELECT id FROM categories WHERE name = 'Poetry'), (SELECT id FROM publishers WHERE name = 'Sang-e-Meel Publications'), 'Available'),
('Bangla Poetry: Selected Works', 'Kazi Nazrul Islam', '9789840801268', (SELECT id FROM categories WHERE name = 'Poetry'), (SELECT id FROM publishers WHERE name = 'Bangla Academy'), 'Available'),
('Gitanjali', 'Rabindranath Tagore', '9780141182827', (SELECT id FROM categories WHERE name = 'Poetry'), (SELECT id FROM publishers WHERE name = 'Penguin Random House India'), 'Available'),
('Milk and Honey', 'Rupi Kaur', '9781449474256', (SELECT id FROM categories WHERE name = 'Poetry'), (SELECT id FROM publishers WHERE name = 'Penguin Random House'), 'Available'),
('The Sun and Her Flowers', 'Rupi Kaur', '9781449486792', (SELECT id FROM categories WHERE name = 'Poetry'), (SELECT id FROM publishers WHERE name = 'Penguin Random House'), 'Available'),
('The Prophet', 'Kahlil Gibran', '9780394404288', (SELECT id FROM categories WHERE name = 'Poetry'), (SELECT id FROM publishers WHERE name = 'Penguin Random House'), 'Available'),

-- ==== Mystery (Total = 10) ====
('The Hound of the Baskervilles', 'Arthur Conan Doyle', '9780553212365', (SELECT id FROM categories WHERE name = 'Mystery'), (SELECT id FROM publishers WHERE name = 'Penguin Random House'), 'Available'),
('Murder on the Orient Express', 'Agatha Christie', '9780062073495', (SELECT id FROM categories WHERE name = 'Mystery'), (SELECT id FROM publishers WHERE name = 'HarperCollins'), 'Available'),
('The Girl with the Dragon Tattoo', 'Stieg Larsson', '9780307454546', (SELECT id FROM categories WHERE name = 'Mystery'), (SELECT id FROM publishers WHERE name = 'Penguin Random House'), 'Available'),
('Gone Girl', 'Gillian Flynn', '9780307588371', (SELECT id FROM categories WHERE name = 'Mystery'), (SELECT id FROM publishers WHERE name = 'Penguin Random House'), 'Available'),
('The Da Vinci Code', 'Dan Brown', '9780385504201', (SELECT id FROM categories WHERE name = 'Mystery'), (SELECT id FROM publishers WHERE name = 'Penguin Random House'), 'Available'),
('The Name of the Rose', 'Umberto Eco', '9780156001311', (SELECT id FROM categories WHERE name = 'Mystery'), (SELECT id FROM publishers WHERE name = 'Penguin Random House'), 'Available'),
('The Big Sleep', 'Raymond Chandler', '9780394758282', (SELECT id FROM categories WHERE name = 'Mystery'), (SELECT id FROM publishers WHERE name = 'Penguin Random House'), 'Available'),
('The Maltese Falcon', 'Dashiell Hammett', '9780679742645', (SELECT id FROM categories WHERE name = 'Mystery'), (SELECT id FROM publishers WHERE name = 'Penguin Random House'), 'Available'),
('The Postman Always Rings Twice', 'James M. Cain', '9780679723255', (SELECT id FROM categories WHERE name = 'Mystery'), (SELECT id FROM publishers WHERE name = 'Penguin Random House'), 'Available'),
('And Then There Were None', 'Agatha Christie', '9780062073488', (SELECT id FROM categories WHERE name = 'Mystery'), (SELECT id FROM publishers WHERE name = 'HarperCollins'), 'Available'),

-- ==== Romance (Total = 10) ====
('Sense and Sensibility', 'Jane Austen', '9780141439662', (SELECT id FROM categories WHERE name = 'Romance'), (SELECT id FROM publishers WHERE name = 'Penguin Random House'), 'Available'),
('Jane Eyre', 'Charlotte Bronte', '9780141441146', (SELECT id FROM categories WHERE name = 'Romance'), (SELECT id FROM publishers WHERE name = 'Penguin Random House'), 'Available'),
('Wuthering Heights', 'Emily Bronte', '9780141439556', (SELECT id FROM categories WHERE name = 'Romance'), (SELECT id FROM publishers WHERE name = 'Penguin Random House'), 'Available'),
('The Notebook', 'Nicholas Sparks', '9780446605236', (SELECT id FROM categories WHERE name = 'Romance'), (SELECT id FROM publishers WHERE name = 'Penguin Random House'), 'Available'),
('Me Before You', 'Jojo Moyes', '9780143124542', (SELECT id FROM categories WHERE name = 'Romance'), (SELECT id FROM publishers WHERE name = 'Penguin Random House'), 'Available'),
('Outlander', 'Diana Gabaldon', '9780440212560', (SELECT id FROM categories WHERE name = 'Romance'), (SELECT id FROM publishers WHERE name = 'Penguin Random House'), 'Available'),
('The Fault in Our Stars', 'John Green', '9780142424179', (SELECT id FROM categories WHERE name = 'Romance'), (SELECT id FROM publishers WHERE name = 'Penguin Random House'), 'Available'),
('Eleanor & Park', 'Rainbow Rowell', '9781250012579', (SELECT id FROM categories WHERE name = 'Romance'), (SELECT id FROM publishers WHERE name = 'Macmillan'), 'Available'),
('The Rosie Project', 'Graeme Simsion', '9781476729091', (SELECT id FROM categories WHERE name = 'Romance'), (SELECT id FROM publishers WHERE name = 'Penguin Random House'), 'Available'),
('Love Story', 'Erich Segal', '9780061000188', (SELECT id FROM categories WHERE name='Romance'), (SELECT id FROM publishers WHERE name='HarperCollins'), 'Available'),

-- ==== Science Fiction (Total = 10) ====
('Dune', 'Frank Herbert', '9780441013593', (SELECT id FROM categories WHERE name = 'Science Fiction'), (SELECT id FROM publishers WHERE name = 'Penguin Random House'), 'Available'),
('Neuromancer', 'William Gibson', '9780441569595', (SELECT id FROM categories WHERE name = 'Science Fiction'), (SELECT id FROM publishers WHERE name = 'Penguin Random House'), 'Available'),
('Foundation', 'Isaac Asimov', '9780553293357', (SELECT id FROM categories WHERE name = 'Science Fiction'), (SELECT id FROM publishers WHERE name = 'Penguin Random House'), 'Available'),
('The Left Hand of Darkness', 'Ursula K. Le Guin', '9780441007318', (SELECT id FROM categories WHERE name = 'Science Fiction'), (SELECT id FROM publishers WHERE name = 'Penguin Random House'), 'Available'),
('Snow Crash', 'Neal Stephenson', '9780553380958', (SELECT id FROM categories WHERE name = 'Science Fiction'), (SELECT id FROM publishers WHERE name = 'Penguin Random House'), 'Available'),
('The Martian', 'Andy Weir', '9780553418026', (SELECT id FROM categories WHERE name = 'Science Fiction'), (SELECT id FROM publishers WHERE name = 'Penguin Random House'), 'Available'),
('Ready Player One', 'Ernest Cline', '9780307887443', (SELECT id FROM categories WHERE name = 'Science Fiction'), (SELECT id FROM publishers WHERE name = 'Penguin Random House'), 'Available'),
('Hyperion', 'Dan Simmons', '9780553283686', (SELECT id FROM categories WHERE name = 'Science Fiction'), (SELECT id FROM publishers WHERE name = 'Penguin Random House'), 'Available'),
('Ender''s Game', 'Orson Scott Card', '9780812550702', (SELECT id FROM categories WHERE name = 'Science Fiction'), (SELECT id FROM publishers WHERE name = 'Macmillan'), 'Available'),
('The Three-Body Problem', 'Liu Cixin', '9780765382030', (SELECT id FROM categories WHERE name = 'Science Fiction'), (SELECT id FROM publishers WHERE name = 'Macmillan'), 'Available'),

-- ==== Self-Help (Total = 10) ====
('The 7 Habits of Highly Effective People', 'Stephen Covey', '9780743269513', (SELECT id FROM categories WHERE name = 'Self-Help'), (SELECT id FROM publishers WHERE name = 'Penguin Random House'), 'Available'),
('How to Win Friends and Influence People', 'Dale Carnegie', '9780671027032', (SELECT id FROM categories WHERE name = 'Self-Help'), (SELECT id FROM publishers WHERE name = 'Penguin Random House'), 'Available'),
('The Power of Now', 'Eckhart Tolle', '9781577314806', (SELECT id FROM categories WHERE name = 'Self-Help'), (SELECT id FROM publishers WHERE name = 'Penguin Random House'), 'Available'),
('Atomic Habits', 'James Clear', '9780735211292', (SELECT id FROM categories WHERE name = 'Self-Help'), (SELECT id FROM publishers WHERE name = 'Penguin Random House'), 'Available'),
('The Subtle Art of Not Giving a F*ck', 'Mark Manson', '9780062457714', (SELECT id FROM categories WHERE name = 'Self-Help'), (SELECT id FROM publishers WHERE name = 'HarperCollins'), 'Available'),
('Daring Greatly', 'Brene Brown', '9781592408412', (SELECT id FROM categories WHERE name = 'Self-Help'), (SELECT id FROM publishers WHERE name = 'Penguin Random House'), 'Available'),
('Mindset', 'Carol S. Dweck', '9780345472328', (SELECT id FROM categories WHERE name = 'Self-Help'), (SELECT id FROM publishers WHERE name = 'Penguin Random House'), 'Available'),
('The Four Agreements', 'Don Miguel Ruiz', '9781878424310', (SELECT id FROM categories WHERE name = 'Self-Help'), (SELECT id FROM publishers WHERE name = 'Penguin Random House'), 'Available'),
('You Are a Badass', 'Jen Sincero', '9781529343762', (SELECT id FROM categories WHERE name = 'Self-Help'), (SELECT id FROM publishers WHERE name = 'Penguin Random House'), 'Available'),
('The 5 AM Club', 'Robin Sharma', '9781443456623', (SELECT id FROM categories WHERE name = 'Self-Help'), (SELECT id FROM publishers WHERE name = 'HarperCollins'), 'Available');

-- =====================================================================
-- PART 4 - DEMO DATA (greatly expanded)
-- =====================================================================
-- We now have 8 students and many books. We'll add:
--   - 20 active/returned loans covering many students
--   - Additional fines (some paid, some unpaid)
--   - More reservations (pending, fulfilled, cancelled)
-- =====================================================================

-- First, mark a few books as Issued to create active loans
UPDATE books SET status = 'Issued' WHERE isbn IN (
    '9780451524935',   -- 1984 (yasir)
    '9780132350884',   -- Clean Code (shaheer)
    '9780062316097',   -- Sapiens (ahmed)
    '9780312420901',   -- Moth Smoke (fatima)
    '9780441013593',   -- Dune (rahul)
    '9780553212365'   -- Hound of Baskervilles (saima)
);

-- ---------------------------------------------------------------------
-- === Loans taken by the students ===
-- ---------------------------------------------------------------------

-- A) yasir - '1984' - active, not yet due
INSERT INTO issued_books (book_id, student_id, issue_date, expiry_date, return_date)
VALUES (
    (SELECT id FROM books    WHERE isbn     = '9780451524935'),
    (SELECT id FROM students WHERE username = 'yasir'),
    DATE_SUB(CURDATE(), INTERVAL 5  DAY),
    DATE_ADD(CURDATE(), INTERVAL 9  DAY),
    NULL
);

-- B) shaheer - 'Clean Code' - active, OVERDUE (7 days past due)
INSERT INTO issued_books (book_id, student_id, issue_date, expiry_date, return_date)
VALUES (
    (SELECT id FROM books    WHERE isbn     = '9780132350884'),
    (SELECT id FROM students WHERE username = 'shaheer'),
    DATE_SUB(CURDATE(), INTERVAL 21 DAY),
    DATE_SUB(CURDATE(), INTERVAL 7  DAY),
    NULL
);

-- C) kiran - 'Cosmos' - returned on time
INSERT INTO issued_books (book_id, student_id, issue_date, expiry_date, return_date)
VALUES (
    (SELECT id FROM books    WHERE isbn     = '9780345539434'),
    (SELECT id FROM students WHERE username = 'kiran'),
    DATE_SUB(CURDATE(), INTERVAL 20 DAY),
    DATE_SUB(CURDATE(), INTERVAL 6  DAY),
    DATE_SUB(CURDATE(), INTERVAL 8  DAY)
);

-- D) yasir - 'Sapiens' - returned 3 days late, fine NOT paid
INSERT INTO issued_books (book_id, student_id, issue_date, expiry_date, return_date)
VALUES (
    (SELECT id FROM books    WHERE isbn     = '9780062316097'),
    (SELECT id FROM students WHERE username = 'yasir'),
    DATE_SUB(CURDATE(), INTERVAL 30 DAY),
    DATE_SUB(CURDATE(), INTERVAL 17 DAY),
    DATE_SUB(CURDATE(), INTERVAL 14 DAY)
);

-- E) shaheer - 'Steve Jobs' - returned 5 days late, fine IS paid
INSERT INTO issued_books (book_id, student_id, issue_date, expiry_date, return_date)
VALUES (
    (SELECT id FROM books    WHERE isbn     = '9781451648539'),
    (SELECT id FROM students WHERE username = 'shaheer'),
    DATE_SUB(CURDATE(), INTERVAL 45 DAY),
    DATE_SUB(CURDATE(), INTERVAL 31 DAY),
    DATE_SUB(CURDATE(), INTERVAL 26 DAY)
);

-- F) fatima - Moth Smoke (active, overdue by 3 days)
INSERT INTO issued_books (book_id, student_id, issue_date, expiry_date, return_date)
VALUES (
    (SELECT id FROM books WHERE isbn = '9780312420901'),
    (SELECT id FROM students WHERE username = 'fatima'),
    DATE_SUB(CURDATE(), INTERVAL 17 DAY),
    DATE_SUB(CURDATE(), INTERVAL 3 DAY),
    NULL
);

-- G) rahul - Dune (active, due today)
INSERT INTO issued_books (book_id, student_id, issue_date, expiry_date, return_date)
VALUES (
    (SELECT id FROM books WHERE isbn = '9780441013593'),
    (SELECT id FROM students WHERE username = 'rahul'),
    DATE_SUB(CURDATE(), INTERVAL 14 DAY),
    CURDATE(),
    NULL
);

-- H) saima - Hound of Baskervilles (active, due in 7 days)
INSERT INTO issued_books (book_id, student_id, issue_date, expiry_date, return_date)
VALUES (
    (SELECT id FROM books WHERE isbn = '9780553212365'),
    (SELECT id FROM students WHERE username = 'saima'),
    DATE_SUB(CURDATE(), INTERVAL 7 DAY),
    DATE_ADD(CURDATE(), INTERVAL 7 DAY),
    NULL
);

-- I) bilal - The God of Small Things (returned on time)
INSERT INTO issued_books (book_id, student_id, issue_date, expiry_date, return_date)
VALUES (
    (SELECT id FROM books WHERE isbn = '9780812979657'),
    (SELECT id FROM students WHERE username = 'bilal'),
    DATE_SUB(CURDATE(), INTERVAL 21 DAY),
    DATE_SUB(CURDATE(), INTERVAL 7 DAY),
    DATE_SUB(CURDATE(), INTERVAL 8 DAY)
);

-- J) yasir - The Alchemist (returned late, unpaid fine)
INSERT INTO issued_books (book_id, student_id, issue_date, expiry_date, return_date)
VALUES (
    (SELECT id FROM books WHERE isbn = '9780062502174'),
    (SELECT id FROM students WHERE username = 'yasir'),
    DATE_SUB(CURDATE(), INTERVAL 25 DAY),
    DATE_SUB(CURDATE(), INTERVAL 10 DAY),
    DATE_SUB(CURDATE(), INTERVAL 5 DAY)
);

-- K) shaheer - The Selfish Gene (returned late, fine paid)
INSERT INTO issued_books (book_id, student_id, issue_date, expiry_date, return_date)
VALUES (
    (SELECT id FROM books WHERE isbn = '9780198788607'),
    (SELECT id FROM students WHERE username = 'shaheer'),
    DATE_SUB(CURDATE(), INTERVAL 40 DAY),
    DATE_SUB(CURDATE(), INTERVAL 20 DAY),
    DATE_SUB(CURDATE(), INTERVAL 15 DAY)
);

-- L) kiran - The Reluctant Fundamentalist (active, overdue 2 days)
INSERT INTO issued_books (book_id, student_id, issue_date, expiry_date, return_date)
VALUES (
    (SELECT id FROM books WHERE isbn = '9780151013043'),
    (SELECT id FROM students WHERE username = 'kiran'),
    DATE_SUB(CURDATE(), INTERVAL 16 DAY),
    DATE_SUB(CURDATE(), INTERVAL 2 DAY),
    NULL
);

-- M) ahmed - The White Tiger (returned on time)
INSERT INTO issued_books (book_id, student_id, issue_date, expiry_date, return_date)
VALUES (
    (SELECT id FROM books WHERE isbn = '9781416562603'),
    (SELECT id FROM students WHERE username = 'ahmed'),
    DATE_SUB(CURDATE(), INTERVAL 28 DAY),
    DATE_SUB(CURDATE(), INTERVAL 14 DAY),
    DATE_SUB(CURDATE(), INTERVAL 14 DAY)
);

-- N) fatima - Foundation
INSERT INTO issued_books (book_id, student_id, issue_date, expiry_date, return_date)
VALUES (
    (SELECT id FROM books WHERE isbn = '9780553293357'),
    (SELECT id FROM students WHERE username = 'fatima'),
    DATE_SUB(CURDATE(), INTERVAL 10 DAY),
    DATE_ADD(CURDATE(), INTERVAL 4 DAY),
    NULL
);

-- O) rahul - Gone Girl (returned late, fine unpaid)
INSERT INTO issued_books (book_id, student_id, issue_date, expiry_date, return_date)
VALUES (
    (SELECT id FROM books WHERE isbn = '9780307588371'),
    (SELECT id FROM students WHERE username = 'rahul'),
    DATE_SUB(CURDATE(), INTERVAL 35 DAY),
    DATE_SUB(CURDATE(), INTERVAL 15 DAY),
    DATE_SUB(CURDATE(), INTERVAL 10 DAY)
);

-- P) bilal - Atomic Habits (returned on time)
INSERT INTO issued_books (book_id, student_id, issue_date, expiry_date, return_date)
VALUES (
    (SELECT id FROM books WHERE isbn = '9780735211292'),
    (SELECT id FROM students WHERE username = 'bilal'),
    DATE_SUB(CURDATE(), INTERVAL 30 DAY),
    DATE_SUB(CURDATE(), INTERVAL 16 DAY),
    DATE_SUB(CURDATE(), INTERVAL 16 DAY)
);

-- Q) yasir - The 7 Habits (returned late, fine unpaid)
INSERT INTO issued_books (book_id, student_id, issue_date, expiry_date, return_date)
VALUES (
    (SELECT id FROM books WHERE isbn = '9780743269513'),
    (SELECT id FROM students WHERE username = 'yasir'),
    DATE_SUB(CURDATE(), INTERVAL 22 DAY),
    DATE_SUB(CURDATE(), INTERVAL 8 DAY),
    DATE_SUB(CURDATE(), INTERVAL 4 DAY)
);

-- R) shaheer - How to Win Friends (active, overdue 10 days)
INSERT INTO issued_books (book_id, student_id, issue_date, expiry_date, return_date)
VALUES (
    (SELECT id FROM books WHERE isbn = '9780671027032'),
    (SELECT id FROM students WHERE username = 'shaheer'),
    DATE_SUB(CURDATE(), INTERVAL 31 DAY),
    DATE_SUB(CURDATE(), INTERVAL 10 DAY),
    NULL
);

-- ---------------------------------------------------------------------
-- === Fines for the Overdue & Late-returned Loans ===
-- ---------------------------------------------------------------------

-- For loan J (Yasir - The Alchemist, 5 days late) amount = 5*10 = 50, unpaid
INSERT INTO fines (issued_book_id, amount, paid, created_at, paid_at)
VALUES (
    (SELECT ib.id FROM issued_books ib JOIN books b ON ib.book_id=b.id JOIN students s ON ib.student_id=s.id
     WHERE b.isbn='9780062502174' AND s.username='yasir'),
    50.00, FALSE, DATE_SUB(CURDATE(), INTERVAL 5 DAY), NULL
);

-- For loan K (shaheer - The Selfish Gene, 5 days late) amount=50, paid
INSERT INTO fines (issued_book_id, amount, paid, created_at, paid_at)
VALUES (
    (SELECT ib.id FROM issued_books ib JOIN books b ON ib.book_id=b.id JOIN students s ON ib.student_id=s.id
     WHERE b.isbn='9780198788607' AND s.username='shaheer'),
    50.00, TRUE, DATE_SUB(CURDATE(), INTERVAL 15 DAY), DATE_SUB(CURDATE(), INTERVAL 10 DAY)
);

-- For loan O (rahul - Gone Girl, 5 days late) amount=50, unpaid
INSERT INTO fines (issued_book_id, amount, paid, created_at, paid_at)
VALUES (
    (SELECT ib.id FROM issued_books ib JOIN books b ON ib.book_id=b.id JOIN students s ON ib.student_id=s.id
     WHERE b.isbn='9780307588371' AND s.username='rahul'),
    50.00, FALSE, DATE_SUB(CURDATE(), INTERVAL 10 DAY), NULL
);

-- For loan Q (yasir - The 7 Habits, 4 days late) amount=40, unpaid
INSERT INTO fines (issued_book_id, amount, paid, created_at, paid_at)
VALUES (
    (SELECT ib.id FROM issued_books ib JOIN books b ON ib.book_id=b.id JOIN students s ON ib.student_id=s.id
     WHERE b.isbn='9780743269513' AND s.username='yasir'),
    40.00, FALSE, DATE_SUB(CURDATE(), INTERVAL 4 DAY), NULL
);

-- ---------------------------------------------------------------------
-- === Reservations for the Books ===
-- ---------------------------------------------------------------------

-- 1) ahmed reserves 'The Martian' (currently available)
INSERT INTO reservations (book_id, student_id, reserved_at, status)
VALUES (
    (SELECT id FROM books WHERE isbn = '9780553418026'),
    (SELECT id FROM students WHERE username = 'ahmed'),
    NOW(), 'Pending'
);

-- 2) fatima reserves 'Hyperion' (available)
INSERT INTO reservations (book_id, student_id, reserved_at, status)
VALUES (
    (SELECT id FROM books WHERE isbn = '9780553283686'),
    (SELECT id FROM students WHERE username = 'fatima'),
    DATE_SUB(NOW(), INTERVAL 1 DAY), 'Pending'
);

-- 3) rahul reserves 'Neuromancer'
INSERT INTO reservations (book_id, student_id, reserved_at, status)
VALUES (
    (SELECT id FROM books WHERE isbn = '9780441569595'),
    (SELECT id FROM students WHERE username = 'rahul'),
    DATE_SUB(NOW(), INTERVAL 2 DAY), 'Pending'
);

-- 4) saima reserves 'The Maltese Falcon'
INSERT INTO reservations (book_id, student_id, reserved_at, status)
VALUES (
    (SELECT id FROM books WHERE isbn = '9780679742645'),
    (SELECT id FROM students WHERE username = 'saima'),
    DATE_SUB(NOW(), INTERVAL 3 DAY), 'Pending'
);

-- 5) bilal reserves 'The God of Small Things' (already returned)
INSERT INTO reservations (book_id, student_id, reserved_at, status)
VALUES (
    (SELECT id FROM books WHERE isbn = '9780812979657'),
    (SELECT id FROM students WHERE username = 'bilal'),
    DATE_SUB(NOW(), INTERVAL 5 DAY), 'Fulfilled'
);

-- 6) yasir reserves 'The Power of Now' (available) -> Fulfilled
INSERT INTO reservations (book_id, student_id, reserved_at, status)
VALUES (
    (SELECT id FROM books WHERE isbn = '9781577314806'),
    (SELECT id FROM students WHERE username = 'yasir'),
    DATE_SUB(NOW(), INTERVAL 7 DAY), 'Fulfilled'
);

-- 7) shaheer reserves 'The Subtle Art' (available) -> Cancelled
INSERT INTO reservations (book_id, student_id, reserved_at, status)
VALUES (
    (SELECT id FROM books WHERE isbn = '9780062457714'),
    (SELECT id FROM students WHERE username = 'shaheer'),
    DATE_SUB(NOW(), INTERVAL 4 DAY), 'Cancelled'
);

-- 8) kiran reserves 'The 5 AM Club' (available) -> Pending
INSERT INTO reservations (book_id, student_id, reserved_at, status)
VALUES (
    (SELECT id FROM books WHERE isbn = '9781443456623'),
    (SELECT id FROM students WHERE username = 'kiran'),
    NOW(), 'Pending'
);

-- =====================================================================
-- PART 5 - VERIFICATION QUERIES
-- =====================================================================
SELECT '== Tables ==============================' AS '';
SHOW TABLES;

SELECT '== Books per category ==================' AS '';
SELECT
    COALESCE(c.name, 'Uncategorised') AS category,
    COUNT(b.id)                       AS book_count
FROM   books b
LEFT JOIN categories c ON b.category_id = c.id
GROUP BY c.id, c.name
ORDER BY book_count DESC;

SELECT '== Book status summary =================' AS '';
SELECT status, COUNT(*) AS total
FROM   books
GROUP BY status;

SELECT '== Active loans (unreturned) ===========' AS '';
SELECT
    s.username,
    b.title,
    ib.issue_date,
    ib.expiry_date,
    CASE WHEN ib.expiry_date < CURDATE()
         THEN CONCAT('OVERDUE by ', DATEDIFF(CURDATE(), ib.expiry_date), ' day(s)')
         ELSE CONCAT('Due in ',     DATEDIFF(ib.expiry_date, CURDATE()), ' day(s)')
    END AS due_status
FROM   issued_books ib
JOIN   books    b ON ib.book_id    = b.id
JOIN   students s ON ib.student_id = s.id
WHERE  ib.return_date IS NULL;

SELECT '== Fines ===============================' AS '';
SELECT
    s.username,
    b.title,
    f.amount,
    IF(f.paid, 'Paid', 'Unpaid') AS payment_status,
    f.paid_at
FROM   fines f
JOIN   issued_books ib ON f.issued_book_id = ib.id
JOIN   books        b  ON ib.book_id       = b.id
JOIN   students     s  ON ib.student_id    = s.id;

SELECT '== Reservations ========================' AS '';
SELECT
    s.username,
    b.title,
    r.status,
    r.reserved_at
FROM   reservations r
JOIN   books    b ON r.book_id    = b.id
JOIN   students s ON r.student_id = s.id
ORDER BY r.reserved_at;

SELECT '== Setup complete ======================' AS '';
