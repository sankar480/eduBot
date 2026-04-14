-- ═══════════════════════════════════════════════════════════════
--  EduBot — Supabase / PostgreSQL Schema
--  Run this in: Supabase Dashboard → SQL Editor → New Query
-- ═══════════════════════════════════════════════════════════════

-- ── DEPARTMENTS ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS departments (
  id         SMALLSERIAL PRIMARY KEY,
  code       VARCHAR(10)  NOT NULL UNIQUE,
  name       VARCHAR(100) NOT NULL,
  hod_name   VARCHAR(100),
  hod_email  VARCHAR(120),
  created_at TIMESTAMPTZ DEFAULT NOW()
);
INSERT INTO departments (code, name) VALUES
  ('CSE','Computer Science and Engineering'),
  ('ECE','Electronics and Communication Engineering'),
  ('EEE','Electrical and Electronics Engineering'),
  ('MECH','Mechanical Engineering'),
  ('CIVIL','Civil Engineering'),
  ('IT','Information Technology'),
  ('AIDS','Artificial Intelligence and Data Science'),
  ('MBA','Master of Business Administration'),
  ('MCA','Master of Computer Applications')
ON CONFLICT (code) DO NOTHING;

-- ── STUDENTS ─────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS students (
  id             SERIAL PRIMARY KEY,
  roll_no        VARCHAR(20)  NOT NULL UNIQUE,
  full_name      VARCHAR(150) NOT NULL,
  email          VARCHAR(150) NOT NULL UNIQUE,
  phone          VARCHAR(15),
  department     VARCHAR(20)  NOT NULL,
  program        VARCHAR(10)  NOT NULL DEFAULT 'UG',
  semester       SMALLINT     NOT NULL DEFAULT 1 CHECK (semester BETWEEN 1 AND 10),
  academic_year  VARCHAR(10)  NOT NULL DEFAULT '2024-25',
  dob            DATE,
  gender         VARCHAR(10),
  address        TEXT,
  guardian_name  VARCHAR(150),
  guardian_phone VARCHAR(15),
  password_hash  VARCHAR(255) NOT NULL,
  is_active      BOOLEAN      NOT NULL DEFAULT TRUE,
  created_at     TIMESTAMPTZ  DEFAULT NOW(),
  updated_at     TIMESTAMPTZ  DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_students_dept   ON students(department);
CREATE INDEX IF NOT EXISTS idx_students_active ON students(is_active);

-- ── FEE TYPES ────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS fee_types (
  id          SMALLSERIAL PRIMARY KEY,
  code        VARCHAR(30)  NOT NULL UNIQUE,
  name        VARCHAR(120) NOT NULL,
  description TEXT,
  is_active   BOOLEAN      NOT NULL DEFAULT TRUE
);
INSERT INTO fee_types (code, name) VALUES
  ('TUITION',   'Tuition Fee'),
  ('EXAM',      'Examination Fee'),
  ('LIBRARY',   'Library Fee'),
  ('LAB',       'Laboratory Fee'),
  ('HOSTEL',    'Hostel Fee'),
  ('TRANSPORT', 'Transport / Bus Fee'),
  ('SPORTS',    'Sports & Cultural Fee'),
  ('CAUTION',   'Caution Deposit'),
  ('MISC',      'Miscellaneous Fee')
ON CONFLICT (code) DO NOTHING;

-- ── FEE DEMANDS ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS fee_demands (
  id            SERIAL PRIMARY KEY,
  student_id    INT          NOT NULL REFERENCES students(id) ON DELETE CASCADE,
  fee_type_id   SMALLINT     NOT NULL REFERENCES fee_types(id),
  academic_year VARCHAR(10)  NOT NULL,
  semester      SMALLINT,
  amount        NUMERIC(10,2) NOT NULL,
  due_date      DATE         NOT NULL,
  waiver_amount NUMERIC(10,2) NOT NULL DEFAULT 0,
  remarks       VARCHAR(255),
  created_at    TIMESTAMPTZ  DEFAULT NOW(),
  UNIQUE(student_id, fee_type_id, academic_year)
);

-- ── FEE PAYMENTS ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS fee_payments (
  id              SERIAL PRIMARY KEY,
  student_id      INT           NOT NULL REFERENCES students(id) ON DELETE CASCADE,
  fee_type_id     SMALLINT      NOT NULL REFERENCES fee_types(id),
  demand_id       INT           REFERENCES fee_demands(id) ON DELETE SET NULL,
  academic_year   VARCHAR(10)   NOT NULL,
  semester        SMALLINT,
  amount_paid     NUMERIC(10,2) NOT NULL,
  payment_date    DATE          NOT NULL,
  payment_mode    VARCHAR(20)   NOT NULL,
  transaction_ref VARCHAR(100),
  receipt_no      VARCHAR(40)   NOT NULL UNIQUE,
  status          VARCHAR(20)   NOT NULL DEFAULT 'Completed',
  collected_by    VARCHAR(60),
  remarks         VARCHAR(255),
  created_at      TIMESTAMPTZ   DEFAULT NOW()
);

-- ── SCHOLARSHIPS ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS scholarships (
  id             SERIAL PRIMARY KEY,
  student_id     INT           NOT NULL REFERENCES students(id) ON DELETE CASCADE,
  scheme_name    VARCHAR(150)  NOT NULL,
  academic_year  VARCHAR(10)   NOT NULL,
  amount         NUMERIC(10,2) NOT NULL,
  disbursed_date DATE,
  status         VARCHAR(20)   NOT NULL DEFAULT 'Pending',
  remarks        VARCHAR(255),
  created_at     TIMESTAMPTZ   DEFAULT NOW()
);

-- ── TIMETABLE ────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS timetable (
  id            SERIAL PRIMARY KEY,
  department    VARCHAR(20)  NOT NULL,
  semester      SMALLINT     NOT NULL,
  academic_year VARCHAR(10)  NOT NULL,
  day_of_week   VARCHAR(12)  NOT NULL,
  period_no     SMALLINT     NOT NULL,
  start_time    TIME         NOT NULL,
  end_time      TIME         NOT NULL,
  subject_code  VARCHAR(20),
  subject_name  VARCHAR(120) NOT NULL,
  faculty_name  VARCHAR(100),
  room_no       VARCHAR(20),
  type          VARCHAR(20)  NOT NULL DEFAULT 'Theory',
  UNIQUE(department, semester, academic_year, day_of_week, period_no)
);

-- ── EXAM SCHEDULE ────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS exam_schedule (
  id            SERIAL PRIMARY KEY,
  exam_type     VARCHAR(30)  NOT NULL,
  department    VARCHAR(20),
  semester      SMALLINT,
  academic_year VARCHAR(10)  NOT NULL,
  subject_code  VARCHAR(20),
  subject_name  VARCHAR(120) NOT NULL,
  exam_date     DATE         NOT NULL,
  start_time    TIME         NOT NULL DEFAULT '09:00',
  end_time      TIME         NOT NULL DEFAULT '12:00',
  hall_no       VARCHAR(30),
  remarks       VARCHAR(255),
  created_at    TIMESTAMPTZ  DEFAULT NOW()
);

-- ── HALL TICKETS ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS hall_tickets (
  id             SERIAL PRIMARY KEY,
  student_id     INT          NOT NULL REFERENCES students(id) ON DELETE CASCADE,
  exam_type      VARCHAR(30)  NOT NULL,
  academic_year  VARCHAR(10)  NOT NULL,
  semester       SMALLINT     NOT NULL,
  issued_date    DATE,
  is_issued      BOOLEAN      NOT NULL DEFAULT FALSE,
  attendance_pct NUMERIC(5,2),
  is_eligible    BOOLEAN      NOT NULL DEFAULT TRUE,
  remarks        VARCHAR(255),
  UNIQUE(student_id, exam_type, academic_year)
);

-- ── ATTENDANCE ───────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS attendance (
  id            SERIAL PRIMARY KEY,
  student_id    INT          NOT NULL REFERENCES students(id) ON DELETE CASCADE,
  subject_code  VARCHAR(20),
  subject_name  VARCHAR(120) NOT NULL,
  department    VARCHAR(20)  NOT NULL,
  semester      SMALLINT     NOT NULL,
  academic_year VARCHAR(10)  NOT NULL,
  total_classes SMALLINT     NOT NULL DEFAULT 0,
  attended      SMALLINT     NOT NULL DEFAULT 0,
  last_updated  DATE,
  UNIQUE(student_id, subject_code, academic_year)
);

-- ── ANNOUNCEMENTS ────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS announcements (
  id             SERIAL PRIMARY KEY,
  title          VARCHAR(200) NOT NULL,
  body           TEXT         NOT NULL,
  type           VARCHAR(20)  NOT NULL DEFAULT 'info',
  target_dept    VARCHAR(20),
  is_active      BOOLEAN      NOT NULL DEFAULT TRUE,
  posted_by      VARCHAR(60)  NOT NULL DEFAULT 'admin',
  created_at     TIMESTAMPTZ  DEFAULT NOW(),
  expires_at     DATE
);
INSERT INTO announcements (title, body, type, posted_by) VALUES
  ('Fee Due Reminder','Semester examination fees are due by November 15. Pay online or at the cash counter.','warning','admin'),
  ('Hall Tickets Released','Hall tickets for Semester End Exams are now available. Download from the exam portal.','success','admin'),
  ('Campus Placement Drive','Infosys campus drive on November 15. Register at placements.college.edu.in before Nov 10.','info','admin')
ON CONFLICT DO NOTHING;

-- ── CHAT LOGS ────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS chat_logs (
  id           SERIAL PRIMARY KEY,
  student_id   INT         REFERENCES students(id) ON DELETE SET NULL,
  role         VARCHAR(10) NOT NULL DEFAULT 'student',
  user_message TEXT        NOT NULL,
  bot_response TEXT,
  created_at   TIMESTAMPTZ DEFAULT NOW()
);

-- ── FAQ ENTRIES ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS faq_entries (
  id        SERIAL PRIMARY KEY,
  category  VARCHAR(30)  NOT NULL,
  question  VARCHAR(500) NOT NULL,
  answer    TEXT         NOT NULL,
  keywords  VARCHAR(500),
  views     INT          NOT NULL DEFAULT 0,
  is_active BOOLEAN      NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ── VIEW: v_student_fee_summary ──────────────────────────────────
CREATE OR REPLACE VIEW v_student_fee_summary AS
SELECT
  s.id                                           AS student_id,
  s.roll_no, s.full_name, s.department,
  s.semester, s.academic_year,
  COALESCE(d.total_demanded, 0)                  AS total_demanded,
  COALESCE(p.total_paid,     0)                  AS total_paid,
  COALESCE(d.total_demanded, 0)
    - COALESCE(p.total_paid, 0)                  AS balance_due,
  CASE
    WHEN COALESCE(d.total_demanded,0) = 0         THEN 'No Demand'
    WHEN COALESCE(p.total_paid,0) >= COALESCE(d.total_demanded,0) THEN 'Paid'
    WHEN COALESCE(p.total_paid,0) > 0             THEN 'Partial'
    WHEN EXISTS (SELECT 1 FROM fee_demands fd2
                 WHERE fd2.student_id=s.id
                   AND fd2.due_date < CURRENT_DATE
                   AND fd2.amount > COALESCE(p.total_paid,0)) THEN 'Overdue'
    ELSE 'Pending'
  END                                            AS payment_status
FROM students s
LEFT JOIN (
  SELECT student_id, SUM(amount) AS total_demanded
  FROM fee_demands GROUP BY student_id
) d ON d.student_id = s.id
LEFT JOIN (
  SELECT student_id, SUM(amount_paid) AS total_paid
  FROM fee_payments WHERE status='Completed' GROUP BY student_id
) p ON p.student_id = s.id;

-- ── DEMO STUDENTS (password = Password@123) ──────────────────────
-- bcrypt hash of "Password@123"
INSERT INTO students (roll_no,full_name,email,phone,department,program,semester,academic_year,password_hash)
VALUES
  ('CS2201001','Arjun Ramesh',      'arjun.r@abc.edu.in',   '9876543210','CSE', 'UG',5,'2024-25','$2a$10$N9qo8uLOickgx2ZMRZoMyeIjZAgcfl7p92ldGxad68LJZdL17lh3y'),
  ('CS2201002','Priya Nair',        'priya.n@abc.edu.in',   '9876543211','CSE', 'UG',5,'2024-25','$2a$10$N9qo8uLOickgx2ZMRZoMyeIjZAgcfl7p92ldGxad68LJZdL17lh3y'),
  ('EC2201003','Karthik Selvam',    'karthik.s@abc.edu.in', '9876543212','ECE', 'UG',3,'2024-25','$2a$10$N9qo8uLOickgx2ZMRZoMyeIjZAgcfl7p92ldGxad68LJZdL17lh3y'),
  ('ME2201004','Deepa Subramaniam', 'deepa.s@abc.edu.in',   '9876543213','MECH','UG',3,'2024-25','$2a$10$N9qo8uLOickgx2ZMRZoMyeIjZAgcfl7p92ldGxad68LJZdL17lh3y'),
  ('AI2201005','Sowmiya Devi',      'sowmiya.d@abc.edu.in', '9876543214','AIDS','UG',3,'2024-25','$2a$10$N9qo8uLOickgx2ZMRZoMyeIjZAgcfl7p92ldGxad68LJZdL17lh3y')
ON CONFLICT (roll_no) DO NOTHING;

SELECT '✅ EduBot Supabase schema ready!' AS status;
