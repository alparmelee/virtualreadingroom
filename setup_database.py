# setup_database.py
import sqlite3
import pandas as pd
import requests
import gzip
import io
import os

DATABASE_FILE = 'backend/pg_explorer.db'
CATALOG_URL = 'https://www.gutenberg.org/cache/epub/feeds/pg_catalog.csv.gz'

def download_and_extract_catalog(url):
    """Downloads the gzipped CSV catalog and returns its content."""
    print(f"Downloading catalog from: {url}")
    try:
        response = requests.get(url, stream=True)
        response.raise_for_status() # Raise an exception for HTTP errors (4xx or 5xx)

        # Check if content is gzipped
        if response.headers.get('Content-Encoding') == 'gzip' or url.endswith('.gz'):
            print("Content is gzipped. Decompressing...")
            gzipped_file = io.BytesIO(response.content)
            with gzip.open(gzipped_file, 'rt', encoding='utf-8') as f:
                return f.read()
        else:
            print("Content is not gzipped. Assuming plain CSV.")
            return response.text
    except requests.exceptions.RequestException as e:
        print(f"Error downloading catalog: {e}")
        return None

def create_and_populate_db(db_file, catalog_csv_content):
    """Creates SQLite database and populates it with book data from CSV."""
    if not catalog_csv_content:
        print("No catalog content to process. Database not populated.")
        return

    # Ensure the backend directory exists
    os.makedirs(os.path.dirname(db_file), exist_ok=True)

    conn = None
    try:
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()

        # Create books table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS books (
                gutenberg_id INTEGER PRIMARY KEY,
                title TEXT NOT NULL,
                author TEXT,
                language TEXT,
                download_link TEXT
            )
        ''')
        conn.commit()

        # Read CSV data using pandas for easier parsing
        # Use StringIO to treat the string content as a file
        df = pd.read_csv(io.StringIO(catalog_csv_content))
        print("Columns found in CSV:", df.columns.tolist()) # ADD THIS LINE

        # Filter and process data
        # We'll focus on English plain text books for simplicity and commonality
        filtered_df = df[
            (df['Language'].str.contains('en', na=False)) &
            (df['Type'] == 'Text')
        ].copy() # Use .copy() to avoid SettingWithCopyWarning

        # Create download link (using a common plain text format)
        # Project Gutenberg standard download link format for plain text:
        # http://www.gutenberg.org/ebooks/{id}.txt.utf8
        filtered_df['download_link'] = filtered_df['Text#'].apply(
        lambda x: f"https://www.gutenberg.org/files/{x}/{x}.txt"
    )
# Clean up author field (remove dates, roles, etc.)
        # NOTICE THE CHANGE FROM 'Author' to 'Authors' HERE
        filtered_df['Authors'] = filtered_df['Authors'].str.split(',').str[0].str.strip()
        filtered_df['Authors'] = filtered_df['Authors'].replace({'[Noel, E. (Eugene)]': 'Unknown', '[Anonymous]': 'Anonymous', '': 'Unknown'})

        # Select relevant columns and rename for database
        # NOTICE THE CHANGE FROM 'Author' to 'Authors' HERE
        books_to_insert = filtered_df[['Text#', 'Title', 'Authors', 'Language', 'download_link']]
        books_to_insert = books_to_insert.rename(columns={
            'Text#': 'gutenberg_id',
            'Title': 'title',
            'Authors': 'author', # AND THIS MAPPING: 'Authors' to 'author'
            'Language': 'language'
        })

        # Insert data into the database
        # Use iterrows to iterate and insert, or to_sql for pandas (less control over primary key)
        # Let's use executemany for efficiency
        book_data = books_to_insert.values.tolist()
        print(f"Inserting {len(book_data)} books into the database...")
        cursor.executemany('''
            INSERT OR IGNORE INTO books (gutenberg_id, title, author, language, download_link)
            VALUES (?, ?, ?, ?, ?)
        ''', book_data)
        conn.commit()
        print("Database populated successfully!")

    except sqlite3.Error as e:
        print(f"SQLite error: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    catalog_content = download_and_extract_catalog(CATALOG_URL)
    if catalog_content:
        create_and_populate_db(DATABASE_FILE, catalog_content)
    else:
        print("Failed to download catalog. Cannot set up database.")