import os
from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3
from datetime import datetime, timedelta
import pytz
from functools import wraps

app = Flask(__name__)
app.secret_key = 'rahasia_dr_galih'

WITA = pytz.timezone('Asia/Makassar')

def date_wita():
    return datetime.now(WITA).strftime('%Y-%m-%d')

def now_wita():
    return datetime.now(WITA).strftime('%Y-%m-%d %H:%M:%S')

def get_db():
    conn = sqlite3.connect('klinik.db')
    conn.row_factory = sqlite3.Row
    return conn

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'logged_in' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

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
            return redirect(url_for('dashboard'))
        return render_template('login.html', error='Username atau password salah')
    return render_template('login.html')

@app.route('/dashboard')
@login_required
def dashboard():
    conn = get_db()
    today = date_wita()
    semua_pasien = conn.execute("SELECT * FROM pasien ORDER BY id DESC").fetchall()
    total_pasien = len(semua_pasien)
    kunjungan_hari_ini = conn.execute("SELECT COUNT(*) as total FROM kunjungan WHERE tanggal=?", (today,)).fetchone()['total']
    total_obat = conn.execute("SELECT COUNT(*) as total FROM obat").fetchone()['total']
    conn.close()
    return render_template('dashboard.html',
                         semua_pasien=semua_pasien,
                         total_pasien=total_pasien,
                         kunjungan_hari_ini=kunjungan_hari_ini,
                         total_obat=total_obat,
                         today=today,
                         now_wita=now_wita)

@app.route('/pasien/baru', methods=['GET', 'POST'])
@login_required
def pasien_baru():
    conn = get_db()
    if request.method == 'POST':
        nama = request.form['nama']
        tgl_lahir = request.form['tgl_lahir']
        alamat = request.form['alamat']
        no_telp = request.form['no_telp']
        # Generate No RM otomatis
        tahun = datetime.now(WITA).strftime('%y')
        count = conn.execute("SELECT COUNT(*) as total FROM pasien").fetchone()['total']
        no_rm = f"{tahun}-{(count + 1):04d}"
        conn.execute("INSERT INTO pasien (no_rm, nama, tgl_lahir, alamat, no_telp) VALUES (?,?,?,?,?)",
                     (no_rm, nama, tgl_lahir, alamat, no_telp))
        conn.commit()
        pasien_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.close()
        return redirect(url_for('rekam_medis', pasien_id=pasien_id))
    conn.close()
    return render_template('pasien_baru.html')

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
        lampiran = request.form.get('lampiran_mega', '')
        cur = conn.execute("INSERT INTO rekam_medis (pasien_id, tanggal, subjective, objective, assessment, planning, lampiran_mega) VALUES (?,?,?,?,?,?,?)",
                           (pasien_id, tgl, subj, obj, ass, plan, lampiran))
        rm_id = cur.lastrowid
        conn.execute("INSERT INTO kunjungan (rekam_medis_id, tanggal) VALUES (?,?)", (rm_id, date_wita()))
        conn.commit()
        conn.close()
        return redirect(url_for('resep', rm_id=rm_id))

    # Ambil data pasien
    pasien = conn.execute("SELECT * FROM pasien WHERE id=?", (pasien_id,)).fetchone()

    # Ambil riwayat kunjungan sebelumnya (urut dari yang terbaru)
    riwayat = conn.execute('''
        SELECT r.*, strftime('%d-%m-%Y %H:%M', r.tanggal) as tgl_format
        FROM rekam_medis r
        WHERE r.pasien_id = ?
        ORDER BY r.tanggal DESC
    ''', (pasien_id,)).fetchall()

    # Ambil daftar ICD-10
    icd_list = conn.execute("SELECT * FROM icd10 ORDER BY kode").fetchall()
    conn.close()

    return render_template('rekam_medis.html', pasien=pasien, icd_list=icd_list, riwayat=riwayat)

@app.route('/resep/<int:rm_id>', methods=['GET', 'POST'])
@login_required
def resep(rm_id):
    conn = get_db()
    obat_list = conn.execute("SELECT * FROM obat ORDER BY nama").fetchall()
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

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/cari_pasien')
@login_required
def cari_pasien():
    keyword = request.args.get('q', '')
    conn = get_db()
    if keyword:
        pasien = conn.execute("SELECT * FROM pasien WHERE nama LIKE ? ORDER BY nama", (f'%{keyword}%',)).fetchall()
    else:
        pasien = []
    conn.close()
    return render_template('cari_pasien.html', pasien=pasien, keyword=keyword)

if __name__ == '__main__':
    # Buat database jika belum ada
    if not os.path.exists('klinik.db'):
        conn = sqlite3.connect('klinik.db')
        c = conn.cursor()
        c.execute('CREATE TABLE user (username TEXT PRIMARY KEY, password TEXT)')
        c.execute("INSERT INTO user VALUES ('admin', 'admin123')")
        c.execute('CREATE TABLE pasien (id INTEGER PRIMARY KEY AUTOINCREMENT, no_rm TEXT, nama TEXT, tgl_lahir TEXT, alamat TEXT, no_telp TEXT)')
        c.execute('CREATE TABLE rekam_medis (id INTEGER PRIMARY KEY AUTOINCREMENT, pasien_id INTEGER, tanggal TEXT, subjective TEXT, objective TEXT, assessment TEXT, planning TEXT, lampiran_mega TEXT)')
        c.execute('CREATE TABLE obat (id INTEGER PRIMARY KEY AUTOINCREMENT, nama TEXT UNIQUE, stok INTEGER, satuan TEXT)')
        c.execute('CREATE TABLE resep (id INTEGER PRIMARY KEY AUTOINCREMENT, rekam_medis_id INTEGER, obat_id INTEGER, jumlah INTEGER, aturan TEXT)')
        c.execute('CREATE TABLE kunjungan (id INTEGER PRIMARY KEY AUTOINCREMENT, rekam_medis_id INTEGER, tanggal TEXT)')
        # Data awal obat
        c.execute("INSERT INTO obat (nama, stok, satuan) VALUES ('Parasetamol', 100, 'tablet')")
        c.execute("INSERT INTO obat (nama, stok, satuan) VALUES ('Amoksisilin', 50, 'kapsul')")
        conn.commit()
        conn.close()
        print("✅ Database baru berhasil dibuat")

    app.run(debug=True, host='0.0.0.0', port=5000)
