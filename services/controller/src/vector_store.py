from __future__ import annotations

import hashlib
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels
from qdrant_client.http.exceptions import UnexpectedResponse


# ──────────────────────────────────────────────
# Data Models
# ──────────────────────────────────────────────

@dataclass
class RagDocument:
    doc_id: str
    text: str
    source: str = ""
    category: str = ""
    airport_icao: str = ""
    controller_position: str = ""
    tags: List[str] = field(default_factory=list)


# ──────────────────────────────────────────────
# Embedding Providers
# ──────────────────────────────────────────────

class EmbeddingProvider(ABC):
    @abstractmethod
    def embed(self, text: str) -> List[float]:
        ...

    @abstractmethod
    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        ...


class RandomEmbeddingProvider(EmbeddingProvider):
    def __init__(self, dim: int = 384):
        self.dim = dim

    def embed(self, text: str) -> List[float]:
        h = hashlib.md5(text.encode()).hexdigest()
        seed = int(h[:8], 16)
        rng = __import__("random").Random(seed)
        vec = [rng.random() for _ in range(self.dim)]
        norm = sum(x * x for x in vec) ** 0.5
        return [x / norm for x in vec]

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        return [self.embed(t) for t in texts]


class OllamaEmbeddingProvider(EmbeddingProvider):
    def __init__(self, base_url: str = "http://localhost:11434",
                 model: str = "nomic-embed-text"):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self._httpx = None

    @property
    def _client(self):
        if self._httpx is None:
            import httpx
            self._httpx = httpx
        return self._httpx

    def embed(self, text: str) -> List[float]:
        resp = self._client.post(
            f"{self.base_url}/api/embeddings",
            json={"model": self.model, "prompt": text},
            timeout=30.0,
        )
        resp.raise_for_status()
        return resp.json()["embedding"]

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        return [self.embed(t) for t in texts]


# ──────────────────────────────────────────────
# Vector Store
# ──────────────────────────────────────────────

COLLECTION_NAME = "atc_procedures"


class VectorStore:
    def __init__(
        self,
        embedding_provider: EmbeddingProvider,
        qdrant_url: str = "",
        qdrant_client: Optional[QdrantClient] = None,
    ):
        self._embedding = embedding_provider
        if qdrant_client:
            self._client = qdrant_client
        elif qdrant_url:
            self._client = QdrantClient(url=qdrant_url)
        else:
            self._client = QdrantClient(location=":memory:")
        self._dimension: Optional[int] = None

    def _ensure_collection(self) -> str:
        name = COLLECTION_NAME
        try:
            self._client.get_collection(name)
        except (UnexpectedResponse, ValueError):
            dim = self._dimension or 384
            self._client.create_collection(
                collection_name=name,
                vectors_config=qmodels.VectorParams(
                    size=dim,
                    distance=qmodels.Distance.COSINE,
                ),
            )
        return name

    def delete_collection(self) -> None:
        try:
            self._client.delete_collection(COLLECTION_NAME)
        except (UnexpectedResponse, ValueError):
            pass

    def index_documents(self, documents: List[RagDocument]) -> int:
        if not documents:
            return 0
        sample = self._embedding.embed(documents[0].text)
        self._dimension = len(sample)
        coll = self._ensure_collection()

        points: List[qmodels.PointStruct] = []
        for doc in documents:
            vec = self._embedding.embed(doc.text)
            pid = int(hashlib.md5(doc.doc_id.encode()).hexdigest()[:16], 16)
            points.append(qmodels.PointStruct(
                id=pid,
                vector=vec,
                payload={
                    "doc_id": doc.doc_id,
                    "text": doc.text,
                    "source": doc.source,
                    "category": doc.category,
                    "airport_icao": doc.airport_icao,
                    "controller_position": doc.controller_position,
                    "tags": doc.tags,
                },
            ))

        self._client.upsert(collection_name=coll, points=points)
        return len(points)

    def search(
        self,
        query: str = "",
        query_vector: Optional[List[float]] = None,
        airport_icao: str = "",
        controller_position: str = "",
        category: str = "",
        limit: int = 5,
    ) -> List[RagDocument]:
        try:
            self._client.get_collection(COLLECTION_NAME)
        except (UnexpectedResponse, ValueError):
            return []

        if query_vector is None:
            if not query:
                return []
            query_vector = self._embedding.embed(query)

        must_filters: List[qmodels.FieldCondition] = []
        if airport_icao:
            must_filters.append(
                qmodels.FieldCondition(
                    key="airport_icao",
                    match=qmodels.MatchValue(value=airport_icao),
                ),
            )
        if controller_position:
            must_filters.append(
                qmodels.FieldCondition(
                    key="controller_position",
                    match=qmodels.MatchValue(value=controller_position),
                ),
            )
        if category:
            must_filters.append(
                qmodels.FieldCondition(
                    key="category",
                    match=qmodels.MatchValue(value=category),
                ),
            )

        filter_obj = qmodels.Filter(must=must_filters) if must_filters else None

        result = self._client.query_points(
            collection_name=COLLECTION_NAME,
            query=query_vector,
            query_filter=filter_obj,
            limit=limit,
        )

        results: List[RagDocument] = []
        for hit in result.points:
            p = hit.payload or {}
            results.append(RagDocument(
                doc_id=p.get("doc_id", ""),
                text=p.get("text", ""),
                source=p.get("source", ""),
                category=p.get("category", ""),
                airport_icao=p.get("airport_icao", ""),
                controller_position=p.get("controller_position", ""),
                tags=p.get("tags", []),
            ))
        return results

    def format_procedures_for_prompt(
        self,
        airport_icao: str = "",
        controller_position: str = "",
        query: str = "",
        limit: int = 3,
    ) -> str:
        docs = self.search(
            query=query,
            airport_icao=airport_icao,
            controller_position=controller_position,
            limit=limit,
        )
        if not docs:
            return ""
        lines: List[str] = []
        for doc in docs:
            lines.append(f"[{doc.source}] {doc.text}")
        return "\n".join(lines)


# ──────────────────────────────────────────────
# Ingestion Helpers
# ──────────────────────────────────────────────

def create_icao_seed_data() -> List[RagDocument]:
    return [
        RagDocument(
            doc_id="icao_taxi_1",
            text="Start-up approved. Pushback approved, tail east.",
            source="ICAO_DOC4444", category="phraseology",
            controller_position="GROUND",
        ),
        RagDocument(
            doc_id="icao_taxi_2",
            text="Taxi to holding point runway [number] via [route]. "
                 "Hold short of runway [number].",
            source="ICAO_DOC4444", category="phraseology",
            controller_position="GROUND",
        ),
        RagDocument(
            doc_id="icao_tower_1",
            text="Line up and wait runway [number]. "
                 "Cleared for takeoff runway [number], wind [direction/speed].",
            source="ICAO_DOC4444", category="phraseology",
            controller_position="TOWER",
        ),
        RagDocument(
            doc_id="icao_tower_2",
            text="Cleared to land runway [number]. Go around. "
                 "Wind check: wind [direction] [speed] knots.",
            source="ICAO_DOC4444", category="phraseology",
            controller_position="TOWER",
        ),
        RagDocument(
            doc_id="icao_departure_1",
            text="[Callsign], climb via the [SID] departure, "
                 "climb to [altitude] feet.",
            source="ICAO_DOC4444", category="phraseology",
            controller_position="DEPARTURE",
        ),
        RagDocument(
            doc_id="icao_departure_2",
            text="[Callsign], turn left/right heading [degrees], "
                 "radar vector to [fix].",
            source="ICAO_DOC4444", category="phraseology",
            controller_position="DEPARTURE",
        ),
        RagDocument(
            doc_id="icao_approach_1",
            text="[Callsign], fly heading [degrees], descend to [altitude] feet, "
                 "cleared ILS approach runway [number].",
            source="ICAO_DOC4444", category="phraseology",
            controller_position="APPROACH",
        ),
        RagDocument(
            doc_id="icao_approach_2",
            text="[Callsign], hold at [fix] at [altitude] feet, "
                 "left/right hand turns, expect approach at [time].",
            source="ICAO_DOC4444", category="phraseology",
            controller_position="APPROACH",
        ),
        RagDocument(
            doc_id="icao_center_1",
            text="[Callsign], climb to [altitude] feet "
                 "/ descend to [altitude] feet. Maintain [altitude] feet.",
            source="ICAO_DOC4444", category="phraseology",
            controller_position="CENTER",
        ),
        RagDocument(
            doc_id="icao_center_2",
            text="[Callsign], contact [facility] on [frequency]. "
                 "Radar service terminated.",
            source="ICAO_DOC4444", category="phraseology",
            controller_position="CENTER",
        ),
        RagDocument(
            doc_id="icao_delivery_1",
            text="[Callsign], cleared to [destination] via the [SID] departure, "
                 "climb to [altitude] feet, departure frequency [frequency], "
                 "squawk [code].",
            source="ICAO_DOC4444", category="phraseology",
            controller_position="DELIVERY",
        ),
        RagDocument(
            doc_id="icao_readback_1",
            text="Readback shall be required for all clearances and instructions "
                 "affecting the aircraft route, altitude, heading, or speed. "
                 "Use 'READBACK CORRECT' or 'READBACK INCORRECT, [correction]'.",
            source="ICAO_DOC4444", category="separation",
        ),
        RagDocument(
            doc_id="icao_separation_1",
            text="Separation minima: 3 NM lateral or 1000 ft vertical "
                 "within radar coverage. 5 NM lateral outside radar coverage.",
            source="ICAO_DOC4444", category="separation",
        ),
    ]


def create_local_procedures(airport_icao: str) -> List[RagDocument]:
    procedures: List[RagDocument] = []
    code = airport_icao.upper()

    if code == "ESSA":
        procedures.extend([
            RagDocument(
                doc_id=f"{code}_noise_1",
                text="Noise abatement: Runway 01L departures turn left heading 010 "
                     "after passing 1500 feet. Runway 19R departures turn right "
                     "heading 200 after passing 1500 feet.",
                source="LOCAL_PROCEDURE", category="noise_abatement",
                airport_icao=code, controller_position="TOWER",
            ),
            RagDocument(
                doc_id=f"{code}_ground_1",
                text="Pushback: Preferred pushback direction for gate A1-A10 is "
                     "tail east. For gate B1-B8 is tail west.",
                source="LOCAL_PROCEDURE", category="ground_operations",
                airport_icao=code, controller_position="GROUND",
            ),
            RagDocument(
                doc_id=f"{code}_dep_1",
                text="SID RNAV only. No radar vectors for departure "
                     "before 5 NM from airport.",
                source="LOCAL_PROCEDURE", category="departure_procedures",
                airport_icao=code, controller_position="DEPARTURE",
            ),
        ])
    elif code == "KLAX":
        procedures.extend([
            RagDocument(
                doc_id=f"{code}_noise_1",
                text="Noise abatement: Runway 24R departures maintain runway "
                     "heading until 3 DME, then turn left heading 200.",
                source="LOCAL_PROCEDURE", category="noise_abatement",
                airport_icao=code, controller_position="TOWER",
            ),
            RagDocument(
                doc_id=f"{code}_ground_1",
                text="Gate hold program in effect when departure demand exceeds "
                     "20 aircraft. Contact ramp control for pushback approval.",
                source="LOCAL_PROCEDURE", category="ground_operations",
                airport_icao=code, controller_position="GROUND",
            ),
        ])
    else:
        procedures.append(
            RagDocument(
                doc_id=f"{code}_general_1",
                text=f"No specific local procedures documented for {code}. "
                     f"Standard ICAO procedures apply.",
                source="LOCAL_PROCEDURE", category="general",
                airport_icao=code,
            ),
        )

    return procedures
