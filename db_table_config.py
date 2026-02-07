import sqlite3

def init_database(self):
    conn = sqlite3.connect(self.db_path)
    cursor = conn.cursor()

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS comparisons (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ontology_name TEXT NOT NULL,
        concept1 TEXT NOT NULL,
        concept2 TEXT NOT NULL,
        lcs TEXT NOT NULL,
        graph_distance REAL,
        wu_palmer REAL,
        lee REAL,
        resnik REAL,
        lin REAL,
        jiang_conrath REAL,
        schlicker REAL,
        meng REAL,
        edge_based REAL,
        batet REAL,
        average_similarity REAL,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        notes TEXT
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS metrics (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        comparison_id INTEGER,
        metric_name TEXT NOT NULL,
        metric_value REAL NOT NULL,
        metric_type TEXT NOT NULL,
        interpretation TEXT,
        FOREIGN KEY (comparison_id) REFERENCES comparisons (id)
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS ontologies (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        file_path TEXT NOT NULL,
        concept_count INTEGER,
        loaded_date DATETIME DEFAULT CURRENT_TIMESTAMP,
        last_used DATETIME
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS favorites (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        comparison_id INTEGER,
        tag TEXT,
        added_date DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (comparison_id) REFERENCES comparisons (id)
    )
    ''')

    cursor.execute('CREATE INDEX IF NOT EXISTS idx_comparisons_concepts ON comparisons(concept1, concept2)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_comparisons_timestamp ON comparisons(timestamp)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_metrics_comparison ON metrics(comparison_id)')

    conn.commit()
    conn.close()