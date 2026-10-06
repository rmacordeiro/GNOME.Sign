import time

import pymupdf
import pytest

from services.document_service import render_thumbnail_png, search_document
from services.tasks import CancelToken, run_in_thread


def make_big_pdf(path, pages):
    doc = pymupdf.open()
    for i in range(pages):
        page = doc.new_page()
        page.insert_text((72, 72), f"Page {i + 1} lorem ipsum needle" if i % 10 == 0 else f"Page {i + 1} lorem ipsum")
    doc.save(path)
    return str(path)


def test_search_returns_results_with_context(tmp_path):
    path = make_big_pdf(tmp_path / "d.pdf", 25)
    results = search_document(path, "needle")
    assert [r.page_num for r in results] == [0, 10, 20]
    assert "needle" in results[0].context


def test_search_can_be_cancelled(tmp_path):
    path = make_big_pdf(tmp_path / "d.pdf", 25)
    token = CancelToken()
    seen = []

    def progress(done, total):
        seen.append(done)
        if done == 5:
            token.cancel()

    results = search_document(path, "needle", cancelled=token.is_cancelled, on_progress=progress)
    assert seen[-1] == 5
    assert [r.page_num for r in results] == [0]


def test_thumbnail_is_scaled_png(tmp_path):
    path = make_big_pdf(tmp_path / "d.pdf", 2)
    png = render_thumbnail_png(path, 1, 150)
    pix = pymupdf.Pixmap(png)
    assert pix.width in (150, 151)


@pytest.mark.parametrize("pages", [300])
def test_large_document_regression_budget(tmp_path, pages):
    """Generous ceilings that catch accidental quadratic behaviour, not micro-benchmarks."""
    path = make_big_pdf(tmp_path / "big.pdf", pages)

    start = time.perf_counter()
    with pymupdf.open(path) as doc:
        assert len(doc) == pages
    assert time.perf_counter() - start < 2

    start = time.perf_counter()
    results = search_document(path, "needle")
    assert len(results) == pages // 10
    assert time.perf_counter() - start < 15

    start = time.perf_counter()
    for page_num in (0, pages // 2, pages - 1):
        render_thumbnail_png(path, page_num)
    assert time.perf_counter() - start < 3


def test_run_in_thread_skips_callback_when_cancelled():
    from gi.repository import GLib
    loop = GLib.MainLoop()
    calls = []
    token = CancelToken()
    token.cancel()
    run_in_thread(lambda t: 1, lambda r, e: calls.append((r, e)), token)
    GLib.timeout_add(200, loop.quit)
    loop.run()
    assert calls == []


def test_run_in_thread_delivers_result_and_errors():
    from gi.repository import GLib
    loop = GLib.MainLoop()
    calls = []

    def done(result, error):
        calls.append((result, type(error).__name__ if error else None))
        if len(calls) == 2:
            loop.quit()

    run_in_thread(lambda t: 42, done)
    run_in_thread(lambda t: 1 / 0, done)
    GLib.timeout_add(3000, loop.quit)
    loop.run()
    assert sorted(calls, key=str) == [(42, None), (None, "ZeroDivisionError")]
