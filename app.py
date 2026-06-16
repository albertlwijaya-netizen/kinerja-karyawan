from flask import Flask, render_template, request, redirect, url_for, session, flash
from database import get_db_connection
# Import generate/check tetap dibiarkan agar tidak error jika ada library lain yang memanggil, 
# tapi tidak kita gunakan untuk pengecekan lagi.
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import datetime

app = Flask(__name__)
app.secret_key = 'kunci_rahasia_anda_yang_sangat_kuat'

# --- DECORATOR KEAMANAN ---
def login_required(role=None):
    def wrapper(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'logged_in' not in session:
                return redirect(url_for('login'))
            if role and session.get('role') != role:
                return "Akses Ditolak: Anda tidak memiliki izin untuk halaman ini.", 403
            return f(*args, **kwargs)
        return decorated_function
    return wrapper

# --- AUTHENTICATION ---
@app.route('/')
def index():
    if 'logged_in' in session:
        return redirect(url_for('admin_dashboard' if session['role'] == 'Admin' else 'karyawan_dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE username = %s", (username,))
        user = cur.fetchone()
        conn.close()

        # PERUBAHAN DISINI: Menggunakan perbandingan langsung (teks biasa)
        if user and user['password'] == password:
            session['logged_in'] = True
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role']
            
            flash(f'Selamat datang, {user["username"]}!', 'success')
            return redirect(url_for('admin_dashboard' if user['role'] == 'Admin' else 'karyawan_dashboard'))
        
        flash('Username atau Password salah!', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Anda telah keluar.', 'info')
    return redirect(url_for('login'))

# --- MODUL ADMIN: DASHBOARD ---
@app.route('/admin/dashboard')
@login_required('Admin')
def admin_dashboard():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) as total FROM karyawan")
    k_count = cur.fetchone()['total']
    cur.execute("SELECT COUNT(*) as total FROM divisi")
    d_count = cur.fetchone()['total']
    cur.execute("SELECT COUNT(*) as total FROM aktivitas")
    a_count = cur.fetchone()['total']
    cur.execute("SELECT COUNT(*) as total FROM penilaian")
    p_count = cur.fetchone()['total']
    
    cur.execute("""
        SELECT a.*, k.nama FROM aktivitas a 
        JOIN karyawan k ON a.karyawan_id = k.id_karyawan 
        ORDER BY id_aktivitas DESC LIMIT 5
    """)
    recent_activities = cur.fetchall()
    
    conn.close()
    return render_template('admin/dashboard.html', 
                           k_count=k_count, d_count=d_count, 
                           a_count=a_count, p_count=p_count,
                           activities=recent_activities)

# --- MODUL ADMIN: DIVISI (CRUD) ---
@app.route('/admin/divisi')
@login_required('Admin')
def admin_divisi():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM divisi")
    divisi = cur.fetchall()
    conn.close()
    return render_template('admin/divisi.html', divisi=divisi)

@app.route('/admin/divisi/add', methods=['POST'])
@login_required('Admin')
def add_divisi():
    nama = request.form['nama_divisi']
    deskripsi = request.form['deskripsi']
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("INSERT INTO divisi (nama_divisi, deskripsi) VALUES (%s, %s)", (nama, deskripsi))
    conn.commit()
    conn.close()
    flash('Divisi berhasil ditambahkan', 'success')
    return redirect(url_for('admin_divisi'))

@app.route('/admin/divisi/delete/<int:id>')
@login_required('Admin')
def delete_divisi(id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM divisi WHERE id_divisi = %s", (id,))
    conn.commit()
    conn.close()
    flash('Divisi berhasil dihapus', 'warning')
    return redirect(url_for('admin_divisi'))

# --- MODUL ADMIN: KARYAWAN (CRUD) ---
@app.route('/admin/karyawan')
@login_required('Admin')
def admin_karyawan():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT k.*, d.nama_divisi 
        FROM karyawan k 
        LEFT JOIN divisi d ON k.divisi_id = d.id_divisi
    """)
    karyawan_data = cur.fetchall()
    cur.execute("SELECT * FROM divisi")
    divisi_list = cur.fetchall()
    conn.close()
    return render_template('admin/karyawan.html', karyawan=karyawan_data, divisi=divisi_list)

@app.route('/admin/karyawan/add', methods=['POST'])
@login_required('Admin')
def add_karyawan():
    data = request.form
    # PERUBAHAN DISINI: Langsung ambil password tanpa di-hash
    password_biasa = data['password']

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # Masukkan password_biasa langsung
        cur.execute("INSERT INTO users (username, password, role) VALUES (%s, %s, 'Karyawan')", 
                    (data['username'], password_biasa))
        user_id = cur.lastrowid
        
        cur.execute("""
            INSERT INTO karyawan (user_id, nik, nama, jk, jabatan, divisi_id, email, no_hp, tanggal_bergabung)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (user_id, data['nik'], data['nama'], data['jk'], data['jabatan'], 
              data['divisi_id'], data['email'], data['no_hp'], data['tanggal_bergabung']))
        conn.commit()
        flash('Data Karyawan berhasil ditambahkan', 'success')
    except Exception as e:
        conn.rollback()
        flash(f'Gagal: {str(e)}', 'danger')
    finally:
        conn.close()
    return redirect(url_for('admin_karyawan'))

@app.route('/admin/karyawan/delete/<int:id>')
@login_required('Admin')
def delete_karyawan(id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT user_id FROM karyawan WHERE id_karyawan = %s", (id,))
    res = cur.fetchone()
    if res:
        user_id = res['user_id']
        cur.execute("DELETE FROM users WHERE id = %s", (user_id,))
        conn.commit()
    conn.close()
    flash('Karyawan berhasil dihapus', 'warning')
    return redirect(url_for('admin_karyawan'))

# --- MODUL ADMIN: PENILAIAN ---
@app.route('/admin/penilaian', methods=['GET', 'POST'])
@login_required('Admin')
def admin_penilaian():
    conn = get_db_connection()
    cur = conn.cursor()
    if request.method == 'POST':
        k_id = request.form['karyawan_id']
        p1 = float(request.form['kehadiran'])
        p2 = float(request.form['disiplin'])
        p3 = float(request.form['produktivitas'])
        p4 = float(request.form['kerjasama'])
        nilai_akhir = (p1 + p2 + p3 + p4) / 4
        
        cur.execute("""
            INSERT INTO penilaian (karyawan_id, periode, kehadiran, disiplin, produktivitas, kerjasama, nilai_akhir, catatan)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (k_id, request.form['periode'], p1, p2, p3, p4, nilai_akhir, request.form['catatan']))
        conn.commit()
        flash('Penilaian berhasil disimpan', 'success')

    cur.execute("SELECT id_karyawan, nama FROM karyawan")
    karyawan_list = cur.fetchall()
    cur.execute("""
        SELECT p.*, k.nama FROM penilaian p 
        JOIN karyawan k ON p.karyawan_id = k.id_karyawan
        ORDER BY id_penilaian DESC
    """)
    penilaian_data = cur.fetchall()
    conn.close()
    return render_template('admin/penilaian.html', karyawan=karyawan_list, penilaian=penilaian_data)

# --- MODUL ADMIN: LAPORAN ---
@app.route('/admin/laporan')
@login_required('Admin')
def admin_laporan():
    divisi_id = request.args.get('divisi_id')
    conn = get_db_connection()
    cur = conn.cursor()
    
    query = """
        SELECT p.*, k.nama, d.nama_divisi 
        FROM penilaian p
        JOIN karyawan k ON p.karyawan_id = k.id_karyawan
        JOIN divisi d ON k.divisi_id = d.id_divisi
        WHERE 1=1
    """
    params = []
    if divisi_id:
        query += " AND d.id_divisi = %s"
        params.append(divisi_id)
        
    cur.execute(query, params)
    laporan = cur.fetchall()
    
    cur.execute("SELECT * FROM divisi")
    divisi_list = cur.fetchall()
    conn.close()
    return render_template('admin/laporan.html', laporan=laporan, divisi=divisi_list)

# --- MODUL KARYAWAN: DASHBOARD ---
@app.route('/karyawan/dashboard')
@login_required('Karyawan')
def karyawan_dashboard():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id_karyawan FROM karyawan WHERE user_id = %s", (session['user_id'],))
    k_res = cur.fetchone()
    
    if not k_res:
        return "Profil Karyawan tidak ditemukan", 404
        
    k_id = k_res['id_karyawan']
    cur.execute("SELECT COUNT(*) as total FROM aktivitas WHERE karyawan_id = %s", (k_id,))
    total_act = cur.fetchone()['total']
    
    cur.execute("SELECT * FROM penilaian WHERE karyawan_id = %s ORDER BY id_penilaian DESC LIMIT 1", (k_id,))
    last_score = cur.fetchone()
    
    cur.execute("SELECT * FROM aktivitas WHERE karyawan_id = %s ORDER BY id_aktivitas DESC LIMIT 5", (k_id,))
    recent_acts = cur.fetchall()
    conn.close()
    return render_template('karyawan/dashboard.html', total_act=total_act, last_score=last_score, activities=recent_acts)

# --- MODUL KARYAWAN: AKTIVITAS ---
@app.route('/karyawan/aktivitas')
@login_required('Karyawan')
def karyawan_aktivitas():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id_karyawan FROM karyawan WHERE user_id = %s", (session['user_id'],))
    k_id = cur.fetchone()['id_karyawan']
    
    cur.execute("SELECT * FROM aktivitas WHERE karyawan_id = %s ORDER BY tanggal DESC", (k_id,))
    aktivitas = cur.fetchall()
    conn.close()
    return render_template('karyawan/aktivitas.html', aktivitas=aktivitas)

@app.route('/karyawan/aktivitas/add', methods=['POST'])
@login_required('Karyawan')
def add_aktivitas():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id_karyawan FROM karyawan WHERE user_id = %s", (session['user_id'],))
    k_id = cur.fetchone()['id_karyawan']
    
    cur.execute("""
        INSERT INTO aktivitas (karyawan_id, tanggal, aktivitas, target, hasil, status)
        VALUES (%s, %s, %s, %s, %s, %s)
    """, (k_id, request.form['tanggal'], request.form['aktivitas'], 
          request.form['target'], request.form['hasil'], request.form['status']))
    conn.commit()
    conn.close()
    flash('Aktivitas berhasil dicatat', 'success')
    return redirect(url_for('karyawan_aktivitas'))

@app.route('/karyawan/aktivitas/delete/<int:id>')
@login_required('Karyawan')
def delete_aktivitas(id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM aktivitas WHERE id_aktivitas = %s", (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('karyawan_aktivitas'))

if __name__ == '__main__':
    app.run(debug=True)