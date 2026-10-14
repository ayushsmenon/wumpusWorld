from collections import defaultdict, deque
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
import os
from typing import Any


@dataclass(frozen=True)
class TopicNode:
    id: int
    course_id: int
    title: str
    description: str | None = None
    parent_id: int | None = None
    order_index: int = 0
    prerequisites: list[int] = field(default_factory=list)


@dataclass(frozen=True)
class TopicMasteryInfo:
    topic_id: int
    mastery_score: float
    confidence: float


@dataclass
class RecommendationItem:
    topic_id: int
    title: str
    status: str
    mastery_score: float
    confidence: float
    priority: float
    reason: str
    blocking_prerequisites: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class AdaptiveRecommendationEngine:
    def __init__(
        self,
        db_url: str | None = None,
        connection_factory: Callable[[], Any] | None = None,
        default_mastery_threshold: float = 0.70,
    ) -> None:
        self.db_url = db_url or os.getenv("DATABASE_URL")
        self._connection_factory = connection_factory
        self.default_mastery_threshold = default_mastery_threshold

    def _get_connection(self) -> Any:
        if self._connection_factory is not None:
            return self._connection_factory()
        if not self.db_url:
            raise RuntimeError("DATABASE_URL is not configured")
        try:
            import psycopg
            from psycopg.rows import dict_row

            return psycopg.connect(self.db_url, row_factory=dict_row)
        except ImportError:
            import psycopg2
            from psycopg2.extras import RealDictCursor

            return psycopg2.connect(self.db_url, cursor_factory=RealDictCursor)

    def load_course_topics(self, course_id: int) -> dict[int, TopicNode]:
        conn = self._get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, course_id, parent_id, title, description, order_index
                    FROM topics
                    WHERE course_id = %s
                    ORDER BY order_index ASC, id ASC;
                    """,
                    (course_id,),
                )
                topic_rows = cur.fetchall()

                cur.execute(
                    """
                    SELECT tp.topic_id, tp.prerequisite_id
                    FROM topic_prerequisites tp
                    JOIN topics t ON tp.topic_id = t.id
                    WHERE t.course_id = %s;
                    """,
                    (course_id,),
                )
                prereq_rows = cur.fetchall()
        finally:
            conn.close()

        prereqs_map: dict[int, list[int]] = defaultdict(list)
        for row in prereq_rows:
            data = row if isinstance(row, dict) else dict(row)
            prereqs_map[data["topic_id"]].append(data["prerequisite_id"])

        topics: dict[int, TopicNode] = {}
        for row in topic_rows:
            data = row if isinstance(row, dict) else dict(row)
            tid = data["id"]
            topics[tid] = TopicNode(
                id=tid,
                course_id=data["course_id"],
                title=data["title"],
                description=data.get("description"),
                parent_id=data.get("parent_id"),
                order_index=data.get("order_index") or 0,
                prerequisites=prereqs_map.get(tid, []),
            )
        return topics

    def load_student_masteries(
        self,
        student_id: int,
        course_id: int,
    ) -> dict[int, TopicMasteryInfo]:
        conn = self._get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT lm.topic_id, lm.mastery_score, lm.confidence
                    FROM learner_mastery lm
                    JOIN topics t ON lm.topic_id = t.id
                    WHERE lm.student_id = %s AND t.course_id = %s;
                    """,
                    (student_id, course_id),
                )
                rows = cur.fetchall()
        finally:
            conn.close()

        masteries: dict[int, TopicMasteryInfo] = {}
        for row in rows:
            data = row if isinstance(row, dict) else dict(row)
            tid = data["topic_id"]
            masteries[tid] = TopicMasteryInfo(
                topic_id=tid,
                mastery_score=float(data["mastery_score"]),
                confidence=float(data["confidence"]),
            )
        return masteries

    def topological_sort(self, topics: dict[int, TopicNode]) -> list[int]:
        in_degree: dict[int, int] = {tid: 0 for tid in topics}
        adjacency: dict[int, list[int]] = defaultdict(list)

        for tid, node in topics.items():
            for pid in node.prerequisites:
                if pid in topics:
                    adjacency[pid].append(tid)
                    in_degree[tid] += 1

        queue = deque(
            sorted(
                [tid for tid, deg in in_degree.items() if deg == 0],
                key=lambda x: (topics[x].order_index, x),
            )
        )
        ordered: list[int] = []

        while queue:
            curr = queue.popleft()
            ordered.append(curr)
            for dep in sorted(adjacency[curr], key=lambda x: (topics[x].order_index, x)):
                in_degree[dep] -= 1
                if in_degree[dep] == 0:
                    queue.append(dep)

        for tid in topics:
            if tid not in ordered:
                ordered.append(tid)

        return ordered

    def get_transitive_prerequisites(
        self,
        topic_id: int,
        topics: dict[int, TopicNode],
    ) -> list[int]:
        visited: set[int] = set()
        result: list[int] = []

        def dfs(curr_id: int) -> None:
            node = topics.get(curr_id)
            if not node:
                return
            for pid in node.prerequisites:
                if pid in topics and pid not in visited:
                    visited.add(pid)
                    dfs(pid)
                    result.append(pid)

        dfs(topic_id)
        return result

    def identify_weak_topics(
        self,
        student_id: int,
        course_id: int,
        mastery_threshold: float | None = None,
    ) -> list[dict[str, Any]]:
        topics = self.load_course_topics(course_id)
        masteries = self.load_student_masteries(student_id, course_id)
        threshold = mastery_threshold or self.default_mastery_threshold
        return self.analyze_weak_topics(topics, masteries, threshold)

    def analyze_weak_topics(
        self,
        topics: dict[int, TopicNode],
        masteries: dict[int, TopicMasteryInfo],
        mastery_threshold: float,
    ) -> list[dict[str, Any]]:
        dependents: dict[int, list[int]] = defaultdict(list)
        for tid, node in topics.items():
            for pid in node.prerequisites:
                dependents[pid].append(tid)

        weak_list: list[dict[str, Any]] = []

        for tid, node in topics.items():
            m_info = masteries.get(tid)
            score = m_info.mastery_score if m_info else 0.0
            confidence = m_info.confidence if m_info else 0.0

            if score < mastery_threshold and (confidence > 0.0 or m_info is not None):
                deficit = round(mastery_threshold - score, 4)
                root_cause_prereqs = []
                for pid in node.prerequisites:
                    p_info = masteries.get(pid)
                    p_score = p_info.mastery_score if p_info else 0.0
                    if p_score < mastery_threshold:
                        p_node = topics.get(pid)
                        root_cause_prereqs.append(
                            {
                                "prerequisite_id": pid,
                                "title": p_node.title if p_node else f"Topic {pid}",
                                "mastery_score": p_score,
                            }
                        )

                dependent_count = len(dependents.get(tid, []))
                base_priority = deficit * (1.0 + 0.25 * dependent_count)
                if not root_cause_prereqs:
                    priority = round(base_priority * 1.2, 4)
                else:
                    priority = round(base_priority * 0.9, 4)

                weak_list.append(
                    {
                        "topic_id": tid,
                        "title": node.title,
                        "mastery_score": score,
                        "confidence": confidence,
                        "deficit": deficit,
                        "priority": priority,
                        "dependent_count": dependent_count,
                        "root_cause_prerequisites": root_cause_prereqs,
                    }
                )

        weak_list.sort(key=lambda item: (-item["priority"], -item["deficit"]))
        return weak_list

    def suggest_study_path(
        self,
        student_id: int,
        course_id: int,
        target_topic_id: int | None = None,
        mastery_threshold: float | None = None,
    ) -> list[dict[str, Any]]:
        topics = self.load_course_topics(course_id)
        masteries = self.load_student_masteries(student_id, course_id)
        threshold = mastery_threshold or self.default_mastery_threshold
        return self.compute_study_path(topics, masteries, target_topic_id, threshold)

    def compute_study_path(
        self,
        topics: dict[int, TopicNode],
        masteries: dict[int, TopicMasteryInfo],
        target_topic_id: int | None = None,
        mastery_threshold: float = 0.70,
    ) -> list[dict[str, Any]]:
        if not topics:
            return []

        if target_topic_id is not None and target_topic_id in topics:
            subgraph_ids = set(self.get_transitive_prerequisites(target_topic_id, topics))
            subgraph_ids.add(target_topic_id)
            filtered_topics = {tid: topics[tid] for tid in subgraph_ids}
        else:
            filtered_topics = topics

        sorted_topic_ids = self.topological_sort(filtered_topics)
        study_path: list[RecommendationItem] = []

        for tid in sorted_topic_ids:
            node = filtered_topics[tid]
            m_info = masteries.get(tid)
            score = m_info.mastery_score if m_info else 0.0
            confidence = m_info.confidence if m_info else 0.0

            unmet_prereqs = []
            for pid in node.prerequisites:
                if pid in topics:
                    p_info = masteries.get(pid)
                    p_score = p_info.mastery_score if p_info else 0.0
                    if p_score < mastery_threshold:
                        p_node = topics.get(pid)
                        unmet_prereqs.append(
                            {
                                "topic_id": pid,
                                "title": p_node.title if p_node else f"Topic {pid}",
                                "mastery_score": p_score,
                            }
                        )

            is_mastered = score >= mastery_threshold
            has_unmet_prereqs = len(unmet_prereqs) > 0
            has_attempted = m_info is not None and (confidence > 0.0 or score > 0.0)

            if is_mastered:
                status = "mastered"
                priority = 0.0
                reason = "Target mastery attained"
            elif has_unmet_prereqs:
                status = "blocked"
                priority = round(max(0.05, 0.5 - 0.1 * len(unmet_prereqs)), 4)
                reason = f"Blocked by {len(unmet_prereqs)} prerequisite topic(s)"
            elif has_attempted and score < mastery_threshold:
                status = "remediation"
                priority = round(1.0 + (mastery_threshold - score), 4)
                reason = "Prerequisites satisfied; needs remediation to reach mastery threshold"
            else:
                status = "ready_to_learn"
                priority = round(0.8 + (mastery_threshold - score), 4)
                reason = "All prerequisites satisfied; ready to begin learning"

            study_path.append(
                RecommendationItem(
                    topic_id=tid,
                    title=node.title,
                    status=status,
                    mastery_score=score,
                    confidence=confidence,
                    priority=priority,
                    reason=reason,
                    blocking_prerequisites=unmet_prereqs,
                )
            )

        study_path.sort(
            key=lambda item: (
                0 if item.status == "remediation" else 1 if item.status == "ready_to_learn" else 2 if item.status == "blocked" else 3,
                -item.priority,
            )
        )

        return [item.to_dict() for item in study_path]

    def recommend_next_topics(
        self,
        student_id: int,
        course_id: int,
        limit: int = 3,
        mastery_threshold: float | None = None,
    ) -> list[dict[str, Any]]:
        study_path = self.suggest_study_path(
            student_id=student_id,
            course_id=course_id,
            mastery_threshold=mastery_threshold,
        )
        actionable = [
            item for item in study_path
            if item["status"] in {"remediation", "ready_to_learn"}
        ]
        if len(actionable) < limit:
            blocked_items = [item for item in study_path if item["status"] == "blocked"]
            actionable.extend(blocked_items[: limit - len(actionable)])
        return actionable[:limit]
