"""
Retrieval over the knowledge base: the statutes the platform applies
(verbatim from gesetze-im-internet.de) and, when present, the company's own
compliance documentation.

BM25 rather than vector embeddings, on purpose:
- legal questions hinge on exact terms ("§ 13b", "Freistellungsbescheinigung",
  "Kleinbetrag"), which lexical matching handles precisely;
- it needs no embedding provider, second API key or vector database;
- it is deterministic, so retrieval quality is covered by ordinary tests.
English questions are mapped to the German legal vocabulary first.
"""
from dataclasses import dataclass
from functools import lru_cache
import math
from pathlib import Path
import re
from typing import Dict, List, Optional

KNOWLEDGE_DIR = Path(__file__).parent / "knowledge"
COMPANY_DOCS_DIR = Path(__file__).resolve().parents[3] / "docs" / "compliance"

LAW_NAMES = {"ustg": "UStG", "ustdv": "UStDV", "estg": "EStG", "ao": "AO"}

STOPWORDS = set("""
der die das den dem des ein eine einer eines einem einen und oder aber nicht ist sind wird werden wurde
im in ins am an auf aus bei mit nach von vor zu zum zur für fuer über ueber unter durch als auch so wie
wenn dass ob es er sie wir ihr ich man sich sein seine ihre ihren dieser diese dieses jeder jede soweit
nr satz absatz abs vom bis kann können koennen muss müssen muessen hat haben
the a an and or of to in on for is are be does do what which who when how this that with from by
""".split())

# English (and everyday German) words mapped to the terms the statutes use
SYNONYMS = {
    "reverse": ["13b", "steuerschuldner", "leistungsempfaenger"],
    "charge": ["13b", "steuerschuldner"],
    "invoice": ["rechnung"],
    "invoices": ["rechnung"],
    "mandatory": ["angaben", "enthalten"],
    "details": ["angaben"],
    "retention": ["aufzubewahren", "aufbewahrung"],
    "retain": ["aufzubewahren"],
    "keep": ["aufzubewahren"],
    "years": ["jahre"],
    "small": ["kleinbetraege", "250"],
    "withholding": ["steuerabzug", "48"],
    "construction": ["bauleistung", "bauleistungen", "bauwerk"],
    "bauleistung": ["bauwerk"],
    "exemption": ["freistellungsbescheinigung"],
    "certificate": ["freistellungsbescheinigung", "bescheinigung"],
    "electronic": ["elektronische"],
    "einvoice": ["elektronische", "rechnung", "strukturierten"],
    "vat": ["umsatzsteuer", "steuer"],
    "id": ["identifikationsnummer"],
    "tax": ["steuer", "steuernummer"],
    "number": ["nummer", "rechnungsnummer"],
    "date": ["datum", "zeitpunkt"],
    "bauabzugsteuer": ["steuerabzug", "48"],
    "kleinbetragsrechnung": ["kleinbetraege", "250"],
    "aufbewahrungsfrist": ["aufzubewahren", "jahre"],
    "aufbewahrt": ["aufzubewahren", "jahre"],
    "aufbewahren": ["aufzubewahren"],
    "lange": ["jahre"],
    "long": ["jahre"],
    "erechnung": ["elektronische", "rechnung"],
}


@dataclass
class Passage:
    id: str
    citation: str
    text: str
    source: str
    score: float = 0.0


def _fold(text: str) -> str:
    text = text.lower()
    for a, b in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss"), ("-", "")):
        text = text.replace(a, b)
    return text


def _stem(token: str) -> str:
    if token.isdigit() or len(token) <= 5:
        return token
    for suffix in ("ungen", "ung", "en", "er", "es", "e", "n", "s"):
        if token.endswith(suffix) and len(token) - len(suffix) >= 4:
            return token[: -len(suffix)]
    return token


def tokenize(text: str, expand: bool = False) -> List[str]:
    tokens = []
    for raw in re.findall(r"[a-z0-9]+", _fold(text)):
        if raw in STOPWORDS:
            continue
        tokens.append(_stem(raw))
        if expand:
            tokens.extend(_stem(s) for s in SYNONYMS.get(raw, []))
    return tokens


def _law_passages(path: Path) -> List[Passage]:
    lines = path.read_text(encoding="utf-8").split("\n")
    heading = lines[0].lstrip("# ").strip()                  # "§ 14 Ausstellung von Rechnungen"
    section = re.match(r"§\s*\w+", heading).group(0)
    law = LAW_NAMES[path.stem.split("_")[0]]
    source = re.search(r"https://\S+", lines[2]).group(0)
    passages = []
    paragraphs = [p for p in "\n".join(lines[3:]).split("\n\n")
                  # "(+++ ... +++)" are the publisher's cross-reference notes, not law text
                  if p.strip() and not p.strip().startswith("(+++")]
    for number, paragraph in enumerate(paragraphs):
        match = re.match(r"\((\d+[a-z]?)\)", paragraph.strip())
        citation = f"{section} Abs. {match.group(1)} {law}" if match else f"{section} {law}"
        passages.append(Passage(f"{path.stem}-{number}", citation, f"{heading}\n{paragraph.strip()}", source))
    return passages


def _doc_passages(path: Path) -> List[Passage]:
    text = path.read_text(encoding="utf-8")
    title = text.split("\n", 1)[0].lstrip("# ").strip()
    passages = []
    for number, section in enumerate(re.split(r"\n(?=## )", text)):
        heading = section.split("\n", 1)[0].lstrip("# ").strip()
        if len(section.strip()) < 80:
            continue
        citation = title if heading == title else f"{title}: {heading}"
        passages.append(Passage(f"{path.stem}-{number}", citation, section.strip(),
                                f"docs/compliance/{path.name}"))
    return passages


class Index:
    """
    BM25 over passages. b is lower than the usual 0.75 because the most
    important paragraphs (the list of mandatory invoice details, the list
    of reverse-charge cases) are also the longest.
    """

    def __init__(self, passages: List[Passage], k1: float = 1.5, b: float = 0.3):
        self.passages = passages
        self.k1, self.b = k1, b
        self.docs = [tokenize(p.citation + " " + p.text) for p in passages]
        self.avg_len = sum(map(len, self.docs)) / max(len(self.docs), 1)
        document_frequency: Dict[str, int] = {}
        for tokens in self.docs:
            for token in set(tokens):
                document_frequency[token] = document_frequency.get(token, 0) + 1
        n = len(self.docs)
        self.idf = {t: math.log(1 + (n - df + 0.5) / (df + 0.5)) for t, df in document_frequency.items()}

    def search(self, query: str, k: int = 5) -> List[Passage]:
        terms = tokenize(query, expand=True)
        # A paragraph number in the question ("§ 13b", "48b") is a strong hint
        mentioned = {_fold(m) for m in re.findall(r"§\s*(\d+[a-z]?)", query)}
        scored = []
        for passage, tokens in zip(self.passages, self.docs):
            counts: Dict[str, int] = {}
            for token in tokens:
                counts[token] = counts.get(token, 0) + 1
            score = 0.0
            for term in set(terms):
                tf = counts.get(term, 0)
                if tf:
                    norm = self.k1 * (1 - self.b + self.b * len(tokens) / self.avg_len)
                    score += self.idf.get(term, 0) * tf * (self.k1 + 1) / (tf + norm)
            section = re.match(r"§\s*(\w+)", passage.citation)
            if section and _fold(section.group(1)) in mentioned:
                score *= 1.5
            if score > 0:
                scored.append(Passage(passage.id, passage.citation, passage.text, passage.source, round(score, 3)))
        return sorted(scored, key=lambda p: p.score, reverse=True)[:k]


@lru_cache(maxsize=1)
def default_index() -> Index:
    passages: List[Passage] = []
    for path in sorted((KNOWLEDGE_DIR / "laws").glob("*.md")):
        passages += _law_passages(path)
    if COMPANY_DOCS_DIR.is_dir():
        for path in sorted(COMPANY_DOCS_DIR.glob("*.md")):
            passages += _doc_passages(path)
    return Index(passages)


def search(query: str, k: int = 5, index: Optional[Index] = None) -> List[Passage]:
    return (index or default_index()).search(query, k)
