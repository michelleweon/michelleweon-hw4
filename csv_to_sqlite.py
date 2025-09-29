#!/usr/bin/env python3
"""
CSV to SQLite Converter

This script converts CSV files to SQLite databases.
It takes two command line arguments:
1. The name of the SQLite database file (e.g., data.db)
2. The name of the CSV file to convert

Usage:
    python csv_to_sqlite.py data.db input.csv
"""

import sys
import csv
import sqlite3
import os
from pathlib import Path


def create_table_from_csv(cursor, csv_file, table_name):
    """
    Create a SQLite table from a CSV file.
    
    Args:
        cursor: SQLite database cursor
        csv_file: Path to the CSV file
        table_name: Name for the SQLite table
    """
    with open(csv_file, 'r', newline='', encoding='utf-8') as file:
        # Read the first row to get column names
        reader = csv.reader(file)
        headers = next(reader)
        
        # Clean column names to be valid SQL identifiers
        clean_headers = []
        for header in headers:
            # Remove spaces and special characters, replace with underscores
            clean_header = ''.join(c if c.isalnum() else '_' for c in header.strip())
            # Ensure it starts with a letter or underscore
            if clean_header and not clean_header[0].isalpha():
                clean_header = 'col_' + clean_header
            # Handle empty headers
            if not clean_header:
                clean_header = 'col_' + str(len(clean_headers))
            clean_headers.append(clean_header)
        
        # Create table with TEXT columns for all fields
        columns = ', '.join([f'"{col}" TEXT' for col in clean_headers])
        create_table_sql = f'CREATE TABLE IF NOT EXISTS "{table_name}" ({columns})'
        cursor.execute(create_table_sql)
        
        # Reset file pointer to beginning
        file.seek(0)
        reader = csv.reader(file)
        next(reader)  # Skip header row
        
        # Insert data
        placeholders = ', '.join(['?' for _ in clean_headers])
        insert_sql = f'INSERT INTO "{table_name}" VALUES ({placeholders})'
        
        for row in reader:
            # Pad row with empty strings if it's shorter than expected
            while len(row) < len(clean_headers):
                row.append('')
            # Truncate row if it's longer than expected
            row = row[:len(clean_headers)]
            cursor.execute(insert_sql, row)


def main():
    """Main function to handle command line arguments and convert CSV to SQLite."""
    if len(sys.argv) != 3:
        print("Usage: python csv_to_sqlite.py <database_name> <csv_file>")
        print("Example: python csv_to_sqlite.py data.db input.csv")
        sys.exit(1)
    
    db_name = sys.argv[1]
    csv_file = sys.argv[2]
    
    # Check if CSV file exists
    if not os.path.exists(csv_file):
        print(f"Error: CSV file '{csv_file}' not found.")
        sys.exit(1)
    
    # Check if CSV file is readable
    if not os.access(csv_file, os.R_OK):
        print(f"Error: Cannot read CSV file '{csv_file}'.")
        sys.exit(1)
    
    try:
        # Create or connect to SQLite database
        conn = sqlite3.connect(db_name)
        cursor = conn.cursor()
        
        # Get table name from CSV filename (without extension)
        table_name = Path(csv_file).stem
        
        print(f"Converting '{csv_file}' to SQLite table '{table_name}' in database '{db_name}'...")
        
        # Create table and insert data
        create_table_from_csv(cursor, csv_file, table_name)
        
        # Commit changes and close connection
        conn.commit()
        conn.close()
        
        print(f"Successfully converted '{csv_file}' to SQLite database '{db_name}'")
        print(f"Table name: '{table_name}'")
        
        # Display some basic info about the created table
        conn = sqlite3.connect(db_name)
        cursor = conn.cursor()
        cursor.execute(f"SELECT COUNT(*) FROM '{table_name}'")
        row_count = cursor.fetchone()[0]
        print(f"Number of rows inserted: {row_count}")
        
        # Show column names
        cursor.execute(f"PRAGMA table_info('{table_name}')")
        columns = cursor.fetchall()
        print(f"Columns: {[col[1] for col in columns]}")
        
        conn.close()
        
    except sqlite3.Error as e:
        print(f"SQLite error: {e}")
        sys.exit(1)
    except csv.Error as e:
        print(f"CSV error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
