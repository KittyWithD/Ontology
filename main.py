from owlready2 import *
from typing import List, Dict, Set
import math
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
import threading
import sqlite3
import datetime
import json
from dataclasses import dataclass
from enum import Enum

class MetricType(Enum):
    DISTANCE = "distance"
    SIMILARITY = "similarity"
    SUMMARY = "summary"

@dataclass
class ComparisonResult:
    concept1: str
    concept2: str
    lcs: str
    graph_distance: float
    wu_palmer: float
    lee: float
    resnik: float
    lin: float
    jiang_conrath: float
    schlicker: float
    meng: float
    edge_based: float
    batet: float
    average_similarity: float
    ontology_name: str
    timestamp: str

class DatabaseManager:
    def __init__(self, db_path="ontology_comparisons.db"):
        self.db_path = db_path
        self.init_database()

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

    def save_comparison(self, result: ComparisonResult, notes: str = ""):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
        INSERT INTO comparisons 
        (ontology_name, concept1, concept2, lcs, graph_distance, wu_palmer, lee, resnik, 
         lin, jiang_conrath, schlicker, meng, edge_based, batet, average_similarity, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            result.ontology_name, result.concept1, result.concept2, result.lcs,
            result.graph_distance, result.wu_palmer, result.lee, result.resnik,
            result.lin, result.jiang_conrath, result.schlicker, result.meng,
            result.edge_based, result.batet, result.average_similarity, notes
        ))

        comparison_id = cursor.lastrowid

        metrics = [
            ("graph_distance", result.graph_distance, MetricType.DISTANCE.value),
            ("wu_palmer", result.wu_palmer, MetricType.SIMILARITY.value),
            ("lee", result.lee, MetricType.SIMILARITY.value),
            ("resnik", result.resnik, MetricType.SIMILARITY.value),
            ("lin", result.lin, MetricType.SIMILARITY.value),
            ("jiang_conrath", result.jiang_conrath, MetricType.DISTANCE.value),
            ("schlicker", result.schlicker, MetricType.SIMILARITY.value),
            ("meng", result.meng, MetricType.SIMILARITY.value),
            ("edge_based", result.edge_based, MetricType.SIMILARITY.value),
            ("batet", result.batet, MetricType.SIMILARITY.value),
            ("average_similarity", result.average_similarity, MetricType.SUMMARY.value),
        ]

        for metric_name, metric_value, metric_type in metrics:
            cursor.execute('''
            INSERT INTO metrics (comparison_id, metric_name, metric_value, metric_type)
            VALUES (?, ?, ?, ?)
            ''', (comparison_id, metric_name, metric_value, metric_type))

        conn.commit()
        conn.close()

        return comparison_id

    def save_ontology_info(self, name: str, file_path: str, concept_count: int):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('SELECT id FROM ontologies WHERE file_path = ?', (file_path,))
        existing = cursor.fetchone()

        if existing:
            cursor.execute('''
            UPDATE ontologies 
            SET last_used = CURRENT_TIMESTAMP, concept_count = ?
            WHERE id = ?
            ''', (concept_count, existing[0]))
        else:
            cursor.execute('''
            INSERT INTO ontologies (name, file_path, concept_count, last_used)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ''', (name, file_path, concept_count))

        conn.commit()
        conn.close()

    def get_comparison_history(self, limit: int = 50):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute('''
        SELECT * FROM comparisons 
        ORDER BY timestamp DESC 
        LIMIT ?
        ''', (limit,))

        results = cursor.fetchall()
        conn.close()

        return [dict(row) for row in results]

    def get_comparison_by_id(self, comparison_id: int):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM comparisons WHERE id = ?', (comparison_id,))
        result = cursor.fetchone()

        if result:
            cursor.execute('SELECT * FROM metrics WHERE comparison_id = ?', (comparison_id,))
            metrics = cursor.fetchall()
            result = dict(result)
            result['metrics'] = [dict(m) for m in metrics]

        conn.close()
        return dict(result) if result else None

    def search_comparisons(self, concept_name: str = None, ontology_name: str = None,
                           date_from: str = None, date_to: str = None):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        query = '''
        SELECT * FROM comparisons 
        WHERE 1=1
        '''
        params = []

        if concept_name:
            query += ' AND (concept1 LIKE ? OR concept2 LIKE ?)'
            params.extend([f'%{concept_name}%', f'%{concept_name}%'])

        if ontology_name:
            query += ' AND ontology_name LIKE ?'
            params.append(f'%{ontology_name}%')

        if date_from:
            query += ' AND timestamp >= ?'
            params.append(date_from)

        if date_to:
            query += ' AND timestamp <= ?'
            params.append(date_to)

        query += ' ORDER BY timestamp DESC'

        cursor.execute(query, params)
        results = cursor.fetchall()
        conn.close()

        return [dict(row) for row in results]

    def add_to_favorites(self, comparison_id: int, tag: str = ""):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
        INSERT INTO favorites (comparison_id, tag)
        VALUES (?, ?)
        ''', (comparison_id, tag))

        conn.commit()
        conn.close()

    def get_favorites(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute('''
        SELECT c.*, f.tag, f.added_date as favorite_date 
        FROM comparisons c
        JOIN favorites f ON c.id = f.comparison_id
        ORDER BY f.added_date DESC
        ''')

        results = cursor.fetchall()
        conn.close()

        return [dict(row) for row in results]

    def get_statistics(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        stats = {}

        cursor.execute('SELECT COUNT(*) FROM comparisons')
        stats['total_comparisons'] = cursor.fetchone()[0]

        cursor.execute('''
        SELECT COUNT(DISTINCT concept) FROM (
            SELECT concept1 as concept FROM comparisons
            UNION ALL
            SELECT concept2 as concept FROM comparisons
        )
        ''')
        stats['unique_concepts'] = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(*) FROM ontologies')
        stats['total_ontologies'] = cursor.fetchone()[0]

        cursor.execute('SELECT MAX(timestamp) FROM comparisons')
        stats['last_comparison'] = cursor.fetchone()[0]

        cursor.execute('''
        SELECT concept1, concept2, COUNT(*) as count
        FROM comparisons
        GROUP BY concept1, concept2
        ORDER BY count DESC
        LIMIT 1
        ''')
        result = cursor.fetchone()
        if result:
            stats['most_compared'] = {
                'concept1': result[0],
                'concept2': result[1],
                'count': result[2]
            }

        conn.close()
        return stats

    def export_to_json(self, file_path: str):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM comparisons ORDER BY timestamp DESC')
        comparisons = cursor.fetchall()

        data = []
        for comp in comparisons:
            comp_dict = dict(comp)
            cursor.execute('SELECT * FROM metrics WHERE comparison_id = ?', (comp_dict['id'],))
            metrics = cursor.fetchall()
            comp_dict['metrics'] = [dict(m) for m in metrics]
            data.append(comp_dict)

        conn.close()

        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)

    def backup_database(self, backup_path: str):
        import shutil
        shutil.copy2(self.db_path, backup_path)


class OntologySimilarityAnalyzer:

    def __init__(self, ontology_path: str):
        self.ontology = get_ontology(ontology_path).load()
        self.ontology_path = ontology_path

        self.classes = list(self.ontology.classes())
        self.class_names = {cls.name.lower(): cls for cls in self.classes}

        self.parents_cache = {}
        self.depth_cache = {}
        self.children_cache = {}
        self._build_caches()

        self.descendants_cache = {}

    def _build_caches(self):
        for cls in self.classes:
            ancestors = set(cls.ancestors())
            ancestors.discard(cls)
            self.parents_cache[cls] = ancestors

            children = set(cls.subclasses())
            self.children_cache[cls] = children

            self.depth_cache[cls] = self._compute_depth(cls)

    def _compute_depth(self, cls) -> int:
        if cls == owl.Thing:
            return 0

        parents = cls.is_a
        direct_parents = [p for p in parents if isinstance(p, owlready2.ThingClass)]

        if not direct_parents:
            return 1

        min_depth = float('inf')
        for parent in direct_parents:
            if parent not in self.depth_cache:
                self.depth_cache[parent] = self._compute_depth(parent)
            min_depth = min(min_depth, self.depth_cache[parent])

        return min_depth + 1

    def get_concepts_list(self) -> List[str]:
        return [cls.name for cls in self.classes]

    def find_concept(self, concept_name: str):
        for cls in self.classes:
            if cls.name.lower() == concept_name.lower():
                return cls

        matches = []
        for cls in self.classes:
            if concept_name.lower() in cls.name.lower():
                matches.append(cls)

        if len(matches) == 1:
            return matches[0]
        elif len(matches) > 1:
            return matches[0]

        return None

    def find_least_common_subsumer(self, cls1, cls2):
        if cls1 == cls2:
            return cls1

        ancestors1 = self.parents_cache[cls1].copy()
        ancestors1.add(cls1)
        ancestors2 = self.parents_cache[cls2].copy()
        ancestors2.add(cls2)

        common_ancestors = ancestors1.intersection(ancestors2)

        if not common_ancestors:
            return owl.Thing

        lcs = max(common_ancestors, key=lambda x: self.depth_cache.get(x, 0))
        return lcs

    def _get_descendants(self, cls) -> Set:
        if cls in self.descendants_cache:
            return self.descendants_cache[cls]

        descendants = set()
        queue = [cls]

        while queue:
            current = queue.pop(0)
            if current not in descendants:
                descendants.add(current)
                for child in self.children_cache.get(current, []):
                    if child not in descendants:
                        queue.append(child)

        self.descendants_cache[cls] = descendants
        return descendants

    def graph_distance(self, cls1, cls2) -> float:
        if cls1 == cls2:
            return 0.0

        lcs = self.find_least_common_subsumer(cls1, cls2)
        dist1 = self._distance_to_ancestor(cls1, lcs)
        dist2 = self._distance_to_ancestor(cls2, lcs)

        return dist1 + dist2

    def _distance_to_ancestor(self, cls, ancestor) -> int:
        if cls == ancestor:
            return 0

        visited = set()
        queue = [(cls, 0)]

        while queue:
            current, distance = queue.pop(0)

            if current == ancestor:
                return distance

            if current in visited:
                continue
            visited.add(current)
            parents = [p for p in current.is_a if isinstance(p, owlready2.ThingClass)]
            for parent in parents:
                queue.append((parent, distance + 1))

            children = current.subclasses()
            for child in children:
                queue.append((child, distance + 1))

        return float('inf')

    def wu_palmer_similarity(self, cls1, cls2) -> float:
        if cls1 == cls2:
            return 1.0

        lcs = self.find_least_common_subsumer(cls1, cls2)

        depth_lcs = self.depth_cache.get(lcs, 0)
        depth1 = self.depth_cache.get(cls1, 0)
        depth2 = self.depth_cache.get(cls2, 0)

        if depth_lcs == 0:
            return 0.0

        similarity = (2.0 * depth_lcs) / (depth1 + depth2)
        return min(1.0, max(0.0, similarity))

    def lee_similarity(self, cls1, cls2) -> float:
        if cls1 == cls2:
            return 1.0

        lcs = self.find_least_common_subsumer(cls1, cls2)
        depth_lcs = self.depth_cache.get(lcs, 0)

        max_depth = max(self.depth_cache.values())

        if max_depth == 0:
            return 0.0

        return depth_lcs / max_depth

    def resnik_similarity(self, cls1, cls2, ic_values: Dict = None) -> float:
        if cls1 == cls2:
            if ic_values and cls1 in ic_values:
                return ic_values[cls1]
            return 1.0

        lcs = self.find_least_common_subsumer(cls1, cls2)

        if ic_values and lcs in ic_values:
            return ic_values[lcs]

        depth_lcs = self.depth_cache.get(lcs, 0)
        max_depth = max(self.depth_cache.values())

        if max_depth == 0:
            return 0.0

        return depth_lcs / max_depth

    def lin_similarity(self, cls1, cls2, ic_values: Dict = None) -> float:
        if cls1 == cls2:
            return 1.0

        lcs = self.find_least_common_subsumer(cls1, cls2)

        if ic_values:
            ic1 = ic_values.get(cls1, 0)
            ic2 = ic_values.get(cls2, 0)
            ic_lcs = ic_values.get(lcs, 0)

            if ic1 + ic2 == 0:
                return 0.0

            return (2 * ic_lcs) / (ic1 + ic2)
        else:
            depth_lcs = self.depth_cache.get(lcs, 0)
            depth1 = self.depth_cache.get(cls1, 0)
            depth2 = self.depth_cache.get(cls2, 0)

            if depth1 + depth2 == 0:
                return 0.0

            return (2 * depth_lcs) / (depth1 + depth2)

    def jiang_conrath_distance(self, cls1, cls2, ic_values: Dict = None) -> float:
        if cls1 == cls2:
            return 0.0

        lcs = self.find_least_common_subsumer(cls1, cls2)

        if ic_values:
            ic1 = ic_values.get(cls1, 0)
            ic2 = ic_values.get(cls2, 0)
            ic_lcs = ic_values.get(lcs, 0)
        else:
            max_depth = max(self.depth_cache.values())
            ic1 = self.depth_cache.get(cls1, 0) / max_depth if max_depth > 0 else 0
            ic2 = self.depth_cache.get(cls2, 0) / max_depth if max_depth > 0 else 0
            ic_lcs = self.depth_cache.get(lcs, 0) / max_depth if max_depth > 0 else 0

        distance = ic1 + ic2 - (2 * ic_lcs)
        return max(0.0, distance)

    def schlicker_similarity(self, cls1, cls2, ic_values: Dict = None) -> float:
        if cls1 == cls2:
            return 1.0

        lcs = self.find_least_common_subsumer(cls1, cls2)

        if ic_values:
            ic_lcs = ic_values.get(lcs, 0)
            ic1 = ic_values.get(cls1, 0)
            ic2 = ic_values.get(cls2, 0)
        else:
            max_depth = max(self.depth_cache.values())
            ic_lcs = self.depth_cache.get(lcs, 0) / max_depth if max_depth > 0 else 0
            ic1 = self.depth_cache.get(cls1, 0) / max_depth if max_depth > 0 else 0
            ic2 = self.depth_cache.get(cls2, 0) / max_depth if max_depth > 0 else 0

        if ic1 == 0 or ic2 == 0:
            return 0.0

        similarity = (2 * ic_lcs) / (ic1 + ic2) * (1 - math.exp(-ic_lcs))
        return min(1.0, max(0.0, similarity))

    def meng_similarity(self, cls1, cls2) -> float:
        if cls1 == cls2:
            return 1.0

        ancestors1 = self.parents_cache[cls1].copy()
        ancestors1.add(cls1)
        ancestors2 = self.parents_cache[cls2].copy()
        ancestors2.add(cls2)
        common_ancestors = ancestors1.intersection(ancestors2)

        descendants1 = self._get_descendants(cls1)
        descendants2 = self._get_descendants(cls2)
        common_descendants = descendants1.intersection(descendants2)

        all_nodes = set(self.classes)

        if len(all_nodes) == 0:
            return 0.0

        ancestor_similarity = len(common_ancestors) / len(all_nodes)
        descendant_similarity = len(common_descendants) / len(all_nodes)

        similarity = 0.6 * ancestor_similarity + 0.4 * descendant_similarity

        return min(1.0, max(0.0, similarity))

    def edge_based_similarity(self, cls1, cls2) -> float:
        if cls1 == cls2:
            return 1.0

        distance = self.graph_distance(cls1, cls2)

        if distance == float('inf'):
            return 0.0

        max_distance = 0
        for c1 in self.classes:
            for c2 in self.classes:
                if c1 != c2:
                    d = self.graph_distance(c1, c2)
                    if d != float('inf'):
                        max_distance = max(max_distance, d)

        if max_distance == 0:
            return 0.0

        similarity = 1.0 - (distance / max_distance)

        return max(0.0, min(1.0, similarity))

    def batet_similarity(self, cls1, cls2) -> float:
        if cls1 == cls2:
            return 1.0

        ancestors1 = self.parents_cache[cls1].copy()
        ancestors1.add(cls1)
        ancestors2 = self.parents_cache[cls2].copy()
        ancestors2.add(cls2)

        union = ancestors1.union(ancestors2)
        intersection = ancestors1.intersection(ancestors2)

        if len(union) == 0:
            return 0.0

        similarity = 1 - (math.log2(len(intersection) + 1) /
                          math.log2(len(union) + 1))

        return max(0.0, min(1.0, similarity))

    def compute_all_metrics(self, concept1_name: str, concept2_name: str,
                            ic_values: Dict = None) -> ComparisonResult:
        concept1 = self.find_concept(concept1_name)
        concept2 = self.find_concept(concept2_name)

        if not concept1:
            raise ValueError(f"Концепт '{concept1_name}' не найден в онтологии")
        if not concept2:
            raise ValueError(f"Концепт '{concept2_name}' не найден в онтологии")

        graph_distance = self.graph_distance(concept1, concept2)
        wu_palmer = self.wu_palmer_similarity(concept1, concept2)
        lee = self.lee_similarity(concept1, concept2)
        resnik = self.resnik_similarity(concept1, concept2, ic_values)
        lin = self.lin_similarity(concept1, concept2, ic_values)
        jiang_conrath = self.jiang_conrath_distance(concept1, concept2, ic_values)
        schlicker = self.schlicker_similarity(concept1, concept2, ic_values)
        meng = self.meng_similarity(concept1, concept2)
        edge_based = self.edge_based_similarity(concept1, concept2)
        batet = self.batet_similarity(concept1, concept2)

        similarity_metrics = [wu_palmer, lee, resnik, lin, schlicker, meng, edge_based, batet]
        average_similarity = sum(similarity_metrics) / len(similarity_metrics)

        lcs = self.find_least_common_subsumer(concept1, concept2)

        result = ComparisonResult(
            concept1=concept1.name,
            concept2=concept2.name,
            lcs=lcs.name,
            graph_distance=graph_distance,
            wu_palmer=wu_palmer,
            lee=lee,
            resnik=resnik,
            lin=lin,
            jiang_conrath=jiang_conrath,
            schlicker=schlicker,
            meng=meng,
            edge_based=edge_based,
            batet=batet,
            average_similarity=average_similarity,
            ontology_name=self.ontology.name,
            timestamp=datetime.datetime.now().isoformat()
        )

        return result

class OntologyGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Анализатор семантической близости концептов с БД")
        self.root.geometry("1400x900")

        self.analyzer = None
        self.ic_values = None
        self.db_manager = DatabaseManager()
        self.current_comparison_id = None

        self.setup_ui()

    def setup_ui(self):
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(3, weight=1)

        title_label = ttk.Label(
            main_frame,
            text="Анализатор семантической близости концептов с SQLite БД",
            font=("Arial", 16, "bold")
        )
        title_label.grid(row=0, column=0, columnspan=4, pady=(0, 10))

        ttk.Label(main_frame, text="Файл онтологии (.owl):", font=("Arial", 10, "bold")).grid(
            row=1, column=0, sticky=tk.W, pady=(0, 5)
        )

        self.file_path_var = tk.StringVar()
        file_entry = ttk.Entry(main_frame, textvariable=self.file_path_var, width=50)
        file_entry.grid(row=1, column=1, sticky=(tk.W, tk.E), padx=(5, 5))

        browse_btn = ttk.Button(main_frame, text="Обзор...", command=self.browse_file)
        browse_btn.grid(row=1, column=2, sticky=tk.W)

        load_btn = ttk.Button(main_frame, text="Загрузить онтологию", command=self.load_ontology)
        load_btn.grid(row=1, column=3, sticky=tk.W, padx=(5, 0))

        concepts_frame = ttk.LabelFrame(main_frame, text="Выбор концептов", padding="10")
        concepts_frame.grid(row=2, column=0, columnspan=4, sticky=(tk.W, tk.E), pady=(10, 10))
        concepts_frame.columnconfigure(1, weight=1)
        concepts_frame.columnconfigure(3, weight=1)

        ttk.Label(concepts_frame, text="Концепт 1:").grid(row=0, column=0, sticky=tk.W, padx=(0, 5))
        self.concept1_var = tk.StringVar()
        self.concept1_combo = ttk.Combobox(concepts_frame, textvariable=self.concept1_var)
        self.concept1_combo.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(0, 20))

        ttk.Label(concepts_frame, text="Концепт 2:").grid(row=0, column=2, sticky=tk.W, padx=(0, 5))
        self.concept2_var = tk.StringVar()
        self.concept2_combo = ttk.Combobox(concepts_frame, textvariable=self.concept2_var)
        self.concept2_combo.grid(row=0, column=3, sticky=(tk.W, tk.E))

        buttons_frame = ttk.Frame(concepts_frame)
        buttons_frame.grid(row=1, column=0, columnspan=4, pady=(10, 0))

        compare_btn = ttk.Button(buttons_frame, text="Сравнить концепты", command=self.compare_concepts)
        compare_btn.pack(side=tk.LEFT, padx=(0, 10))

        save_btn = ttk.Button(buttons_frame, text="Сохранить в БД", command=self.save_to_db)
        save_btn.pack(side=tk.LEFT, padx=(0, 10))

        clear_btn = ttk.Button(buttons_frame, text="Очистить", command=self.clear_results)
        clear_btn.pack(side=tk.LEFT)

        notes_frame = ttk.Frame(concepts_frame)
        notes_frame.grid(row=2, column=0, columnspan=4, pady=(10, 0), sticky=(tk.W, tk.E))

        ttk.Label(notes_frame, text="Примечания:").pack(side=tk.LEFT, padx=(0, 5))
        self.notes_var = tk.StringVar()
        notes_entry = ttk.Entry(notes_frame, textvariable=self.notes_var, width=70)
        notes_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.notebook = ttk.Notebook(main_frame)
        self.notebook.grid(row=3, column=0, columnspan=4, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))

        metrics_frame = ttk.Frame(self.notebook)
        self.notebook.add(metrics_frame, text="Метрики сравнения")
        self.setup_metrics_tab(metrics_frame)

        history_frame = ttk.Frame(self.notebook)
        self.notebook.add(history_frame, text="История сравнений")
        self.setup_history_tab(history_frame)

        search_frame = ttk.Frame(self.notebook)
        self.notebook.add(search_frame, text="Поиск в БД")
        self.setup_search_tab(search_frame)

        favorites_frame = ttk.Frame(self.notebook)
        self.notebook.add(favorites_frame, text="Избранное")
        self.setup_favorites_tab(favorites_frame)

        stats_frame = ttk.Frame(self.notebook)
        self.notebook.add(stats_frame, text="Статистика")
        self.setup_stats_tab(stats_frame)

        list_frame = ttk.Frame(self.notebook)
        self.notebook.add(list_frame, text="Концепты онтологии")
        self.setup_concepts_tab(list_frame)

        self.status_var = tk.StringVar(value="Готов к работе. База данных: ontology_comparisons.db")
        status_bar = ttk.Label(main_frame, textvariable=self.status_var, relief=tk.SUNKEN)
        status_bar.grid(row=4, column=0, columnspan=4, sticky=(tk.W, tk.E), pady=(5, 0))

    def setup_metrics_tab(self, parent):
        columns = ('metric', 'value', 'interpretation')
        self.tree_metrics = ttk.Treeview(parent, columns=columns, show='headings', height=20)

        self.tree_metrics.heading('metric', text='Метрика')
        self.tree_metrics.heading('value', text='Значение')
        self.tree_metrics.heading('interpretation', text='Интерпретация')

        self.tree_metrics.column('metric', width=250)
        self.tree_metrics.column('value', width=150)
        self.tree_metrics.column('interpretation', width=400)

        scrollbar = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=self.tree_metrics.yview)
        self.tree_metrics.configure(yscrollcommand=scrollbar.set)

        self.tree_metrics.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))

        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)

        btn_frame = ttk.Frame(parent)
        btn_frame.grid(row=1, column=0, columnspan=2, pady=(5, 0))

        ttk.Button(btn_frame, text="Экспорт в JSON", command=self.export_to_json).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Добавить в избранное", command=self.add_to_favorites).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Создать резервную копию БД", command=self.backup_database).pack(side=tk.LEFT,
                                                                                                    padx=5)

    def setup_history_tab(self, parent):
        control_frame = ttk.Frame(parent)
        control_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 5))

        ttk.Label(control_frame, text="Лимит:").pack(side=tk.LEFT, padx=(0, 5))
        self.history_limit_var = tk.StringVar(value="50")
        history_limit = ttk.Entry(control_frame, textvariable=self.history_limit_var, width=10)
        history_limit.pack(side=tk.LEFT, padx=(0, 10))

        ttk.Button(control_frame, text="Обновить", command=self.load_history).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(control_frame, text="Очистить таблицу", command=self.clear_history_table).pack(side=tk.LEFT)

        columns = ('id', 'timestamp', 'ontology', 'concept1', 'concept2', 'avg_similarity', 'lcs')
        self.tree_history = ttk.Treeview(parent, columns=columns, show='headings', height=15)

        for col in columns:
            if col == 'id':
                self.tree_history.heading(col, text='ID')
                self.tree_history.column(col, width=50)
            elif col == 'timestamp':
                self.tree_history.heading(col, text='Дата/время')
                self.tree_history.column(col, width=150)
            elif col == 'ontology':
                self.tree_history.heading(col, text='Онтология')
                self.tree_history.column(col, width=150)
            elif col == 'concept1':
                self.tree_history.heading(col, text='Концепт 1')
                self.tree_history.column(col, width=120)
            elif col == 'concept2':
                self.tree_history.heading(col, text='Концепт 2')
                self.tree_history.column(col, width=120)
            elif col == 'avg_similarity':
                self.tree_history.heading(col, text='Сред. сходство')
                self.tree_history.column(col, width=100)
            elif col == 'lcs':
                self.tree_history.heading(col, text='LCS')
                self.tree_history.column(col, width=120)

        scrollbar = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=self.tree_history.yview)
        self.tree_history.configure(yscrollcommand=scrollbar.set)

        self.tree_history.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        scrollbar.grid(row=1, column=1, sticky=(tk.N, tk.S))

        self.tree_history.bind('<Double-Button-1>', self.view_history_item)

        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(1, weight=1)

    def setup_search_tab(self, parent):
        search_frame = ttk.LabelFrame(parent, text="Параметры поиска", padding="10")
        search_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))

        ttk.Label(search_frame, text="Концепт:").grid(row=0, column=0, sticky=tk.W)
        self.search_concept_var = tk.StringVar()
        ttk.Entry(search_frame, textvariable=self.search_concept_var, width=30).grid(
            row=0, column=1, sticky=tk.W, padx=(5, 20)
        )

        ttk.Label(search_frame, text="Онтология:").grid(row=0, column=2, sticky=tk.W)
        self.search_ontology_var = tk.StringVar()
        ttk.Entry(search_frame, textvariable=self.search_ontology_var, width=30).grid(
            row=0, column=3, sticky=tk.W, padx=(5, 0)
        )

        ttk.Label(search_frame, text="С даты (YYYY-MM-DD):").grid(row=1, column=0, sticky=tk.W, pady=(10, 0))
        self.search_date_from_var = tk.StringVar()
        ttk.Entry(search_frame, textvariable=self.search_date_from_var, width=15).grid(
            row=1, column=1, sticky=tk.W, padx=(5, 20), pady=(10, 0)
        )

        ttk.Label(search_frame, text="По дату (YYYY-MM-DD):").grid(row=1, column=2, sticky=tk.W, pady=(10, 0))
        self.search_date_to_var = tk.StringVar()
        ttk.Entry(search_frame, textvariable=self.search_date_to_var, width=15).grid(
            row=1, column=3, sticky=tk.W, padx=(5, 0), pady=(10, 0)
        )

        btn_frame = ttk.Frame(search_frame)
        btn_frame.grid(row=2, column=0, columnspan=4, pady=(10, 0))

        ttk.Button(btn_frame, text="Искать", command=self.search_comparisons).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Очистить", command=self.clear_search).pack(side=tk.LEFT, padx=5)

        columns = ('id', 'timestamp', 'ontology', 'concept1', 'concept2', 'avg_similarity')
        self.tree_search = ttk.Treeview(parent, columns=columns, show='headings', height=12)

        for col in columns:
            if col == 'id':
                self.tree_search.heading(col, text='ID')
                self.tree_search.column(col, width=50)
            elif col == 'timestamp':
                self.tree_search.heading(col, text='Дата/время')
                self.tree_search.column(col, width=150)
            elif col == 'ontology':
                self.tree_search.heading(col, text='Онтология')
                self.tree_search.column(col, width=150)
            elif col == 'concept1':
                self.tree_search.heading(col, text='Концепт 1')
                self.tree_search.column(col, width=120)
            elif col == 'concept2':
                self.tree_search.heading(col, text='Концепт 2')
                self.tree_search.column(col, width=120)
            elif col == 'avg_similarity':
                self.tree_search.heading(col, text='Сред. сходство')
                self.tree_search.column(col, width=100)

        scrollbar = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=self.tree_search.yview)
        self.tree_search.configure(yscrollcommand=scrollbar.set)

        self.tree_search.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        scrollbar.grid(row=1, column=1, sticky=(tk.N, tk.S))

        self.tree_search.bind('<Double-Button-1>', self.view_search_item)

        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(1, weight=1)

    def setup_favorites_tab(self, parent):
        columns = ('id', 'concept1', 'concept2', 'avg_similarity', 'tag', 'added_date')
        self.tree_favorites = ttk.Treeview(parent, columns=columns, show='headings', height=15)

        for col in columns:
            if col == 'id':
                self.tree_favorites.heading(col, text='ID')
                self.tree_favorites.column(col, width=50)
            elif col == 'concept1':
                self.tree_favorites.heading(col, text='Концепт 1')
                self.tree_favorites.column(col, width=120)
            elif col == 'concept2':
                self.tree_favorites.heading(col, text='Концепт 2')
                self.tree_favorites.column(col, width=120)
            elif col == 'avg_similarity':
                self.tree_favorites.heading(col, text='Сред. сходство')
                self.tree_favorites.column(col, width=100)
            elif col == 'tag':
                self.tree_favorites.heading(col, text='Тег')
                self.tree_favorites.column(col, width=100)
            elif col == 'added_date':
                self.tree_favorites.heading(col, text='Дата добавления')
                self.tree_favorites.column(col, width=150)

        scrollbar = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=self.tree_favorites.yview)
        self.tree_favorites.configure(yscrollcommand=scrollbar.set)

        self.tree_favorites.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))

        btn_frame = ttk.Frame(parent)
        btn_frame.grid(row=1, column=0, columnspan=2, pady=(10, 0))

        ttk.Button(btn_frame, text="Обновить", command=self.load_favorites).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Удалить из избранного", command=self.remove_from_favorites).pack(side=tk.LEFT,
                                                                                                     padx=5)

        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)

    def setup_stats_tab(self, parent):
        self.stats_text = scrolledtext.ScrolledText(parent, wrap=tk.WORD, width=80, height=20)
        self.stats_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        btn_frame = ttk.Frame(parent)
        btn_frame.grid(row=1, column=0, pady=(10, 0))

        ttk.Button(btn_frame, text="Обновить статистику", command=self.load_statistics).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Экспорт статистики", command=self.export_stats).pack(side=tk.LEFT, padx=5)

        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)

    def setup_concepts_tab(self, parent):
        self.concepts_listbox = tk.Listbox(parent, height=20)
        scrollbar = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=self.concepts_listbox.yview)
        self.concepts_listbox.configure(yscrollcommand=scrollbar.set)

        self.concepts_listbox.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))

        btn_frame = ttk.Frame(parent)
        btn_frame.grid(row=1, column=0, columnspan=2, pady=(10, 0))

        ttk.Button(btn_frame, text="Копировать выбранное", command=self.copy_selected_concept).pack(side=tk.LEFT,
                                                                                                    padx=5)
        ttk.Button(btn_frame, text="Обновить список", command=self.update_concepts_list).pack(side=tk.LEFT, padx=5)

        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)

    def browse_file(self):
        filename = filedialog.askopenfilename(
            title="Выберите файл онтологии",
            filetypes=[("OWL files", "*.owl"), ("All files", "*.*")]
        )
        if filename:
            self.file_path_var.set(filename)

    def load_ontology(self):
        filepath = self.file_path_var.get()
        if not filepath:
            messagebox.showerror("Ошибка", "Укажите путь к файлу онтологии")
            return

        try:
            self.status_var.set("Загрузка онтологии...")
            self.root.update()

            def load():
                try:
                    self.analyzer = OntologySimilarityAnalyzer(filepath)
                    concepts = self.analyzer.get_concepts_list()

                    self.db_manager.save_ontology_info(
                        self.analyzer.ontology.name,
                        filepath,
                        len(concepts)
                    )

                    self.root.after(0, self.update_concepts_list, concepts)
                    self.root.after(0, lambda: self.status_var.set(
                        f"Онтология '{self.analyzer.ontology.name}' загружена. Концептов: {len(concepts)}"
                    ))

                except Exception as e:
                    self.root.after(0, lambda: messagebox.showerror(
                        "Ошибка загрузки", f"Не удалось загрузить онтологию: {str(e)}"
                    ))
                    self.root.after(0, lambda: self.status_var.set("Ошибка загрузки"))

            thread = threading.Thread(target=load)
            thread.daemon = True
            thread.start()

        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось загрузить онтологию: {str(e)}")
            self.status_var.set("Ошибка загрузки")

    def update_concepts_list(self, concepts):
        self.concept1_combo['values'] = concepts
        self.concept2_combo['values'] = concepts

        self.concepts_listbox.delete(0, tk.END)
        for concept in sorted(concepts):
            self.concepts_listbox.insert(tk.END, concept)

    def compare_concepts(self):
        if not self.analyzer:
            messagebox.showerror("Ошибка", "Сначала загрузите онтологию")
            return

        concept1 = self.concept1_var.get().strip()
        concept2 = self.concept2_var.get().strip()

        if not concept1 or not concept2:
            messagebox.showerror("Ошибка", "Выберите оба концепта для сравнения")
            return

        try:
            self.status_var.set("Вычисление метрик...")
            self.root.update()

            def compute():
                try:
                    self.current_result = self.analyzer.compute_all_metrics(concept1, concept2, self.ic_values)

                    self.root.after(0, self.display_results, self.current_result)
                    self.root.after(0, lambda: self.status_var.set(
                        f"Сравнение завершено: {concept1} vs {concept2}"
                    ))

                except ValueError as e:
                    self.root.after(0, lambda: messagebox.showerror("Ошибка", str(e)))
                    self.root.after(0, lambda: self.status_var.set("Ошибка вычисления"))
                except Exception as e:
                    self.root.after(0, lambda: messagebox.showerror(
                        "Ошибка", f"Ошибка при вычислении: {str(e)}"
                    ))
                    self.root.after(0, lambda: self.status_var.set("Ошибка вычисления"))

            thread = threading.Thread(target=compute)
            thread.daemon = True
            thread.start()

        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось сравнить концепты: {str(e)}")
            self.status_var.set("Ошибка")

    def display_results(self, result: ComparisonResult):
        for item in self.tree_metrics.get_children():
            self.tree_metrics.delete(item)

        def format_value(val):
            if isinstance(val, float):
                return f"{val:.4f}"
            return str(val)

        metrics_data = [
            ("Общая информация", "", ""),
            ("Концепт 1", result.concept1, ""),
            ("Концепт 2", result.concept2, ""),
            ("Наименьший общий предок", result.lcs, "Самый специфичный общий родительский концепт"),
            ("Онтология", result.ontology_name, ""),
            ("Дата/время", result.timestamp, ""),

            ("", "", ""),
            ("Метрики расстояния (чем меньше, тем ближе)", "", ""),
            ("Расстояние в графе", format_value(result.graph_distance),
             f"{self.interpret_distance(result.graph_distance)}"),
            ("Расстояние Цзян-Конрата", format_value(result.jiang_conrath),
             f"{self.interpret_jiang_distance(result.jiang_conrath)}"),

            ("", "", ""),
            ("Метрики сходства (0-1, чем ближе к 1, тем ближе)", "", ""),
            ("Wu-Palmer", format_value(result.wu_palmer),
             f"{self.interpret_similarity(result.wu_palmer)}"),
            ("Ли", format_value(result.lee),
             f"{self.interpret_similarity(result.lee)}"),
            ("Рескник", format_value(result.resnik),
             f"{self.interpret_similarity(result.resnik)}"),
            ("Лин", format_value(result.lin),
             f"{self.interpret_similarity(result.lin)}"),
            ("Шликер", format_value(result.schlicker),
             f"{self.interpret_similarity(result.schlicker)}"),
            ("Менг", format_value(result.meng),
             f"{self.interpret_similarity(result.meng)}"),
            ("Edge-based", format_value(result.edge_based),
             f"{self.interpret_similarity(result.edge_based)}"),
            ("Батет", format_value(result.batet),
             f"{self.interpret_similarity(result.batet)}"),

            ("", "", ""),
            ("Сводные показатели", "", ""),
            ("Среднее сходство", format_value(result.average_similarity),
             f"{self.interpret_average_similarity(result.average_similarity)}"),
        ]

        for metric, value, interpretation in metrics_data:
            tag = ''
            if 'Общая информация' in metric or 'Метрики' in metric or 'Сводные' in metric:
                tag = 'header'
            elif metric == "":
                tag = 'spacer'

            self.tree_metrics.insert('', tk.END, values=(metric, value, interpretation), tags=(tag,))

        self.tree_metrics.tag_configure('header', font=('Arial', 10, 'bold'))
        self.tree_metrics.tag_configure('spacer', foreground='white')

        self.notebook.select(0)

    def interpret_distance(self, distance):
        if distance == 0:
            return "Один и тот же концепт"
        elif distance < 3:
            return "Очень близкие концепты"
        elif distance < 6:
            return "Близкие концепты"
        elif distance < 10:
            return "Умеренно удаленные концепты"
        else:
            return "Далекие концепты"

    def interpret_jiang_distance(self, distance):
        if distance == 0:
            return "Один и тот же концепт"
        elif distance < 0.2:
            return "Очень близкие концепты"
        elif distance < 0.4:
            return "Близкие концепты"
        elif distance < 0.6:
            return "Умеренно удаленные концепты"
        else:
            return "Далекие концепты"

    def interpret_similarity(self, similarity):
        if similarity > 0.9:
            return "Практически идентичные концепты"
        elif similarity > 0.7:
            return "Очень близкие концепты"
        elif similarity > 0.5:
            return "Близкие концепты"
        elif similarity > 0.3:
            return "Умеренно схожие концепты"
        elif similarity > 0.1:
            return "Слабо схожие концепты"
        else:
            return "Практически не связанные концепты"

    def interpret_average_similarity(self, avg_sim):
        if avg_sim > 0.8:
            return "ОЧЕНЬ ВЫСОКАЯ семантическая близость"
        elif avg_sim > 0.6:
            return "ВЫСОКАЯ семантическая близость"
        elif avg_sim > 0.4:
            return "УМЕРЕННАЯ семантическая близость"
        elif avg_sim > 0.2:
            return "НИЗКАЯ семантическая близость"
        else:
            return "ОЧЕНЬ НИЗКАЯ семантическая близость"

    def save_to_db(self):
        if not hasattr(self, 'current_result'):
            messagebox.showerror("Ошибка", "Сначала выполните сравнение концептов")
            return

        try:
            notes = self.notes_var.get()
            comparison_id = self.db_manager.save_comparison(self.current_result, notes)
            self.current_comparison_id = comparison_id

            messagebox.showinfo("Успех", f"Результаты сохранены в БД с ID: {comparison_id}")
            self.status_var.set(f"Сохранено в БД с ID: {comparison_id}")
            self.load_history()

        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось сохранить в БД: {str(e)}")

    def load_history(self):
        try:
            limit = int(self.history_limit_var.get())
            history = self.db_manager.get_comparison_history(limit)

            for item in self.tree_history.get_children():
                self.tree_history.delete(item)

            for item in history:
                self.tree_history.insert('', tk.END, values=(
                    item['id'],
                    item['timestamp'],
                    item['ontology_name'],
                    item['concept1'],
                    item['concept2'],
                    f"{item['average_similarity']:.4f}",
                    item['lcs']
                ))

            self.status_var.set(f"Загружено {len(history)} записей из истории")

        except ValueError:
            messagebox.showerror("Ошибка", "Лимит должен быть числом")
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось загрузить историю: {str(e)}")

    def clear_history_table(self):
        for item in self.tree_history.get_children():
            self.tree_history.delete(item)

    def view_history_item(self, event):
        selection = self.tree_history.selection()
        if not selection:
            return

        item = self.tree_history.item(selection[0])
        comparison_id = item['values'][0]

        self.view_comparison_details(comparison_id)

    def search_comparisons(self):
        try:
            results = self.db_manager.search_comparisons(
                concept_name=self.search_concept_var.get() if self.search_concept_var.get() else None,
                ontology_name=self.search_ontology_var.get() if self.search_ontology_var.get() else None,
                date_from=self.search_date_from_var.get() if self.search_date_from_var.get() else None,
                date_to=self.search_date_to_var.get() if self.search_date_to_var.get() else None
            )

            for item in self.tree_search.get_children():
                self.tree_search.delete(item)

            for item in results:
                self.tree_search.insert('', tk.END, values=(
                    item['id'],
                    item['timestamp'],
                    item['ontology_name'],
                    item['concept1'],
                    item['concept2'],
                    f"{item['average_similarity']:.4f}"
                ))

            self.status_var.set(f"Найдено {len(results)} записей")

        except Exception as e:
            messagebox.showerror("Ошибка", f"Ошибка поиска: {str(e)}")

    def clear_search(self):
        self.search_concept_var.set("")
        self.search_ontology_var.set("")
        self.search_date_from_var.set("")
        self.search_date_to_var.set("")

        for item in self.tree_search.get_children():
            self.tree_search.delete(item)

    def view_search_item(self, event):
        selection = self.tree_search.selection()
        if not selection:
            return

        item = self.tree_search.item(selection[0])
        comparison_id = item['values'][0]

        self.view_comparison_details(comparison_id)

    def view_comparison_details(self, comparison_id):
        try:
            comparison = self.db_manager.get_comparison_by_id(comparison_id)
            if not comparison:
                messagebox.showerror("Ошибка", "Запись не найдена")
                return

            details_window = tk.Toplevel(self.root)
            details_window.title(f"Детали сравнения ID: {comparison_id}")
            details_window.geometry("600x500")

            text_widget = scrolledtext.ScrolledText(details_window, wrap=tk.WORD, width=70, height=30)
            text_widget.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            text = f"ДЕТАЛИ СРАВНЕНИЯ ID: {comparison_id}\n"
            text += "=" * 60 + "\n\n"

            text += f"Онтология: {comparison['ontology_name']}\n"
            text += f"Концепт 1: {comparison['concept1']}\n"
            text += f"Концепт 2: {comparison['concept2']}\n"
            text += f"LCS: {comparison['lcs']}\n"
            text += f"Дата/время: {comparison['timestamp']}\n"

            if comparison.get('notes'):
                text += f"Примечания: {comparison['notes']}\n"

            text += "\n" + "=" * 60 + "\n"
            text += "МЕТРИКИ:\n"
            text += "=" * 60 + "\n\n"

            for metric in comparison.get('metrics', []):
                text += f"{metric['metric_name']}: {metric['metric_value']:.4f}\n"

            text_widget.insert(tk.END, text)
            text_widget.config(state=tk.DISABLED)

        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось загрузить детали: {str(e)}")

    def load_favorites(self):
        try:
            favorites = self.db_manager.get_favorites()

            for item in self.tree_favorites.get_children():
                self.tree_favorites.delete(item)

            for item in favorites:
                self.tree_favorites.insert('', tk.END, values=(
                    item['id'],
                    item['concept1'],
                    item['concept2'],
                    f"{item['average_similarity']:.4f}",
                    item.get('tag', ''),
                    item.get('favorite_date', '')
                ))

            self.status_var.set(f"Загружено {len(favorites)} избранных")

        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось загрузить избранное: {str(e)}")

    def add_to_favorites(self):
        if not self.current_comparison_id:
            messagebox.showerror("Ошибка", "Сначала сохраните сравнение в БД")
            return

        tag = tk.simpledialog.askstring(
            "Добавить в избранное",
            "Введите тег (опционально):",
            parent=self.root
        )

        try:
            self.db_manager.add_to_favorites(self.current_comparison_id, tag or "")
            messagebox.showinfo("Успех", "Добавлено в избранное")
            self.load_favorites()

        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось добавить в избранное: {str(e)}")

    def remove_from_favorites(self):
        selection = self.tree_favorites.selection()
        if not selection:
            messagebox.showerror("Ошибка", "Выберите запись для удаления")
            return

        item = self.tree_favorites.item(selection[0])
        comparison_id = item['values'][0]

        messagebox.showinfo("Информация",
                            "В данной реализации удаление из избранного требует\n"
                            "дополнительной реализации в классе DatabaseManager")

    def load_statistics(self):
        try:
            stats = self.db_manager.get_statistics()

            self.stats_text.delete(1.0, tk.END)

            text = "СТАТИСТИКА БАЗЫ ДАННЫХ\n"
            text += "=" * 50 + "\n\n"

            text += f"Всего сравнений: {stats.get('total_comparisons', 0)}\n"
            text += f"Уникальных концептов: {stats.get('unique_concepts', 0)}\n"
            text += f"Загруженных онтологий: {stats.get('total_ontologies', 0)}\n"
            text += f"Последнее сравнение: {stats.get('last_comparison', 'Нет данных')}\n\n"

            if 'most_compared' in stats:
                most = stats['most_compared']
                text += f"Самое частое сравнение:\n"
                text += f"  {most['concept1']} ↔ {most['concept2']}\n"
                text += f"  Количество сравнений: {most['count']}\n"

            self.stats_text.insert(tk.END, text)

            self.status_var.set("Статистика загружена")

        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось загрузить статистику: {str(e)}")

    def export_stats(self):
        file_path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )

        if file_path:
            try:
                stats = self.db_manager.get_statistics()
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write("СТАТИСТИКА БАЗЫ ДАННЫХ\n")
                    f.write("=" * 50 + "\n\n")

                    for key, value in stats.items():
                        if isinstance(value, dict):
                            f.write(f"{key}:\n")
                            for k, v in value.items():
                                f.write(f"  {k}: {v}\n")
                        else:
                            f.write(f"{key}: {value}\n")

                messagebox.showinfo("Успех", f"Статистика экспортирована в {file_path}")

            except Exception as e:
                messagebox.showerror("Ошибка", f"Не удалось экспортировать: {str(e)}")

    def export_to_json(self):
        file_path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )

        if file_path:
            try:
                self.db_manager.export_to_json(file_path)
                messagebox.showinfo("Успех", f"Данные экспортированы в {file_path}")

            except Exception as e:
                messagebox.showerror("Ошибка", f"Не удалось экспортировать: {str(e)}")

    def backup_database(self):
        file_path = filedialog.asksaveasfilename(
            defaultextension=".db",
            filetypes=[("Database files", "*.db"), ("All files", "*.*")]
        )

        if file_path:
            try:
                self.db_manager.backup_database(file_path)
                messagebox.showinfo("Успех", f"Резервная копия создана: {file_path}")

            except Exception as e:
                messagebox.showerror("Ошибка", f"Не удалось создать резервную копию: {str(e)}")

    def copy_selected_concept(self):
        selection = self.concepts_listbox.curselection()
        if selection:
            concept = self.concepts_listbox.get(selection[0])
            self.root.clipboard_clear()
            self.root.clipboard_append(concept)
            self.status_var.set(f"Скопировано: {concept}")

    def clear_results(self):
        for item in self.tree_metrics.get_children():
            self.tree_metrics.delete(item)

        self.concept1_var.set("")
        self.concept2_var.set("")
        self.notes_var.set("")

        if hasattr(self, 'current_result'):
            delattr(self, 'current_result')

        self.current_comparison_id = None
        self.status_var.set("Результаты очищены")

    def run(self):
        self.root.mainloop()

def main():
    app = OntologyGUI()
    app.run()

if __name__ == "__main__":
    main()