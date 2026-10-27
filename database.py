import sqlite3

DATABASE = "documind.db"


def get_connection():
    conn = sqlite3.connect(DATABASE, timeout=10.0)
    conn.row_factory = sqlite3.Row
    return conn


def init_database():
    try:
        conn = get_connection()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS search_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                search_query TEXT NOT NULL,
                searched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Database init warning: {e}")


def save_search(search_query):
    query = str(search_query or "").strip()
    if not query:
        return
    try:
        conn = get_connection()
        # Avoid storing duplicate search query consecutively
        conn.execute("DELETE FROM search_history WHERE LOWER(search_query) = LOWER(?)", (query,))
        conn.execute("INSERT INTO search_history (search_query) VALUES (?)", (query,))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Database save warning: {e}")


def get_search_history(limit=10):
    try:
        conn = get_connection()
        rows = conn.execute("""
            SELECT id, search_query, searched_at
            FROM search_history
            ORDER BY searched_at DESC, id DESC
            LIMIT ?
        """, (limit,)).fetchall()
        conn.close()
        return [dict(row) for row in rows]
    except Exception as e:
        print(f"Database read warning: {e}")
        return []
