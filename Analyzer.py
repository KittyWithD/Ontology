from owlready2 import *
from typing import List, Dict, Set
import math
import datetime

from main import ComparisonResult

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