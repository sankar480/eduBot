// ═══════════════════════════════════════════════════════════════
//  server.js  —  EduBot Backend  (Node.js + Express + MySQL)
//  API key lives ONLY in .env — never exposed to browser
//  npm install express mysql2 bcryptjs jsonwebtoken cors dotenv express-rate-limit helmet
// ═══════════════════════════════════════════════════════════════
'use strict';
require('dotenv').config();

const express   = require('express');
const mysql     = require('mysql2/promise');
const bcrypt    = require('bcryptjs');
const jwt       = require('jsonwebtoken');
const cors      = require('cors');
const helmet    = require('helmet');
const rateLimit = require('express-rate-limit');
const path      = require('path');

const app = express();
// FIX: helmet CSP relaxed so server-side fetch to Anthropic works
// (helmet affects response headers, not server-side fetch — kept for safety)
app.use(helmet({ contentSecurityPolicy: false }));
app.use(cors({ origin: process.env.CORS_ORIGIN || (process.env.NODE_ENV === 'production' ? 'https://yourdomain.com' : '*') }));
app.use(express.json({ limit: '2mb' }));
app.use(express.static(path.join(__dirname, 'public')));

const limiter      = rateLimit({ windowMs:15*60*1000, max:150 });
const loginLimiter = rateLimit({ windowMs:15*60*1000, max:10, message:{error:'Too many attempts. Wait 15 min.'} });
app.use('/api/', limiter);
app.use('/api/auth/', loginLimiter);
app.use('/api/admin/login', loginLimiter);

const pool = mysql.createPool({
  host: process.env.DB_HOST||'localhost', port: parseInt(process.env.DB_PORT)||3306,
  user: process.env.DB_USER, password: process.env.DB_PASS, database: process.env.DB_NAME,
  connectionLimit:10, waitForConnections:true, timezone:'+05:30',
});

const genReceipt = () => 'REC' + Date.now() + Math.floor(Math.random()*1000);

function authStudent(req,res,next){
  const h=req.headers.authorization;
  if(!h?.startsWith('Bearer ')) return res.status(401).json({error:'Unauthorized'});
  try { req.user=jwt.verify(h.slice(7),process.env.JWT_SECRET); next(); }
  catch { res.status(401).json({error:'Session expired. Please log in again.'}); }
}

function authAdmin(req,res,next){
  const h=req.headers.authorization;
  if(!h?.startsWith('Bearer ')) return res.status(401).json({error:'Admin unauthorized'});
  try {
    const d=jwt.verify(h.slice(7),process.env.ADMIN_JWT_SECRET);
    if(d.role!=='admin') return res.status(403).json({error:'Forbidden'});
    req.admin=d; next();
  } catch { res.status(401).json({error:'Admin session expired.'}); }
}

// ══ STUDENT AUTH ══════════════════════════════════════════════
app.post('/api/auth/login', async(req,res)=>{
  const {roll_no,password}=req.body;
  if(!roll_no||!password) return res.status(400).json({error:'roll_no and password required'});
  try{
    const [[s]]=await pool.query('SELECT id,roll_no,full_name,email,department,program,semester,password_hash,is_active FROM students WHERE roll_no=?',[roll_no.trim().toUpperCase()]);
    if(!s||!s.is_active) return res.status(401).json({error:'Invalid credentials or account inactive'});
    if(!await bcrypt.compare(password,s.password_hash)) return res.status(401).json({error:'Invalid credentials'});
    const token=jwt.sign({id:s.id,roll_no:s.roll_no,name:s.full_name,dept:s.department},process.env.JWT_SECRET,{expiresIn:'8h'});
    res.json({token,student:{id:s.id,roll_no:s.roll_no,name:s.full_name,email:s.email,department:s.department,program:s.program,semester:s.semester}});
  }catch(e){console.error(e);res.status(500).json({error:'Server error'});}
});

app.post('/api/auth/change-password', authStudent, async(req,res)=>{
  const {old_password,new_password}=req.body;
  if(!new_password||new_password.length<8) return res.status(400).json({error:'Password must be 8+ chars'});
  try{
    const [[s]]=await pool.query('SELECT password_hash FROM students WHERE id=?',[req.user.id]);
    if(!await bcrypt.compare(old_password,s.password_hash)) return res.status(401).json({error:'Old password wrong'});
    await pool.query('UPDATE students SET password_hash=? WHERE id=?',[await bcrypt.hash(new_password,10),req.user.id]);
    res.json({message:'Password updated'});
  }catch{res.status(500).json({error:'Server error'});}
});

// ══ ADMIN AUTH ════════════════════════════════════════════════
app.post('/api/admin/login', async(req,res)=>{
  const {username,password}=req.body;
  if(!username||!password) return res.status(400).json({error:'username and password required'});
  if(username!==process.env.ADMIN_USERNAME||password!==process.env.ADMIN_PASSWORD)
    return res.status(401).json({error:'Invalid admin credentials'});
  const token=jwt.sign({username,role:'admin'},process.env.ADMIN_JWT_SECRET,{expiresIn:'4h'});
  res.json({token,admin:{username,role:'admin'}});
});

app.get('/api/admin/verify', authAdmin, (req,res)=>res.json({valid:true,admin:req.admin}));

// ══ STUDENT PROFILE ═══════════════════════════════════════════
app.get('/api/student/profile', authStudent, async(req,res)=>{
  try{
    const [[s]]=await pool.query('SELECT id,roll_no,full_name,email,phone,department,program,semester,academic_year,dob,gender,address,guardian_name,guardian_phone FROM students WHERE id=? AND is_active=1',[req.user.id]);
    if(!s) return res.status(404).json({error:'Not found'});
    res.json(s);
  }catch{res.status(500).json({error:'Server error'});}
});

// ══ FEES — STUDENT ════════════════════════════════════════════
app.get('/api/fees/summary', authStudent, async(req,res)=>{
  try{ const [[s]]=await pool.query('SELECT * FROM v_student_fee_summary WHERE student_id=?',[req.user.id]); res.json(s||{total_demanded:0,total_paid:0,balance_due:0,payment_status:'No Demand'}); }
  catch{ res.status(500).json({error:'Server error'}); }
});

app.get('/api/fees/demands', authStudent, async(req,res)=>{
  const {academic_year}=req.query;
  try{
    const [rows]=await pool.query(`SELECT fd.id,ft.code,ft.name AS fee_name,fd.academic_year,fd.semester,fd.amount,fd.due_date,COALESCE(SUM(fp.amount_paid),0) AS amount_paid,fd.amount-COALESCE(SUM(fp.amount_paid),0) AS balance,CASE WHEN COALESCE(SUM(fp.amount_paid),0)>=fd.amount THEN 'Paid' WHEN COALESCE(SUM(fp.amount_paid),0)>0 THEN 'Partial' WHEN fd.due_date<CURDATE() THEN 'Overdue' ELSE 'Pending' END AS status FROM fee_demands fd JOIN fee_types ft ON ft.id=fd.fee_type_id LEFT JOIN fee_payments fp ON fp.demand_id=fd.id AND fp.status='Completed' WHERE fd.student_id=? ${academic_year?'AND fd.academic_year=?':''} GROUP BY fd.id ORDER BY fd.due_date DESC`,
      academic_year?[req.user.id,academic_year]:[req.user.id]);
    res.json(rows);
  }catch{res.status(500).json({error:'Server error'});}
});

app.get('/api/fees/payments', authStudent, async(req,res)=>{
  const {academic_year}=req.query;
  try{
    const [rows]=await pool.query(`SELECT fp.id,fp.receipt_no,ft.name AS fee_name,ft.code,fp.academic_year,fp.semester,fp.amount_paid,fp.payment_date,fp.payment_mode,fp.transaction_ref,fp.status FROM fee_payments fp JOIN fee_types ft ON ft.id=fp.fee_type_id WHERE fp.student_id=? ${academic_year?'AND fp.academic_year=?':''} AND fp.status='Completed' ORDER BY fp.payment_date DESC`,
      academic_year?[req.user.id,academic_year]:[req.user.id]);
    res.json(rows);
  }catch{res.status(500).json({error:'Server error'});}
});

app.get('/api/fees/scholarships', authStudent, async(req,res)=>{
  try{ const [r]=await pool.query('SELECT * FROM scholarships WHERE student_id=? ORDER BY academic_year DESC',[req.user.id]); res.json(r); }
  catch{ res.status(500).json({error:'Server error'}); }
});

// ══ ADMIN — DASHBOARD STATS ═══════════════════════════════════
app.get('/api/admin/stats', authAdmin, async(req,res)=>{
  try{
    const [[{totalStudents}]]=await pool.query('SELECT COUNT(*) AS totalStudents FROM students WHERE is_active=1');
    const [[{totalPaid}]]=await pool.query("SELECT COALESCE(SUM(amount_paid),0) AS totalPaid FROM fee_payments WHERE status='Completed'");
    const [[{totalDue}]]=await pool.query('SELECT COALESCE(SUM(balance_due),0) AS totalDue FROM v_student_fee_summary');
    const [[{paidCount}]]=await pool.query("SELECT COUNT(*) AS paidCount FROM v_student_fee_summary WHERE payment_status='Paid'");
    res.json({totalStudents,totalPaid,totalDue,paidCount});
  }catch{res.status(500).json({error:'Server error'});}
});

// ══ ADMIN — ALL STUDENTS ══════════════════════════════════════
app.get('/api/admin/students', authAdmin, async(req,res)=>{
  const {dept,search}=req.query;
  try{
    let q='SELECT id,roll_no,full_name,email,phone,department,program,semester,academic_year,is_active FROM students WHERE 1=1';
    const p=[];
    if(dept){q+=' AND department=?';p.push(dept);}
    if(search){q+=' AND (roll_no LIKE ? OR full_name LIKE ? OR email LIKE ?)';p.push(`%${search}%`,`%${search}%`,`%${search}%`);}
    q+=' ORDER BY roll_no';
    const [r]=await pool.query(q,p); res.json(r);
  }catch{res.status(500).json({error:'Server error'});}
});

app.post('/api/admin/students', authAdmin, async(req,res)=>{
  const {roll_no,full_name,email,phone,department,program,semester,academic_year,password}=req.body;
  if(!roll_no||!full_name||!email||!department||!password) return res.status(400).json({error:'Missing required fields'});
  try{
    const hash=await bcrypt.hash(password,10);
    await pool.query('INSERT INTO students (roll_no,full_name,email,phone,department,program,semester,academic_year,password_hash) VALUES (?,?,?,?,?,?,?,?,?)',
      [roll_no.toUpperCase(),full_name,email,phone||null,department,program||'UG',semester||1,academic_year||'2024-25',hash]);
    res.status(201).json({message:'Student added'});
  }catch(e){ if(e.code==='ER_DUP_ENTRY') return res.status(409).json({error:'Roll number or email already exists'}); res.status(500).json({error:'Server error'}); }
});

app.patch('/api/admin/students/:id/toggle', authAdmin, async(req,res)=>{
  try{ await pool.query('UPDATE students SET is_active=NOT is_active WHERE id=?',[req.params.id]); res.json({message:'Updated'}); }
  catch{ res.status(500).json({error:'Server error'}); }
});

// FIX: Added missing DELETE student endpoint
app.delete('/api/admin/students/:id', authAdmin, async(req,res)=>{
  try{ await pool.query('UPDATE students SET is_active=0 WHERE id=?',[req.params.id]); res.json({message:'Student deactivated'}); }
  catch{ res.status(500).json({error:'Server error'}); }
});

app.patch('/api/admin/students/:id/reset-password', authAdmin, async(req,res)=>{
  const {new_password}=req.body;
  if(!new_password||new_password.length<8) return res.status(400).json({error:'Password too short'});
  try{ const hash=await bcrypt.hash(new_password,10); await pool.query('UPDATE students SET password_hash=? WHERE id=?',[hash,req.params.id]); res.json({message:'Password reset'}); }
  catch{ res.status(500).json({error:'Server error'}); }
});

// ══ ADMIN — FEES MANAGEMENT ═══════════════════════════════════
app.get('/api/admin/fees/all', authAdmin, async(req,res)=>{
  try{ const [r]=await pool.query('SELECT * FROM v_student_fee_summary ORDER BY roll_no'); res.json(r); }
  catch{ res.status(500).json({error:'Server error'}); }
});

app.post('/api/admin/fees/record-payment', authAdmin, async(req,res)=>{
  const {student_id,fee_type_code,academic_year,semester,amount_paid,payment_mode,transaction_ref,demand_id}=req.body;
  if(!student_id||!fee_type_code||!amount_paid||!payment_mode) return res.status(400).json({error:'Missing fields'});
  try{
    const [[ft]]=await pool.query('SELECT id FROM fee_types WHERE code=?',[fee_type_code]);
    if(!ft) return res.status(400).json({error:'Unknown fee type'});
    const rno=genReceipt();
    await pool.query(`INSERT INTO fee_payments (student_id,fee_type_id,demand_id,academic_year,semester,amount_paid,payment_date,payment_mode,transaction_ref,receipt_no,status,collected_by) VALUES (?,?,?,?,?,?,CURDATE(),?,?,?,'Completed',?)`,
      [student_id,ft.id,demand_id||null,academic_year,semester||null,amount_paid,payment_mode,transaction_ref||null,rno,req.admin.username]);
    res.status(201).json({message:'Payment recorded',receipt_no:rno});
  }catch{res.status(500).json({error:'Server error'});}
});

app.post('/api/admin/fees/demand', authAdmin, async(req,res)=>{
  const {student_id,fee_type_code,academic_year,semester,amount,due_date}=req.body;
  if(!student_id||!fee_type_code||!amount||!due_date) return res.status(400).json({error:'Missing fields'});
  try{
    const [[ft]]=await pool.query('SELECT id FROM fee_types WHERE code=?',[fee_type_code]);
    await pool.query('INSERT IGNORE INTO fee_demands (student_id,fee_type_id,academic_year,semester,amount,due_date) VALUES (?,?,?,?,?,?)',[student_id,ft.id,academic_year,semester||null,amount,due_date]);
    res.status(201).json({message:'Demand created'});
  }catch{res.status(500).json({error:'Server error'});}
});

// ══ ANNOUNCEMENTS — persisted to MySQL (FIX: was in-memory, lost on restart) ══
app.get('/api/announcements', async(req,res)=>{
  try{
    const [r]=await pool.query(`SELECT id,title,body,type,posted_by,DATE_FORMAT(created_at,'%Y-%m-%d') AS date FROM announcements WHERE is_active=1 AND (expires_at IS NULL OR expires_at>=CURDATE()) ORDER BY created_at DESC LIMIT 20`);
    res.json(r);
  }catch{ res.status(500).json({error:'Server error'}); }
});
app.get('/api/admin/announcements', authAdmin, async(req,res)=>{
  try{
    const [r]=await pool.query(`SELECT id,title,body,type,posted_by,is_active,DATE_FORMAT(created_at,'%Y-%m-%d') AS date FROM announcements ORDER BY created_at DESC`);
    res.json(r);
  }catch{ res.status(500).json({error:'Server error'}); }
});
app.post('/api/admin/announcements', authAdmin, async(req,res)=>{
  const {title,body,type}=req.body;
  if(!title||!body) return res.status(400).json({error:'title and body required'});
  try{
    const [result]=await pool.query(`INSERT INTO announcements (title,body,type,posted_by) VALUES (?,?,?,?)`,
      [title,body,type||'info',req.admin.username]);
    const [[a]]=await pool.query('SELECT id,title,body,type,posted_by,DATE_FORMAT(created_at,\'%Y-%m-%d\') AS date FROM announcements WHERE id=?',[result.insertId]);
    res.status(201).json(a);
  }catch{ res.status(500).json({error:'Server error'}); }
});
app.delete('/api/admin/announcements/:id', authAdmin, async(req,res)=>{
  try{ await pool.query('UPDATE announcements SET is_active=0 WHERE id=?',[req.params.id]); res.json({message:'Deleted'}); }
  catch{ res.status(500).json({error:'Server error'}); }
});

// ══ CLAUDE AI PROXY — API key stored in .env only ═════════════
app.post('/api/chat', authStudent, async(req,res)=>{
  const {messages,system}=req.body;
  if(!Array.isArray(messages)) return res.status(400).json({error:'messages array required'});
  try{
    const r=await fetch('https://api.anthropic.com/v1/messages',{
      method:'POST',
      headers:{'Content-Type':'application/json','x-api-key':process.env.ANTHROPIC_API_KEY,'anthropic-version':'2023-06-01'},
      body:JSON.stringify({model:'claude-sonnet-4-20250514',max_tokens:1200,system,messages})
    });
    const d=await r.json(); if(!r.ok) return res.status(r.status).json(d); res.json(d);
  }catch{res.status(500).json({error:'AI service error'});}
});

app.post('/api/admin/chat', authAdmin, async(req,res)=>{
  const {messages,system}=req.body;
  if(!Array.isArray(messages)) return res.status(400).json({error:'messages required'});
  try{
    const r=await fetch('https://api.anthropic.com/v1/messages',{
      method:'POST',
      headers:{'Content-Type':'application/json','x-api-key':process.env.ANTHROPIC_API_KEY,'anthropic-version':'2023-06-01'},
      body:JSON.stringify({model:'claude-sonnet-4-20250514',max_tokens:1200,system,messages})
    });
    const d=await r.json(); if(!r.ok) return res.status(r.status).json(d); res.json(d);
  }catch{res.status(500).json({error:'AI error'});}
});

app.get('/api/health',(_, res)=>res.json({status:'ok',ts:new Date().toISOString()}));
app.listen(process.env.PORT||3000,()=>console.log(`✅ EduBot → http://localhost:${process.env.PORT||3000}`));
