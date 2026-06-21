import base64

from atsbench.fixtures.pdf_text import first_pages_text, format_pages

# Minimal one-page PDF containing the text "Hello" (generated once, embedded here).
_ONE_PAGE_PDF = base64.b64decode(
    "JVBERi0xLjQKMSAwIG9iago8PC9UeXBlL0NhdGFsb2cvUGFnZXMgMiAwIFI+PgplbmRvYmoKMiAw"
    "IG9iago8PC9UeXBlL1BhZ2VzL0tpZHNbMyAwIFJdL0NvdW50IDE+PgplbmRvYmoKMyAwIG9iago8"
    "PC9UeXBlL1BhZ2UvUGFyZW50IDIgMCBSL01lZGlhQm94WzAgMCAyMDAgMjAwXS9SZXNvdXJjZXM8"
    "PC9Gb250PDwvRjEgNCAwIFI+Pj4+L0NvbnRlbnRzIDUgMCBSPj4KZW5kb2JqCjQgMCBvYmoKPDwv"
    "VHlwZS9Gb250L1N1YnR5cGUvVHlwZTEvQmFzZUZvbnQvSGVsdmV0aWNhPj4KZW5kb2JqCjUgMCBv"
    "YmoKPDwvTGVuZ3RoIDQ0Pj4Kc3RyZWFtCkJUIC9GMSAyNCBUZiAyMCAxMDAgVGQgKEhlbGxvKSBU"
    "agpFVAplbmRzdHJlYW0KZW5kb2JqCnhyZWYKMCA2CjAwMDAwMDAwMDAgNjU1MzUgZiAKMDAwMDAw"
    "MDAwOSAwMDAwMCBuIAowMDAwMDAwMDU4IDAwMDAwIG4gCjAwMDAwMDAxMTUgMDAwMDAgbiAKMDAw"
    "MDAwMDI0MSAwMDAwMCBuIAowMDAwMDAwMzEwIDAwMDAwIG4gCnRyYWlsZXIKPDwvU2l6ZSA2L1Jv"
    "b3QgMSAwIFI+PgpzdGFydHhyZWYKNDA0CiUlRU9GCg=="
)


def test_format_pages_skips_empty_and_numbers_from_one():
    out = format_pages(["alpha", None, "gamma"])
    assert out == "--- Page 1 ---\nalpha\n\n--- Page 3 ---\ngamma"


def test_first_pages_text_reads_pdf():
    out = first_pages_text(_ONE_PAGE_PDF, n=3)
    assert "--- Page 1 ---" in out
    assert "Hello" in out
