import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import json

import pytest

from prompt_engine import PromptContext, PromptEngine
from tower import TowerController
from ground import GroundController
from vector_store import (
    COLLECTION_NAME,
    EmbeddingProvider,
    RagDocument,
    RandomEmbeddingProvider,
    VectorStore,
    create_icao_seed_data,
    create_local_procedures,
)


@pytest.fixture
def embedding():
    return RandomEmbeddingProvider(dim=64)


@pytest.fixture
def store(embedding):
    s = VectorStore(embedding_provider=embedding)
    s.delete_collection()
    return s


@pytest.fixture
def icao_docs():
    return create_icao_seed_data()


@pytest.fixture
def essa_docs():
    return create_local_procedures("ESSA")


@pytest.fixture
def klax_docs():
    return create_local_procedures("KLAX")


# ──────────────────────────────────────────────
# RagDocument
# ──────────────────────────────────────────────

class TestRagDocument:
    def test_create_minimal(self):
        d = RagDocument(doc_id="test_1", text="some text")
        assert d.doc_id == "test_1"
        assert d.text == "some text"
        assert d.source == ""
        assert d.category == ""
        assert d.airport_icao == ""
        assert d.controller_position == ""
        assert d.tags == []

    def test_create_full(self):
        d = RagDocument(
            doc_id="test_2",
            text="hold at fix",
            source="ICAO_DOC4444",
            category="phraseology",
            airport_icao="ESSA",
            controller_position="TOWER",
            tags=["separation", "holding"],
        )
        assert d.source == "ICAO_DOC4444"
        assert d.airport_icao == "ESSA"
        assert d.tags == ["separation", "holding"]


# ──────────────────────────────────────────────
# RandomEmbeddingProvider
# ──────────────────────────────────────────────

class TestRandomEmbeddingProvider:
    def test_embed_dimensionality(self):
        ep = RandomEmbeddingProvider(dim=64)
        vec = ep.embed("test text")
        assert len(vec) == 64

    def test_embed_normalized(self):
        ep = RandomEmbeddingProvider(dim=384)
        vec = ep.embed("some phraseology text")
        norm = sum(x * x for x in vec) ** 0.5
        assert abs(norm - 1.0) < 0.01

    def test_deterministic_same_text(self):
        ep = RandomEmbeddingProvider(dim=64)
        v1 = ep.embed("cleared to land runway 01L")
        v2 = ep.embed("cleared to land runway 01L")
        assert v1 == v2

    def test_deterministic_different_text(self):
        ep = RandomEmbeddingProvider(dim=64)
        v1 = ep.embed("cleared to land runway 01L")
        v2 = ep.embed("hold at MAKUR at 5000 feet")
        assert v1 != v2

    def test_embed_batch(self):
        ep = RandomEmbeddingProvider(dim=32)
        texts = ["text a", "text b", "text c"]
        vecs = ep.embed_batch(texts)
        assert len(vecs) == 3
        assert all(len(v) == 32 for v in vecs)
        assert vecs[0] != vecs[1]

    def test_dimension_default(self):
        ep = RandomEmbeddingProvider()
        vec = ep.embed("default dim")
        assert len(vec) == 384


# ──────────────────────────────────────────────
# VectorStore — Indexing
# ──────────────────────────────────────────────

class TestVectorStoreIndex:
    def test_index_empty(self, store):
        count = store.index_documents([])
        assert count == 0

    def test_index_single(self, store):
        docs = [RagDocument(doc_id="doc_1", text="test phraseology")]
        count = store.index_documents(docs)
        assert count == 1

    def test_index_multiple(self, store):
        docs = [
            RagDocument(doc_id="doc_1", text="first"),
            RagDocument(doc_id="doc_2", text="second"),
            RagDocument(doc_id="doc_3", text="third"),
        ]
        count = store.index_documents(docs)
        assert count == 3

    def test_index_then_search_finds_docs(self, store):
        docs = [
            RagDocument(
                doc_id="icao_001",
                text="Cleared to land runway 01L. Go around.",
                source="ICAO_DOC4444",
                category="phraseology",
                controller_position="TOWER",
            ),
        ]
        store.index_documents(docs)
        results = store.search(query="landing clearance")
        assert len(results) == 1
        assert results[0].doc_id == "icao_001"


# ──────────────────────────────────────────────
# VectorStore — Search
# ──────────────────────────────────────────────

class TestVectorStoreSearch:
    def test_search_no_docs_returns_empty(self, store):
        results = store.search(query="anything")
        assert results == []

    def test_search_empty_query_returns_empty(self, store):
        results = store.search()
        assert results == []

    def test_search_returns_limited_results(self, store):
        docs = [
            RagDocument(doc_id=f"doc_{i}", text=f"phraseology rule {i}")
            for i in range(10)
        ]
        store.index_documents(docs)
        results = store.search(query="phraseology", limit=3)
        assert len(results) == 3

    def test_search_with_airport_filter(self, store, icao_docs, essa_docs):
        all_docs = icao_docs + essa_docs
        store.index_documents(all_docs)
        results = store.search(
            query="noise abatement",
            airport_icao="ESSA",
        )
        assert len(results) >= 1
        for r in results:
            assert r.airport_icao == "ESSA"

    def test_search_with_position_filter(self, store, icao_docs):
        store.index_documents(icao_docs)
        results = store.search(
            query="takeoff",
            controller_position="TOWER",
        )
        assert len(results) >= 1
        for r in results:
            assert r.controller_position == "TOWER"

    def test_search_with_category_filter(self, store, icao_docs):
        store.index_documents(icao_docs)
        results = store.search(
            query="readback",
            category="separation",
        )
        assert len(results) >= 1
        for r in results:
            assert r.category == "separation"

    def test_search_with_multiple_filters(self, store, icao_docs, essa_docs):
        all_docs = icao_docs + essa_docs
        store.index_documents(all_docs)
        results = store.search(
            query="pushback gate",
            airport_icao="ESSA",
            controller_position="GROUND",
        )
        assert len(results) >= 1
        for r in results:
            assert r.airport_icao == "ESSA"
            assert r.controller_position == "GROUND"

    def test_search_returns_different_airports_independently(
        self, store, essa_docs, klax_docs,
    ):
        store.index_documents(essa_docs + klax_docs)
        essa_results = store.search(
            query="pushback",
            airport_icao="ESSA",
        )
        klax_results = store.search(
            query="pushback",
            airport_icao="KLAX",
        )
        if essa_results:
            assert all(r.airport_icao == "ESSA" for r in essa_results)
        if klax_results:
            assert all(r.airport_icao == "KLAX" for r in klax_results)

    def test_search_returns_empty_for_unmatched_filter(self, store, icao_docs):
        store.index_documents(icao_docs)
        results = store.search(
            query="takeoff",
            airport_icao="NONEXISTENT",
        )
        assert len(results) == 0

    def test_search_with_vector_direct(self, store):
        docs = [
            RagDocument(doc_id="vec_1", text="climb via SID departure"),
        ]
        store.index_documents(docs)
        ep = RandomEmbeddingProvider(dim=64)
        vec = ep.embed("SID climb")
        results = store.search(query_vector=vec)
        assert len(results) == 1

    def test_search_returns_correct_payload(self, store):
        docs = [
            RagDocument(
                doc_id="full_test",
                text="full payload check",
                source="ICAO_DOC4444",
                category="phraseology",
                airport_icao="ESSA",
                controller_position="TOWER",
                tags=["critical"],
            ),
        ]
        store.index_documents(docs)
        results = store.search(query="payload")
        assert len(results) == 1
        r = results[0]
        assert r.doc_id == "full_test"
        assert r.source == "ICAO_DOC4444"
        assert r.airport_icao == "ESSA"
        assert r.controller_position == "TOWER"
        assert r.tags == ["critical"]


# ──────────────────────────────────────────────
# format_procedures_for_prompt
# ──────────────────────────────────────────────

class TestFormatProcedures:
    def test_format_with_results(self, store, icao_docs):
        store.index_documents(icao_docs)
        text = store.format_procedures_for_prompt(
            controller_position="TOWER",
            query="landing",
        )
        assert len(text) > 0
        assert "[ICAO_DOC4444]" in text
        assert "\n" in text

    def test_format_empty_when_no_results(self, store):
        text = store.format_procedures_for_prompt(
            airport_icao="ESSA",
            controller_position="TOWER",
            query="nothing",
        )
        assert text == ""

    def test_format_limit(self, store):
        docs = [
            RagDocument(doc_id=f"doc_{i}", text="rule text here",
                        controller_position="TOWER")
            for i in range(5)
        ]
        store.index_documents(docs)
        text = store.format_procedures_for_prompt(
            controller_position="TOWER",
            query="rule",
            limit=2,
        )
        lines = text.strip().split("\n")
        assert len(lines) == 2

    def test_format_local_procedures(self, store, essa_docs):
        store.index_documents(essa_docs)
        text = store.format_procedures_for_prompt(
            airport_icao="ESSA",
            controller_position="TOWER",
            query="noise abatement",
        )
        assert "[LOCAL_PROCEDURE]" in text
        assert "noise" in text.lower()


# ──────────────────────────────────────────────
# Ingestion Helpers
# ──────────────────────────────────────────────

class TestIngestionHelpers:
    def test_create_icao_seed_data(self):
        docs = create_icao_seed_data()
        assert len(docs) > 0
        for d in docs:
            assert d.source == "ICAO_DOC4444"

    def test_icao_seed_has_all_positions(self):
        docs = create_icao_seed_data()
        positions = set(d.controller_position for d in docs if d.controller_position)
        for pos in ("GROUND", "TOWER", "DEPARTURE", "APPROACH", "CENTER", "DELIVERY"):
            assert pos in positions, f"Missing position: {pos}"

    def test_icao_seed_has_separation_rules(self):
        docs = create_icao_seed_data()
        sep = [d for d in docs if d.category == "separation"]
        assert len(sep) >= 1

    def test_create_essa_procedures(self):
        docs = create_local_procedures("ESSA")
        assert len(docs) >= 1
        for d in docs:
            assert d.airport_icao == "ESSA"
            assert d.source == "LOCAL_PROCEDURE"

    def test_essa_has_noise_abatement(self):
        docs = create_local_procedures("ESSA")
        noise = [d for d in docs if d.category == "noise_abatement"]
        assert len(noise) >= 1

    def test_create_klax_procedures(self):
        docs = create_local_procedures("KLAX")
        assert len(docs) >= 1
        for d in docs:
            assert d.airport_icao == "KLAX"

    def test_unknown_airport_gets_fallback(self):
        docs = create_local_procedures("XYZ")
        assert len(docs) == 1
        assert "Standard ICAO" in docs[0].text

    def test_icao_seed_doc_ids_unique(self):
        docs = create_icao_seed_data()
        ids = [d.doc_id for d in docs]
        assert len(ids) == len(set(ids))


# ──────────────────────────────────────────────
# PromptEngine Integration
# ──────────────────────────────────────────────

class TestPromptEngineEnrichment:
    def test_enrich_adds_local_procedures(self, store, icao_docs, essa_docs):
        store.index_documents(icao_docs + essa_docs)
        engine = PromptEngine(vector_store=store)
        twr = TowerController("ESSA_TWR", 118.5, "ESSA_TWR", "ESSA", ["01L"])
        ctx = PromptContext(controller=twr)
        result = engine.build_radio_call_prompt(ctx)
        assert ctx.local_procedures is not None
        assert "source" in ctx.local_procedures
        assert ctx.local_procedures["source"] == "vector_rag"

    def test_enrich_contains_procedures_text(self, store, icao_docs, essa_docs):
        store.index_documents(icao_docs + essa_docs)
        engine = PromptEngine(vector_store=store)
        twr = TowerController("ESSA_TWR", 118.5, "ESSA_TWR", "ESSA", ["01L"])
        ctx = PromptContext(controller=twr)
        engine.build_radio_call_prompt(ctx)
        text = ctx.local_procedures.get("procedures", "")
        assert len(text) > 0
        assert "[ICAO_DOC4444]" in text or "[LOCAL_PROCEDURE]" in text

    def test_enrich_injects_into_prompt(self, store, icao_docs, essa_docs):
        store.index_documents(icao_docs + essa_docs)
        engine = PromptEngine(vector_store=store)
        twr = TowerController("ESSA_TWR", 118.5, "ESSA_TWR", "ESSA", ["01L"])
        ctx = PromptContext(controller=twr)
        result = engine.build_radio_call_prompt(ctx)
        assert "LOCAL PROCEDURES" in result.full_prompt
        assert "vector_rag" in result.full_prompt

    def test_enrich_skips_if_already_populated(self, store):
        engine = PromptEngine(vector_store=store)
        twr = TowerController("ESSA_TWR", 118.5, "ESSA_TWR", "ESSA", ["01L"])
        ctx = PromptContext(
            controller=twr,
            local_procedures={"manual": "data"},
        )
        engine.build_radio_call_prompt(ctx)
        assert ctx.local_procedures == {"manual": "data"}

    def test_enrich_no_vector_store(self):
        engine = PromptEngine()
        twr = TowerController("ESSA_TWR", 118.5, "ESSA_TWR", "ESSA", ["01L"])
        ctx = PromptContext(controller=twr)
        engine.build_radio_call_prompt(ctx)
        assert ctx.local_procedures is None

    def test_enrich_with_empty_store(self, store):
        engine = PromptEngine(vector_store=store)
        twr = TowerController("ESSA_TWR", 118.5, "ESSA_TWR", "ESSA", ["01L"])
        ctx = PromptContext(controller=twr)
        engine.build_radio_call_prompt(ctx)
        assert ctx.local_procedures is None or ctx.local_procedures == {}

    def test_enrich_ground_controller(self, store, icao_docs, essa_docs):
        store.index_documents(icao_docs + essa_docs)
        engine = PromptEngine(vector_store=store)
        gnd = GroundController("ESSA_GND", 121.8, "ESSA_GND", "ESSA")
        ctx = PromptContext(controller=gnd)
        engine.build_radio_call_prompt(ctx)
        text = ctx.local_procedures.get("procedures", "")
        if text:
            assert "GROUND" in ctx.local_procedures.get("position", "")

    def test_enrich_different_airports(self, store, icao_docs, essa_docs, klax_docs):
        store.index_documents(icao_docs + essa_docs + klax_docs)
        engine = PromptEngine(vector_store=store)
        # ESSA tower
        twr = TowerController("ESSA_TWR", 118.5, "ESSA_TWR", "ESSA", ["01L"])
        ctx1 = PromptContext(controller=twr)
        engine.build_radio_call_prompt(ctx1)
        # KLAX tower
        twr2 = TowerController("KLAX_TWR", 118.5, "KLAX_TWR", "KLAX", ["24R"])
        ctx2 = PromptContext(controller=twr2)
        engine.build_radio_call_prompt(ctx2)
        # Different airports should yield different procedures
        p1 = ctx1.local_procedures.get("airport", "") if ctx1.local_procedures else ""
        p2 = ctx2.local_procedures.get("airport", "") if ctx2.local_procedures else ""
        assert p1 != p2 or p1 == ""


# ──────────────────────────────────────────────
# Integration
# ──────────────────────────────────────────────

class TestIntegration:
    def test_seed_then_search_then_prompt(self, store):
        icao = create_icao_seed_data()
        local = create_local_procedures("ESSA")
        all_docs = icao + local
        count = store.index_documents(all_docs)
        assert count == len(all_docs)

        results = store.search(
            query="takeoff clearance runway",
            controller_position="TOWER",
        )
        assert len(results) >= 1
        assert results[0].controller_position == "TOWER"

        engine = PromptEngine(vector_store=store)
        twr = TowerController("ESSA_TWR", 118.5, "ESSA_TWR", "ESSA", ["01L"])
        ctx = PromptContext(controller=twr)
        prompt = engine.build_radio_call_prompt(ctx)
        assert "LOCAL PROCEDURES" in prompt.full_prompt
        assert prompt.estimated_tokens > 0

    def test_rag_preserves_existing_context(self, store, icao_docs, essa_docs):
        store.index_documents(icao_docs + essa_docs)
        engine = PromptEngine(vector_store=store)
        twr = TowerController("ESSA_TWR", 118.5, "ESSA_TWR", "ESSA", ["01L"])
        ctx = PromptContext(
            controller=twr,
            airports={"ESSA": {"elevation_ft": 150, "runways": {"01L": {}}}},
            weather={"ESSA": {"wind": {"direction": 180, "speed_kn": 10}}},
        )
        prompt = engine.build_radio_call_prompt(ctx)
        assert "ESSA" in prompt.full_prompt
        assert "LOCAL PROCEDURES" in prompt.full_prompt

    def test_prompt_engine_without_vector_store_unchanged(self):
        engine = PromptEngine()
        twr = TowerController("ESSA_TWR", 118.5, "ESSA_TWR", "ESSA", ["01L"])
        ctx = PromptContext(controller=twr)
        prompt = engine.build_radio_call_prompt(ctx)
        assert prompt.full_prompt is not None
        assert prompt.estimated_tokens > 0
        assert "vector_rag" not in prompt.full_prompt

    def test_icao_seed_covers_all_positions(self):
        docs = create_icao_seed_data()
        covered = {d.controller_position for d in docs if d.controller_position}
        all_positions = {"GROUND", "TOWER", "DEPARTURE", "APPROACH", "CENTER", "DELIVERY"}
        assert covered == all_positions, f"Missing: {all_positions - covered}"


# ──────────────────────────────────────────────
# Collection Lifecycle
# ──────────────────────────────────────────────

class TestCollectionLifecycle:
    def test_delete_collection(self, store, icao_docs):
        store.index_documents(icao_docs)
        store.delete_collection()
        results = store.search(query="test")
        assert results == []

    def test_reindex_after_delete(self, store, icao_docs):
        store.index_documents(icao_docs)
        store.delete_collection()
        store.index_documents(icao_docs[:1])
        results = store.search(query="test")
        assert len(results) == 1


# ──────────────────────────────────────────────
# Edge Cases
# ──────────────────────────────────────────────

class TestEdgeCases:
    def test_very_long_text(self, store):
        long_text = "phraseology " * 1000
        docs = [RagDocument(doc_id="long_1", text=long_text)]
        store.index_documents(docs)
        results = store.search(query="phraseology")
        assert len(results) == 1

    def test_special_characters_in_text(self, store):
        docs = [RagDocument(doc_id="special_1", text="QNH 1013 hPa [correction]")]
        store.index_documents(docs)
        results = store.search(query="QNH")
        assert len(results) == 1

    def test_large_batch_index(self, store):
        docs = [
            RagDocument(doc_id=f"batch_{i}", text=f"rule {i}")
            for i in range(50)
        ]
        count = store.index_documents(docs)
        assert count == 50
        results = store.search(query="rule", limit=10)
        assert len(results) == 10
