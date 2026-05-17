from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3
from datetime import datetime
import pytz
from functools import wraps
import os

app = Flask(__name__)
app.secret_key = 'rahasia_dr_galih_pythonanywhere'

WITA = pytz.timezone('Asia/Makassar')

def now_wita():
    return datetime.now(WITA).strftime('%Y-%m-%d %H:%M:%S')

def date_wita():
    return datetime.now(WITA).strftime('%Y-%m-%d')

def init_db():
    # GANTI username_kamu dengan username PythonAnywhere mu
    conn = sqlite3.connect('/home/kecik/klinik_dr_galih/klinik.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS pasien (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nama TEXT, tgl_lahir TEXT, alamat TEXT, no_telp TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS rekam_medis (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        pasien_id INTEGER,
        tanggal TEXT,
        subjective TEXT,
        objective TEXT,
        assessment TEXT,
        planning TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS obat (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nama TEXT UNIQUE, stok INTEGER, satuan TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS resep (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        rekam_medis_id INTEGER,
        obat_id INTEGER,
        jumlah INTEGER,
        aturan TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS kunjungan (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        rekam_medis_id INTEGER,
        tanggal TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS user (
        username TEXT PRIMARY KEY,
        password TEXT)''')

    c.execute("INSERT OR IGNORE INTO user VALUES ('admin', 'admin123')")
    c.execute("INSERT OR IGNORE INTO obat (nama, stok, satuan) VALUES ('Parasetamol', 100, 'tablet')")
    c.execute("INSERT OR IGNORE INTO obat (nama, stok, satuan) VALUES ('Amoksisilin', 50, 'kapsul')")
    c.execute("INSERT OR IGNORE INTO obat (nama, stok, satuan) VALUES ('CTM', 80, 'tablet')")
    c.execute("INSERT OR IGNORE INTO obat (nama, stok, satuan) VALUES ('Ibuprofen', 60, 'tablet')")
    c.execute("INSERT OR IGNORE INTO obat (nama, stok, satuan) VALUES ('Loratadin', 40, 'tablet')")
    c.execute("INSERT OR IGNORE INTO obat (nama, stok, satuan) VALUES ('Antimo', 30, 'tablet')")
    conn.commit()
    conn.close()

def get_db():
    # GANTI username_kamu dengan username PythonAnywhere mu
    conn = sqlite3.connect('/home/kecik/klinik_dr_galih/klinik.db')
    conn.row_factory = sqlite3.Row
    return conn

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = get_db()
        user = conn.execute("SELECT * FROM user WHERE username=? AND password=?", (username, password)).fetchone()
        conn.close()
        if user:
            session['logged_in'] = True
            session['username'] = username
            return redirect(url_for('dashboard'))
        else:
            return render_template('login.html', error='Username atau password salah')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/')
def index():
    if 'logged_in' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    conn = get_db()
    today = date_wita()
    total_pasien = conn.execute("SELECT COUNT(*) as total FROM pasien").fetchone()['total']
    kunjungan_hari_ini = conn.execute("SELECT COUNT(*) as total FROM kunjungan WHERE tanggal=?", (today,)).fetchone()['total']
    total_obat = conn.execute("SELECT COUNT(*) as total FROM obat").fetchone()['total']
    obat_menipis = conn.execute("SELECT * FROM obat WHERE stok < 20").fetchall()
    recent_kunjungan = conn.execute('''
        SELECT k.tanggal, p.nama
        FROM kunjungan k
        JOIN rekam_medis r ON k.rekam_medis_id = r.id
        JOIN pasien p ON r.pasien_id = p.id
        ORDER BY k.tanggal DESC LIMIT 5
    ''').fetchall()
    conn.close()
    return render_template('dashboard.html',
                         total_pasien=total_pasien,
                         kunjungan_hari_ini=kunjungan_hari_ini,
                         total_obat=total_obat,
                         obat_menipis=obat_menipis,
                         recent_kunjungan=recent_kunjungan,
                         today=today)

@app.route('/pasien/baru', methods=['GET', 'POST'])
@login_required
def pasien_baru():
    if request.method == 'POST':
        nama = request.form['nama']
        tgl_lahir = request.form['tgl_lahir']
        alamat = request.form['alamat']
        no_telp = request.form['no_telp']
        conn = get_db()
        conn.execute("INSERT INTO pasien (nama, tgl_lahir, alamat, no_telp) VALUES (?,?,?,?)",
                     (nama, tgl_lahir, alamat, no_telp))
        conn.commit()
        pasien_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.close()
        return redirect(url_for('rekam_medis', pasien_id=pasien_id))
    return render_template('pasien_baru.html')

@app.route('/cari_pasien')
@login_required
def cari_pasien():
    keyword = request.args.get('q', '')
    conn = get_db()
    pasien = conn.execute("SELECT * FROM pasien WHERE nama LIKE ? LIMIT 10", (f'%{keyword}%',)).fetchall()
    conn.close()
    return render_template('cari_pasien.html', pasien=pasien, keyword=keyword)

@app.route('/rekam_medis/<int:pasien_id>', methods=['GET', 'POST'])
@login_required
def rekam_medis(pasien_id):
    conn = get_db()
    if request.method == 'POST':
        subj = request.form['subjective']
        obj = request.form['objective']
        ass = request.form['assessment']
        plan = request.form['planning']
        tgl = now_wita()
        cur = conn.execute("INSERT INTO rekam_medis (pasien_id, tanggal, subjective, objective, assessment, planning) VALUES (?,?,?,?,?,?)",
                           (pasien_id, tgl, subj, obj, ass, plan))
        rm_id = cur.lastrowid
        conn.execute("INSERT INTO kunjungan (rekam_medis_id, tanggal) VALUES (?,?)", (rm_id, date_wita()))
        conn.commit()
        conn.close()
        return redirect(url_for('resep', rm_id=rm_id))
    pasien = conn.execute("SELECT * FROM pasien WHERE id=?", (pasien_id,)).fetchone()
    conn.close()
    return render_template('rekam_medis.html', pasien=pasien)

@app.route('/resep/<int:rm_id>', methods=['GET', 'POST'])
@login_required
def resep(rm_id):
    conn = get_db()
    obat_list = conn.execute("SELECT * FROM obat").fetchall()
    if request.method == 'POST':
        obat_id = request.form['obat_id']
        jumlah = int(request.form['jumlah'])
        aturan = request.form['aturan']
        stok = conn.execute("SELECT stok FROM obat WHERE id=?", (obat_id,)).fetchone()['stok']
        if stok >= jumlah:
            conn.execute("UPDATE obat SET stok = stok - ? WHERE id = ?", (jumlah, obat_id))
            conn.execute("INSERT INTO resep (rekam_medis_id, obat_id, jumlah, aturan) VALUES (?,?,?,?)",
                         (rm_id, obat_id, jumlah, aturan))
            conn.commit()
            conn.close()
            return redirect(url_for('dashboard'))
        else:
            conn.close()
            return "Stok tidak mencukupi!", 400
    conn.close()
    return render_template('resep.html', rm_id=rm_id, obat_list=obat_list)

@app.route('/laporan')
@login_required
def laporan():
    conn = get_db()
    penyakit = conn.execute('''
        SELECT assessment, COUNT(*) as total
        FROM rekam_medis
        WHERE assessment IS NOT NULL AND assessment != ''
        GROUP BY assessment
        ORDER BY total DESC
        LIMIT 10
    ''').fetchall()
    obat_top = conn.execute('''
        SELECT o.nama, SUM(r.jumlah) as total
        FROM resep r JOIN obat o ON r.obat_id = o.id
        GROUP BY o.id
        ORDER BY total DESC
        LIMIT 10
    ''').fetchall()
    kunjungan = conn.execute('''
        SELECT tanggal, COUNT(*) as jml
        FROM kunjungan
        GROUP BY tanggal
        ORDER BY tanggal DESC
        LIMIT 30
    ''').fetchall()
    conn.close()
    return render_template('laporan.html', penyakit=penyakit, obat_top=obat_top, kunjungan=kunjungan)

@app.route('/surat_istirahat/<int:rm_id>')
@login_required
def surat_istirahat(rm_id):
    conn = get_db()
    rm = conn.execute('''
        SELECT r.*, p.nama, p.tgl_lahir
        FROM rekam_medis r
        JOIN pasien p ON r.pasien_id = p.id
        WHERE r.id = ?
    ''', (rm_id,)).fetchone()
    conn.close()
    return render_template('surat_istirahat.html', rm=rm, tgl=date_wita())

@app.route('/surat_dokter/<int:rm_id>')
@login_required
def surat_dokter(rm_id):
    conn = get_db()
    rm = conn.execute('''
        SELECT r.*, p.nama, p.tgl_lahir
        FROM rekam_medis r
        JOIN pasien p ON r.pasien_id = p.id
        WHERE r.id = ?
    ''', (rm_id,)).fetchone()
    conn.close()
    return render_template('surat_dokter.html', rm=rm, tgl=date_wita())

@app.route('/obat')
@login_required
def obat():
    conn = get_db()
    obat_list = conn.execute("SELECT * FROM obat ORDER BY nama").fetchall()
    conn.close()
    return render_template('obat.html', obat_list=obat_list)

@app.route('/obat/tambah', methods=['POST'])
@login_required
def obat_tambah():
    nama = request.form['nama']
    stok = int(request.form['stok'])
    satuan = request.form['satuan']
    conn = get_db()
    try:
        conn.execute("INSERT INTO obat (nama, stok, satuan) VALUES (?,?,?)", (nama, stok, satuan))
        conn.commit()
    except:
        pass
    conn.close()
    return redirect(url_for('obat'))

@app.route('/obat/edit/<int:obat_id>', methods=['POST'])
@login_required
def obat_edit(obat_id):
    stok = int(request.form['stok'])
    conn = get_db()
    conn.execute("UPDATE obat SET stok = ? WHERE id = ?", (stok, obat_id))
    conn.commit()
    conn.close()
    return redirect(url_for('obat'))

# INIT DATABASE (jalanin sekali)
init_db()

# Untuk PythonAnywhere
application = app
