import sqlite3
import click
from flask import current_app, g

class Database:
    def __init__(self,db_path):
        self.db_path = db_path

    def connect(self):
        return sqlite3.connect(self.db_path)

    def execture_query(self, query, params=()):
        with self.connect() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            conn.commit()

    def fetch_one(self, query, params=()):
        with self.connect() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return cursor.fetchone()
        
    def fetch_all(self, query, params=()):
        with self.connect() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return cursor.fetchall()
        
    def save_data(self, table, criteria=None):
        query = f"SELECT * FROM {table}"
        if criteria:
            placeholders = ' AND'.join([f"{key}=?" for key in criteria.keys()])
            query += f" WHERE {placeholders}"
            return self.fech_all(query, tuple(criteria.value()))
        return self.fech_all(query)
    


def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(
            current_app.config['DATABASE'],
            detect_types=sqlite3.PARSE_DECLTYPES
        )
        g.db.row_factory = sqlite3.Row

    return g.db


def close_db(e=None):
    db = g.pop('db', None)

    if db is not None:
        db.close()