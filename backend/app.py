# backend/app.py
from flask import Flask, jsonify, request
import sqlite3
import os
from flask_cors import CORS
import requests # <--- ADDED THIS LINE

app = Flask(__name__)
CORS(app)

DATABASE_FILE = 'pg_explorer.db'

def get_db_connection():
    conn = sqlite3.connect(DATABASE_FILE)
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
def index():
    return "Project Gutenberg Explorer Backend is running!"

@app.route('/books', methods=['GET'])
def get_books():
    conn = get_db_connection()
    cursor = conn.cursor()

    query = "SELECT gutenberg_id, title, author, language, download_link FROM books WHERE 1=1"
    params = []

    search_term = request.args.get('search')
    if search_term:
        query += " AND (title LIKE ? OR author LIKE ?)"
        params.append(f"%{search_term}%")
        params.append(f"%{search_term}%")

    language_filter = request.args.get('lang')
    if language_filter:
        query += " AND language = ?"
        params.append(language_filter)

    limit = request.args.get('limit', 50, type=int)
    offset = request.args.get('offset', 0, type=int)

    query += " LIMIT ? OFFSET ?"
    params.append(limit)
    params.append(offset)

    cursor.execute(query, params)
    books = cursor.fetchall()
    conn.close()

    books_list = [dict(row) for row in books]
    return jsonify(books_list)

@app.route('/languages', methods=['GET'])
def get_languages():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT language FROM books WHERE language IS NOT NULL ORDER BY language")
    languages = [row[0] for row in cursor.fetchall()]
    conn.close()
    return jsonify(languages)

# --- NEW ENDPOINT TO FETCH BOOK CONTENT ---
@app.route('/book_content/<int:gutenberg_id>', methods=['GET'])
def get_book_content(gutenberg_id):
    book_url = f"https://www.gutenberg.org/files/{gutenberg_id}/{gutenberg_id}-0.txt"
    try:
        response = requests.get(book_url, timeout=10)
        response.raise_for_status()
        return response.text, 200, {'Content-Type': 'text/plain; charset=utf-8'}
    except requests.exceptions.RequestException as e:
        print(f"Error fetching book content for ID {gutenberg_id}: {e}")
        return jsonify({"error": f"Could not fetch book content. Details: {str(e)}"}), 500
    except Exception as e:
        print(f"An unexpected error occurred while fetching book content for ID {gutenberg_id}: {e}")
        return jsonify({"error": f"An unexpected server error occurred. Details: {str(e)}"}), 500

if __name__ == '__main__':
    if not os.path.exists(DATABASE_FILE):
        print(f"Database '{DATABASE_FILE}' not found. Please run 'python setup_database.py' first.")
        exit()
    app.run(debug=True, port=5000)