"""Document search and page rendering helpers without GTK dependencies."""
import pymupdf

from models import SearchResult

CONTEXT_MARGIN_X = 50
CONTEXT_MARGIN_Y = 5


def search_page(page, page_num, text):
    """Returns the SearchResults for one page."""
    results = []
    for rect in page.search_for(text):
        context_rect = pymupdf.Rect(rect.x0 - CONTEXT_MARGIN_X, rect.y0 - CONTEXT_MARGIN_Y,
                                    rect.x1 + CONTEXT_MARGIN_X, rect.y1 + CONTEXT_MARGIN_Y)
        context = page.get_textbox(context_rect).replace('\n', ' ').strip()
        results.append(SearchResult(page_num, rect, context))
    return results


def search_document(path, text, cancelled=None, on_progress=None):
    """Searches every page of the PDF at `path`; opens its own handle so it is safe in a worker thread.

    Stops early (returning what was found so far) when `cancelled()` returns True.
    """
    results = []
    with pymupdf.open(path) as doc:
        total = len(doc)
        for page_num in range(total):
            if cancelled and cancelled():
                break
            results.extend(search_page(doc[page_num], page_num, text))
            if on_progress:
                on_progress(page_num + 1, total)
    return results


def render_thumbnail_png(path, page_num, max_width=150):
    """Renders a page to PNG bytes scaled to `max_width`; opens its own handle (thread safe)."""
    with pymupdf.open(path) as doc:
        page = doc[page_num]
        zoom = max_width / page.rect.width if page.rect.width else 1
        return page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=False).tobytes("png")


def display_rect_to_pdf_box(page, rect):
    """Converts a rectangle in displayed page coordinates (top-left origin, after /Rotate and CropBox)
    into the unrotated PDF user-space box (x0, y0, x1, y1) that signature fields use."""
    r = pymupdf.Rect(rect) * page.derotation_matrix * ~page.transformation_matrix
    r.normalize()
    return (r.x0, r.y0, r.x1, r.y1)
