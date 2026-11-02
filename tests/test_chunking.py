from jmi.rag.chunking import CHUNK_WORDS, OVERLAP_WORDS, chunk, chunk_sections, chunk_window, html_to_lines

POSTING = (
    "<p>We build a data platform for analytics and AI. " + "Context sentence here. " * 15 + "</p>"
    "<h3>Responsibilities</h3><ul><li>Build Airflow DAGs.</li><li>Model data in dbt.</li>"
    + "<li>Own pipelines end to end with tests and monitoring.</li>" * 6 + "</ul>"
    "<div><b>Requirements:</b><br></div><ul><li>5+ years of Python and SQL.</li>"
    + "<li>Experience with ClickHouse or another columnar database.</li>" * 6 + "</ul>"
    "<p>We value <strong>ownership</strong> and curiosity.</p>"
)


def test_html_to_lines_marks_headings_and_list_items():
    lines = html_to_lines(POSTING)
    assert "## Responsibilities" in lines
    assert "## Requirements:" in lines
    assert "- Build Airflow DAGs." in lines
    # Bold inside a sentence is not a heading.
    assert "We value ownership and curiosity." in lines


def test_sections_carry_heading_and_kind():
    chunks = chunk_sections(POSTING)
    kinds = {c.section: c.section_kind for c in chunks}
    assert kinds["Responsibilities"] == "responsibilities"
    assert kinds["Requirements"] == "requirements"
    assert "Build Airflow DAGs." in next(c.text for c in chunks if c.section == "Responsibilities")
    assert [c.index for c in chunks] == list(range(len(chunks)))


def test_tiny_trailing_section_is_merged_not_dropped():
    chunks = chunk_sections(POSTING)
    assert any("ownership" in c.text for c in chunks)
    assert all(len(c.text.split()) >= 10 for c in chunks)


def test_russian_headings_are_classified():
    html = ("<p><strong>Обязанности</strong></p><ul>" + "<li>Разработка ETL-процессов на Airflow</li>" * 10
            + "</ul><p><strong>Требования</strong></p><ul>" + "<li>Опыт работы с Python от 3 лет</li>" * 10
            + "</ul><p><strong>Мы предлагаем</strong></p><ul>" + "<li>Удалённая работа и ДМС</li>" * 10 + "</ul>")
    assert [c.section_kind for c in chunk_sections(html)] == ["responsibilities", "requirements", "benefits"]


def test_window_overlaps_and_covers_all_words():
    words = [f"w{i}" for i in range(CHUNK_WORDS * 2)]
    chunks = chunk_window("<p>" + " ".join(words) + "</p>")
    assert len(chunks) == 3
    first, second = chunks[0].text.split(), chunks[1].text.split()
    assert len(first) == CHUNK_WORDS
    assert first[-OVERLAP_WORDS:] == second[:OVERLAP_WORDS]
    assert chunks[-1].text.split()[-1] == words[-1]


def test_long_section_falls_back_to_windows():
    html = "<h3>Requirements</h3><p>" + "python " * (CHUNK_WORDS + 100) + "</p>"
    chunks = chunk(html, "sections")
    assert len(chunks) == 2
    assert {c.section_kind for c in chunks} == {"requirements"}


def test_empty_description_has_no_chunks():
    assert chunk("", "window") == []
    assert chunk("<p> </p>", "sections") == []
