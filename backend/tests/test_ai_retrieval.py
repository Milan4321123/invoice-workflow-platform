"""Retrieval must find the paragraph that answers typical AP questions, in German and English."""
import pytest

from services.ai.retrieval import Index, Passage, default_index, tokenize


@pytest.mark.parametrize("question, expected", [
    ("Welche Angaben muss eine Rechnung enthalten?", "§ 14 Abs. 4 UStG"),
    ("Does reverse charge apply to construction services?", "§ 13b Abs. 2 UStG"),
    ("Wie lange müssen Rechnungen aufbewahrt werden?", "§ 147 Abs. 3 AO"),
    ("What is the limit for a small invoice?", "§ 33 UStDV"),
    ("Wann muss ich Bauabzugsteuer einbehalten?", "§ 48"),
    ("Was gilt für die Freistellungsbescheinigung?", "§ 48b"),
    ("Is an e-invoice the same as a PDF?", "§ 14 Abs. 1 UStG"),
])
def test_relevant_paragraph_is_in_top_3(question, expected):
    citations = [p.citation for p in default_index().search(question, 3)]
    assert any(c.startswith(expected) for c in citations), citations


def test_statute_text_is_verbatim_and_sourced():
    passage = next(p for p in default_index().passages if p.citation == "§ 147 Abs. 3 AO")
    assert "acht Jahre" in passage.text
    assert passage.source == "https://www.gesetze-im-internet.de/ao_1977/__147.html"


def test_editorial_notes_are_not_indexed():
    assert not any("(+++" in p.text.split("\n", 1)[1][:5] for p in default_index().passages)


def test_umlauts_and_stemming():
    assert tokenize("Aufbewahrungsfristen für Bauleistungen") == tokenize("aufbewahrungsfristen fuer bauleistung")


def test_unrelated_question_finds_nothing():
    index = Index([Passage("a", "§ 1 X", "Rechnung Steuer", "x")])
    assert index.search("Fußball Ergebnis gestern") == []
