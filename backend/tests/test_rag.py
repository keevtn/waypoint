"""RAG pipeline tests (SPEC.md §6.5, §11). Offline: FakeEmbedder, no model, no network."""
from __future__ import annotations

import re
from urllib.parse import urlparse

import pytest

from app import config
from app.models import RagAskResponse
from app.rag import answer, facts, index, ingest, retrieve
from app.rag.answer import INVESTING_REFUSAL, NO_SOURCE_REFUSAL, ask

ALLOWED_DOMAINS = ("pa.gov", "naic.org", "consumerfinance.gov", "hud.gov", "huduser.gov", "ftc.gov", "usa.gov")
BANNED_NAMES = re.compile(
    r"\bFNB\b|First National|Wells Fargo|Fifth Third|\bChase\b|Bank of America|\bPNC\b|Citizens Bank|Penn State",
    re.IGNORECASE,
)
CITE = re.compile(r"\[s:([^\]\s]+)\]")


# -- corpus ---------------------------------------------------------------------


def test_corpus_has_enough_sources():
    assert len(ingest.corpus_files()) >= 8


@pytest.mark.parametrize("path", ingest.corpus_files(), ids=lambda p: p.stem)
def test_corpus_file_frontmatter_and_publisher(path):
    raw = path.read_text(encoding="utf-8")
    meta, body = ingest.parse_frontmatter(raw)
    for key in ("title", "url", "publisher", "year", "tags"):
        assert meta.get(key), f"{path.name}: missing {key}"
    host = urlparse(meta["url"]).hostname or ""
    assert host.endswith(ALLOWED_DOMAINS), f"{path.name}: {host} is not a gov/regulator/non-profit source"
    assert not BANNED_NAMES.search(raw), f"{path.name}: names a bank or sponsor"
    assert len(body.split()) < 2000


def test_parse_frontmatter_lists_and_scalars():
    meta, body = ingest.parse_frontmatter("---\ntitle: T\nyear: 2025\ntags: [a, b]\n---\n# H\ntext\n")
    assert meta == {"title": "T", "year": "2025", "tags": ["a", "b"]}
    assert body.startswith("# H")


def test_chunks_are_well_formed():
    chunks = ingest.load_corpus()
    ids = [c.id for c in chunks]
    assert len(ids) == len(set(ids))
    for c in chunks:
        assert re.fullmatch(r"[a-z0-9-]+#\d+", c.id)
        assert c.text and len(c.text.split()) <= ingest.MAX_WORDS
        assert c.url and c.publisher and c.tags


def test_long_section_splits_with_overlap(tmp_path):
    para = " ".join(f"w{i}" for i in range(200))
    (tmp_path / "m").mkdir()
    f = tmp_path / "m" / "long.md"
    f.write_text(f"---\ntitle: L\nurl: https://x.gov\npublisher: P\nyear: 2025\ntags: [m]\n---\n## S\n\n{para}\n\n{para}\n")
    chunks = ingest.chunk_file(f, tmp_path)
    assert [c.id for c in chunks] == ["long#0", "long#1"]
    assert chunks[0].module == "m"
    tail = chunks[0].text.split()[-ingest.OVERLAP_WORDS :]
    assert chunks[1].text.split()[: ingest.OVERLAP_WORDS] == tail


# -- key fact ids (Session A cites these) --------------------------------------


@pytest.mark.parametrize("chunk_id,phrase", facts.EXPECTED_TEXT.items())
def test_fact_ids_exist_and_hold_their_fact(chunk_id, phrase):
    chunk = retrieve.get_chunk(chunk_id)
    assert chunk is not None, f"{chunk_id} no longer exists; update rag/facts.py and notify Session A"
    assert phrase.lower() in chunk.text.lower()


def test_citation_for_builds_short_excerpt():
    c = retrieve.citation_for(facts.PA_TORT)
    assert c.chunk_id == facts.PA_TORT
    assert c.publisher == "Pennsylvania Insurance Department"
    assert c.url.startswith("https://")
    assert len(c.excerpt) <= retrieve.EXCERPT_CHARS
    assert retrieve.citation_for("nope#0") is None


# -- index + retrieval ------------------------------------------------------------


def test_fake_embedder_is_used_offline():
    assert isinstance(index.get_embedder(), index.FakeEmbedder)
    assert index.index_chunk_count() == len(ingest.load_corpus())


def test_index_save_load_roundtrip(tmp_path):
    emb = index.FakeEmbedder()
    built = index.build_index(emb)
    built.save(tmp_path)
    loaded = index.Index.load(tmp_path, emb, built.corpus_hash)
    assert loaded is not None and [c.id for c in loaded.chunks] == [c.id for c in built.chunks]
    assert index.Index.load(tmp_path, emb, "stale-hash") is None


def test_fastembed_failure_falls_back(monkeypatch):
    class Boom:
        def __init__(self):
            raise RuntimeError("no model")

    monkeypatch.setattr(config, "LLM_FAKE", False)
    monkeypatch.setattr(index, "FastEmbedEmbedder", Boom)
    monkeypatch.setattr(index, "_embedder", None)
    assert isinstance(index.get_embedder(), index.FakeEmbedder)
    monkeypatch.setattr(index, "_embedder", None)  # restored to the cached fake below


def test_retrieve_ranks_tort_chunk_first():
    hits = retrieve.retrieve("What does limited tort mean in Pennsylvania?", module="auto_insurance")
    assert hits and hits[0].chunk.id == facts.PA_TORT
    assert all(h.score >= index.get_embedder().min_score for h in hits)


def test_retrieve_module_filter():
    hits = retrieve.retrieve("rent affordable share of income emergency savings", module="rent", k=20)
    assert hits
    assert all({"rent", "general"} & set(h.chunk.tags) for h in hits)
    assert not any(h.chunk.slug.startswith("pa-") for h in hits)


# -- /rag/ask logic: the three §11 cases and friends -------------------------------


def _assert_cited(resp: RagAskResponse):
    assert resp.answer and resp.refusal is None and resp.citations
    marked = set(CITE.findall(resp.answer))
    assert marked == {c.chunk_id for c in resp.citations}


def test_ask_limited_tort_cites_pa_insurance_department():
    resp = ask("What does limited tort mean in Pennsylvania?", "auto_insurance")
    _assert_cited(resp)
    assert facts.PA_TORT in {c.chunk_id for c in resp.citations}
    assert resp.citations[0].publisher == "Pennsylvania Insurance Department"
    assert "tort" in resp.answer.lower()


def test_ask_index_fund_is_investing_refusal():
    resp = ask("Should I put my refund in an index fund?", None)
    assert resp == RagAskResponse(answer=None, refusal=INVESTING_REFUSAL, citations=[])


def test_ask_bicycle_is_no_source_refusal():
    resp = ask("Does PA require insurance on a bicycle?", "auto_insurance")
    assert resp == RagAskResponse(answer=None, refusal=NO_SOURCE_REFUSAL, citations=[])


@pytest.mark.parametrize(
    "q",
    ["What's the weather tomorrow?", "Do I need insurance on a boat?", "How much is car insurance for a 21 year old?", "  "],
)
def test_ask_off_corpus_refuses(q):
    assert ask(q, "auto_insurance").refusal == NO_SOURCE_REFUSAL


@pytest.mark.parametrize(
    "q,expect_id",
    [
        ("What are the minimum coverage requirements in Pennsylvania?", None),
        ("Does my lender require collision coverage on a financed car?", None),
        ("How should I pick a deductible?", None),
        ("What happens if my insurance lapses?", facts.PA_LAPSE_SUSPENSION),
        ("How big should my emergency fund be?", None),
        ("Can I get a quote from an independent agent?", facts.INDEPENDENT_AGENT),
    ],
)
def test_ask_in_corpus_questions_answer(q, expect_id):
    resp = ask(q, "auto_insurance")
    _assert_cited(resp)
    if expect_id:
        assert expect_id in {c.chunk_id for c in resp.citations}


@pytest.mark.parametrize(
    "q,investing",
    [
        ("Should I buy stocks with my refund?", True),
        ("Is crypto a good idea?", True),
        ("Should I open a Roth IRA?", True),
        ("How big should my emergency fund be?", False),
        ("What are the fundamentals of liability coverage?", False),
    ],
)
def test_investing_classifier(q, investing):
    assert answer.is_investing_question(q) is investing


# -- LLM path (mocked; real client lands in Phase 6) ---------------------------------


class _StubLLM:
    def __init__(self, result):
        self.result = result
        self.calls: list[tuple[str, dict]] = []

    def call(self, call_type, payload, output_type):
        self.calls.append((call_type, payload))
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


@pytest.fixture
def real_llm_mode(monkeypatch):
    """Exercise the LLM branch while keeping the fake embedder."""
    monkeypatch.setattr(config, "LLM_FAKE", False)

    def install(result):
        stub = _StubLLM(result)
        import app.llm.client as client

        monkeypatch.setattr(client, "get_llm", lambda: stub)
        return stub

    return install


Q_TORT = "What does limited tort mean in Pennsylvania?"


def test_llm_answer_used_and_citations_rebuilt(real_llm_mode):
    stub = real_llm_mode(
        RagAskResponse(answer=f"Limited tort trades premium for fewer rights to sue [s:{facts.PA_TORT}] [s:made-up#9].",
                       refusal=None, citations=[])
    )
    resp = ask(Q_TORT, "auto_insurance")
    call_type, payload = stub.calls[0]
    assert call_type == "rag" and payload["question"] == Q_TORT
    assert facts.PA_TORT in {c["id"] for c in payload["chunks"]}
    assert "made-up#9" not in resp.answer
    assert [c.chunk_id for c in resp.citations] == [facts.PA_TORT]


def test_llm_uncited_answer_falls_back_to_extractive(real_llm_mode):
    real_llm_mode(RagAskResponse(answer="Limited tort is cheaper.", refusal=None, citations=[]))
    _assert_cited(ask(Q_TORT, "auto_insurance"))


def test_llm_error_falls_back_to_extractive(real_llm_mode):
    real_llm_mode(RuntimeError("api down"))
    _assert_cited(ask(Q_TORT, "auto_insurance"))


def test_llm_refusal_is_passed_through(real_llm_mode):
    real_llm_mode(RagAskResponse(answer=None, refusal=None, citations=[]))
    assert ask(Q_TORT, "auto_insurance").refusal == NO_SOURCE_REFUSAL


def test_investing_refusal_never_calls_llm(real_llm_mode):
    stub = real_llm_mode(RuntimeError("must not be called"))
    assert ask("Should I put my refund in an index fund?", None).refusal == INVESTING_REFUSAL
    assert stub.calls == []
