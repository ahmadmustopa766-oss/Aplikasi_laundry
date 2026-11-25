from datetime import date
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import check_password_hash
from db import get_db_connection, init_db

app = Flask(__name__)
app.secret_key = "kunci-rahasia-aplikasi-laundry-2026"


# --- Filter Custom untuk Format Rupiah di Template ---
@app.template_filter("rupiah")
def format_rupiah(nilai):
    if nilai is None:
        return "Rp 0"
    nilai = int(nilai)
    if nilai < 0:
        return f"-Rp {abs(nilai):,}".replace(",", ".")
    return f"Rp {nilai:,}".replace(",", ".")


# --- Decorator Proteksi Login & Role ---
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            flash("Silakan login terlebih dahulu.", "warning")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function


def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if "user_id" not in session:
                flash("Silakan login terlebih dahulu.", "warning")
                return redirect(url_for("login"))
            if session.get("role") not in roles:
                flash("Anda tidak memiliki akses ke halaman tersebut.", "danger")
                return redirect(url_for("dashboard_redirect"))
            return f(*args, **kwargs)
        return decorated_function
    return decorator


# --- Fungsi Helper Ambil Data & Hitung Keuntungan ---
def get_laporan_keuangan(filter_jenis="semua"):
    conn = get_db_connection()

    # Hitung ringkasan keseluruhan (tidak terpengaruh filter tabel)
    ringkasan = conn.execute("""
        SELECT
            COALESCE(SUM(CASE WHEN jenis = 'pemasukan' THEN nominal ELSE 0 END), 0) AS total_pemasukan,
            COALESCE(SUM(CASE WHEN jenis = 'pengeluaran' THEN nominal ELSE 0 END), 0) AS total_pengeluaran
        FROM transaksi
    """).fetchone()

    total_pemasukan = ringkasan["total_pemasukan"]
    total_pengeluaran = ringkasan["total_pengeluaran"]
    keuntungan = total_pemasukan - total_pengeluaran

    # Ambil daftar transaksi sesuai filter
    if filter_jenis in ("pemasukan", "pengeluaran"):
        transaksi = conn.execute(
            "SELECT * FROM transaksi WHERE jenis = ? ORDER BY tanggal DESC, id DESC",
            (filter_jenis,)
        ).fetchall()
    else:
        transaksi = conn.execute(
            "SELECT * FROM transaksi ORDER BY tanggal DESC, id DESC"
        ).fetchall()

    conn.close()
    return {
        "total_pemasukan": total_pemasukan,
        "total_pengeluaran": total_pengeluaran,
        "keuntungan": keuntungan,
        "transaksi": transaksi,
    }


# --- Route Utama & Autentikasi ---
@app.route("/")
def dashboard_redirect():
    role = session.get("role")
    if role == "owner":
        return redirect(url_for("dashboard_owner"))
    elif role == "anggota":
        return redirect(url_for("dashboard_anggota"))
    elif role == "pelanggan":
        return redirect(url_for("dashboard_pelanggan"))
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if "user_id" in session:
        return redirect(url_for("dashboard_redirect"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        conn = get_db_connection()
        user = conn.execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        ).fetchone()
        conn.close()

        if user and check_password_hash(user["password"], password):
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["nama"] = user["nama"]
            session["role"] = user["role"]
            flash(f"Selamat datang, {user['nama']}!", "success")
            return redirect(url_for("dashboard_redirect"))

        flash("Username atau password salah.", "danger")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("Anda telah berhasil logout.", "info")
    return redirect(url_for("login"))


# --- Route Dashboard Per Role ---
@app.route("/owner")
@role_required("owner")
def dashboard_owner():
    filter_jenis = request.args.get("jenis", "semua")
    data = get_laporan_keuangan(filter_jenis)
    return render_template(
        "owner.html",
        **data,
        filter_jenis=filter_jenis,
        today=date.today().isoformat()
    )


@app.route("/anggota")
@role_required("anggota")
def dashboard_anggota():
    filter_jenis = request.args.get("jenis", "semua")
    data = get_laporan_keuangan(filter_jenis)
    return render_template(
        "anggota.html",
        **data,
        filter_jenis=filter_jenis,
        today=date.today().isoformat()
    )


@app.route("/pelanggan")
@role_required("pelanggan")
def dashboard_pelanggan():
    filter_jenis = request.args.get("jenis", "semua")
    data = get_laporan_keuangan(filter_jenis)
    return render_template(
        "pelanggan.html",
        **data,
        filter_jenis=filter_jenis
    )


# --- Route CRUD Transaksi ---
@app.route("/transaksi/tambah", methods=["POST"])
@role_required("owner", "anggota")
def tambah_transaksi():
    tanggal = request.form.get("tanggal", "").strip()
    jenis = request.form.get("jenis", "").strip()
    kategori = request.form.get("kategori", "").strip()
    keterangan = request.form.get("keterangan", "").strip()
    nominal_str = request.form.get("nominal", "").strip()

    if not all([tanggal, jenis, kategori, keterangan, nominal_str]):
        flash("Semua kolom wajib diisi.", "danger")
        return redirect(url_for("dashboard_redirect"))

    if jenis not in ("pemasukan", "pengeluaran"):
        flash("Jenis transaksi tidak valid.", "danger")
        return redirect(url_for("dashboard_redirect"))

    try:
        nominal = int(nominal_str)
        if nominal <= 0:
            raise ValueError
    except ValueError:
        flash("Nominal harus berupa angka lebih dari 0.", "danger")
        return redirect(url_for("dashboard_redirect"))

    conn = get_db_connection()
    conn.execute(
        """INSERT INTO transaksi (tanggal, jenis, kategori, keterangan, nominal, dicatat_oleh)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (tanggal, jenis, kategori, keterangan, nominal, session["nama"])
    )
    conn.commit()
    conn.close()

    flash("Data transaksi berhasil dicatat.", "success")
    return redirect(url_for("dashboard_redirect"))


@app.route("/transaksi/edit/<int:id>", methods=["POST"])
@role_required("owner")
def edit_transaksi(id):
    tanggal = request.form.get("tanggal", "").strip()
    jenis = request.form.get("jenis", "").strip()
    kategori = request.form.get("kategori", "").strip()
    keterangan = request.form.get("keterangan", "").strip()
    nominal_str = request.form.get("nominal", "").strip()

    if not all([tanggal, jenis, kategori, keterangan, nominal_str]) or jenis not in ("pemasukan", "pengeluaran"):
        flash("Data pembaruan tidak valid.", "danger")
        return redirect(url_for("dashboard_owner"))

    try:
        nominal = int(nominal_str)
        if nominal <= 0:
            raise ValueError
    except ValueError:
        flash("Nominal harus berupa angka lebih dari 0.", "danger")
        return redirect(url_for("dashboard_owner"))

    conn = get_db_connection()
    conn.execute(
        """UPDATE transaksi
           SET tanggal = ?, jenis = ?, kategori = ?, keterangan = ?, nominal = ?
           WHERE id = ?""",
        (tanggal, jenis, kategori, keterangan, nominal, id)
    )
    conn.commit()
    conn.close()

    flash("Data transaksi berhasil diperbarui.", "success")
    return redirect(url_for("dashboard_owner"))


@app.route("/transaksi/hapus/<int:id>", methods=["POST"])
@role_required("owner")
def hapus_transaksi(id):
    conn = get_db_connection()
    conn.execute("DELETE FROM transaksi WHERE id = ?", (id,))
    conn.commit()
    conn.close()

    flash("Data transaksi berhasil dihapus.", "info")
    return redirect(url_for("dashboard_owner"))


if __name__ == "__main__":
    init_db()
    app.run(debug=True)