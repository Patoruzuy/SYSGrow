import sqlite3
import click
from flask import current_app, g

class Database:
    def __init__(self, db_path):
        self.db_path = db_path

    def connect(self):
        return sqlite3.connect(self.db_path)

    def execute_query(self, query, params=()):
        try:
            with self.connect() as conn:
                cursor = conn.cursor()
                cursor.execute(query, params)
                conn.commit()
        except sqlite3.Error as e:
            print(f"An error occurred: {e}")

    def fetch_one(self, query, params=()):
        try:
            with self.connect() as conn:
                cursor = conn.cursor()
                cursor.execute(query, params)
                return cursor.fetchone()
        except sqlite3.Error as e:
            print(f"An error occurred: {e}")
            return None

    def fetch_all(self, query, params=()):
        try:
            with self.connect() as conn:
                cursor = conn.cursor()
                cursor.execute(query, params)
                return cursor.fetchall()
        except sqlite3.Error as e:
            print(f"An error occurred: {e}")
            return []

    def save_data(self, table, criteria=None):
        query = f"SELECT * FROM {table}"
        if criteria:
            placeholders = ' AND '.join([f"{key}=?" for key in criteria.keys()])
            query += f" WHERE {placeholders}"
            return self.fetch_all(query, tuple(criteria.values()))
        return self.fetch_all(query)
    
    def init_db(self, schema_path):
        with self.connect() as conn:
            with current_app.open_resource(schema_path) as f:
                conn.executescript(f.read().decode('utf8'))


def get_db():
    if 'db' not in g:
        g.db = Database(current_app.config['DATABASE'])
    return g.db

def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        db.connect().close()

def init_db():
    db = get_db()
    db.init_db('schema.sql')


@click.command('init-db')
def init_db_command():
    """Clear the existing data and create new tables."""
    init_db()
    click.echo('Initialized the database.')

def init_app(app):
    app.teardown_appcontext(close_db)
    app.cli.add_command(init_db_command)