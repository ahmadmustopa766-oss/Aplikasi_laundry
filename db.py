import sqlite3
from werkzeug.security import generate_password_hash

DB_NAME = "laundry.db"

def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. Tabel Users (owner, anggota, pelanggan)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            nama TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('owner', 'anggota', 'pelanggan'))
        )
    """)

    # 2. Tabel Transaksi (pemasukan & pengeluaran)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS transaksi (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tanggal TEXT NOT NULL,
            jenis TEXT NOT NULL CHECK(jenis IN ('pemasukan', 'pengeluaran')),
            kategori TEXT NOT NULL,
            keterangan TEXT NOT NULL,
            nominal INTEGER NOT NULL,
            dicatat_oleh TEXT NOT NULL
        )
    """)

    # 3. Seed akun default jika tabel users masih kosong
    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] == 0:
        default_users = [
            ("owner", generate_password_hash("owner123"), "Pemilik Laundry", "owner"),
            ("anggota", generate_password_hash("anggota123"), "Staf Kasir", "anggota"),
            ("pelanggan", generate_password_hash("pelanggan123"), "Pelanggan Setia", "pelanggan"),
        ]
        cursor.executemany(
            "INSERT INTO users (username, password, nama, role) VALUES (?, ?, ?, ?)",
            default_users
        )

    # 4. Seed contoh transaksi awal jika tabel transaksi masih kosong
    cursor.execute("SELECT COUNT(*) FROM transaksi")
    if cursor.fetchone()[0] == 0:
        sample_transaksi = [
            ("2026-11-20", "pemasukan", "Cuci Komplit", "Order #001 - 5 kg pakaian", 35000, "Staf Kasir"),
            ("2026-11-21", "pemasukan", "Cuci Express", "Order #002 - 3 kg + Bedcover", 55000, "Staf Kasir"),
            ("2026-11-22", "pengeluaran", "Bahan Baku", "Beli deterjen cair & parfum laundry", 40000, "Staf Kasir"),
            ("2026-11-23", "pemasukan", "Setrika Saja", "Order #003 - 4 kg pakaian", 20000, "Staf Kasir"),
        ]
        cursor.executemany(
            """INSERT INTO transaksi (tanggal, jenis, kategori, keterangan, nominal, dicatat_oleh)
               VALUES (?, ?, ?, ?, ?, ?)""",
            sample_transaksi
        )

    conn.commit()
    conn.close()
    print("Database laundry.db berhasil diinisiasi!")

if __name__ == "__main__":
    init_db()