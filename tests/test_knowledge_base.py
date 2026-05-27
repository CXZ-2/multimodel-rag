"""
End-to-end test for RAG knowledge base management platform.

Covers:
  1. Knowledge base page — upload PDFs, view status, view detail, delete
  2. Chat page — create conversation, send question, verify persistence

Usage:
  docker compose up -d              # all services must be running
  python tests/test_knowledge_base.py
"""

import os
import sys
import time
import json
import requests
from playwright.sync_api import sync_playwright

BASE = "http://localhost:8000"
FRONTEND = "http://localhost:3000"
PDF_DIR = "/tmp/test_pdfs"


def generate_test_pdfs():
    """Generate minimal valid PDF files for testing."""
    pdf = b"""%PDF-1.4
1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj
2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj
3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]/Contents 4 0 R/Resources<</Font<</F1 5 0 R>>>>>>endobj
4 0 obj<</Length 44>>stream
BT /F1 18 Tf 72 700 Td (Test Document) Tj ET
endstream
endobj
5 0 obj<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>endobj
xref
0 6
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
0000000115 00000 n
0000000266 00000 n
0000000360 00000 n
trailer<</Size 6/Root 1 0 R>>
startxref
441
%%EOF"""
    os.makedirs(PDF_DIR, exist_ok=True)
    for i in range(3):
        path = os.path.join(PDF_DIR, f"doc_{i+1}.pdf")
        with open(path, "wb") as f:
            f.write(pdf)


# ── Helpers ──────────────────────────────────────────────────

def wait_for_status(doc_id: str, target: str, timeout: int = 60) -> dict:
    """Poll /api/documents/{id}/status until it reaches target status."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = requests.get(f"{BASE}/api/documents/{doc_id}/status")
            s = r.json()
            if s["status"] == target:
                return s
            if s["status"] == "failed":
                return s
        except Exception:
            pass
        time.sleep(2)
    raise TimeoutError(f"Document {doc_id} did not reach '{target}' within {timeout}s")


# ── Test: API ─────────────────────────────────────────────────

def test_api_batch_upload():
    """POST /api/documents/upload with 3 PDFs → returns list of docs."""
    print("\n[1] API batch upload")
    files = []
    for i in range(3):
        path = os.path.join(PDF_DIR, f"doc_{i+1}.pdf")
        files.append(("files", (f"doc_{i+1}.pdf", open(path, "rb"), "application/pdf")))

    r = requests.post(f"{BASE}/api/documents/upload", files=files)
    assert r.status_code == 200, f"upload failed: {r.status_code} {r.text}"
    docs = r.json()
    assert len(docs) == 3, f"expected 3 docs, got {len(docs)}"
    for d in docs:
        assert d["status"] == "pending", f"unexpected status: {d['status']}"
        assert d["filename"].startswith("doc_"), f"unexpected filename: {d['filename']}"
    print(f"  OK — {len(docs)} documents uploaded")
    return docs


def test_api_list_documents():
    """GET /api/documents → returns list with total."""
    print("\n[2] API list documents")
    r = requests.get(f"{BASE}/api/documents")
    assert r.status_code == 200
    data = r.json()
    assert "items" in data and "total" in data
    assert data["total"] >= 3
    print(f"  OK — {data['total']} documents listed")
    return data["items"]


def test_api_document_detail(doc_id: str):
    """GET /api/documents/{id} → returns full detail."""
    print(f"\n[3] API document detail ({doc_id[:8]}...)")
    r = requests.get(f"{BASE}/api/documents/{doc_id}")
    assert r.status_code == 200
    doc = r.json()
    assert doc["id"] == doc_id
    assert doc["filename"]
    assert "status" in doc
    print(f"  OK — {doc['filename']} status={doc['status']}")


def test_api_delete_document(doc_id: str):
    """DELETE /api/documents/{id} → ok."""
    print(f"\n[4] API delete document ({doc_id[:8]}...)")
    r = requests.delete(f"{BASE}/api/documents/{doc_id}")
    assert r.status_code == 200
    assert r.json() == {"ok": True}
    # Verify gone
    r2 = requests.get(f"{BASE}/api/documents/{doc_id}")
    assert r2.status_code == 404
    print("  OK — document deleted")


def test_api_conversation_flow():
    """Full conversation CRUD via API."""
    print("\n[5] API conversation flow")

    # Create
    r = requests.post(f"{BASE}/api/conversations")
    assert r.status_code == 200
    conv = r.json()
    conv_id = conv["id"]
    print(f"  Created: {conv_id[:8]}...")

    # List
    r = requests.get(f"{BASE}/api/conversations")
    assert any(c["id"] == conv_id for c in r.json())

    # Send query
    r = requests.post(f"{BASE}/api/query", json={
        "question": "什么是RAG技术？",
        "conversation_id": conv_id,
    })
    assert r.status_code == 200
    qr = r.json()
    assert "answer" in qr
    print(f"  Answer: {qr['answer'][:60]}...")

    # Check messages saved
    r = requests.get(f"{BASE}/api/conversations/{conv_id}")
    detail = r.json()
    assert len(detail["messages"]) == 2
    assert detail["messages"][0]["role"] == "user"
    assert detail["messages"][1]["role"] == "assistant"
    print(f"  Messages: {len(detail['messages'])} saved")

    # Delete
    r = requests.delete(f"{BASE}/api/conversations/{conv_id}")
    assert r.json() == {"ok": True}
    print("  Deleted — OK")


# ── Test: Image Search + Multi-format ──────────────────────────

def test_api_image_search():
    """POST /api/image-search — upload image, find similar."""
    print("\n[12] API image search")
    from PIL import Image
    import io, base64
    img = Image.new("RGB", (100, 100), "blue")
    buf = io.BytesIO()
    img.save(buf, "PNG")
    b64 = base64.b64encode(buf.getvalue()).decode()

    r = requests.post(f"{BASE}/api/image-search", json={
        "image_base64": b64, "top_k": 5,
    })
    assert r.status_code == 200, f"Expected 200, got {r.status_code}"
    data = r.json()
    assert "results" in data
    print(f"  OK — found {len(data['results'])} images")


def test_api_upload_docx():
    """POST /api/documents/upload — Word document."""
    print("\n[13] Multi-format upload (docx)")
    from docx import Document
    import io
    doc = Document()
    doc.add_paragraph("金融市场是以资金为交易对象的市场。货币政策是央行调控经济的手段。")
    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)
    buf_len = len(buf.read())
    buf.seek(0)

    r = requests.post(f"{BASE}/api/documents/upload",
        files=[("files", ("test_finance.docx", buf.read(),
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"))])
    assert r.status_code == 200, f"Expected 200, got {r.status_code}"
    docs = r.json()
    assert len(docs) > 0
    assert docs[0]["status"] == "pending"
    print(f"  OK — uploaded docx, id={docs[0]['id'][:8]}..., size={buf_len}B")


# ── Test: Frontend ────────────────────────────────────────────

def test_frontend_knowledge_page():
    """UI test for /knowledge page."""
    print("\n[6] Frontend /knowledge page")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.goto(f"{FRONTEND}/knowledge")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(1500)

        # Sidebar visible
        assert page.locator(".app-sidebar").is_visible()
        # Header visible
        assert page.locator(".app-header").is_visible()
        # Table visible (Ant Design)
        table = page.locator(".ant-table")
        assert table.is_visible()

        # Batch upload button
        upload_btn = page.locator("button:has-text('批量上传')")
        assert upload_btn.is_visible()
        print("  Layout OK — sidebar, header, table, upload button all present")

        # Upload a PDF through the file input
        file_input = page.locator("input[type=file]")
        if file_input.count() > 0:
            file_input.first.set_input_files(
                os.path.join(PDF_DIR, "doc_1.pdf")
            )
            page.wait_for_timeout(2000)
            msg = page.locator(".ant-message-notice")
            if msg.count() > 0:
                print(f"  Upload: message notice appeared")
            else:
                print("  Upload: no message (Celery may not be running)")

        # Check for any console errors
        console_errors = []
        page.on("console", lambda m: console_errors.append(m.text) if m.type == "error" else None)

        page.screenshot(path="/tmp/e2e_knowledge.png")
        print(f"  Screenshot: /tmp/e2e_knowledge.png")

        browser.close()
        return console_errors


def test_frontend_chat_page():
    """UI test for /chat page with conversation flow."""
    print("\n[7] Frontend /chat page")

    # Record pre-existing conversations to clean up after test
    pre_ids = {c["id"] for c in requests.get(f"{BASE}/api/conversations").json()}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})

        # Collect console errors
        errors = []
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)

        page.goto(f"{FRONTEND}/chat")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(1500)

        # Conversation sidebar
        conv_sidebar = page.locator(".conv-sidebar")
        assert conv_sidebar.is_visible()
        print("  Conversation sidebar visible")

        # "New" button
        new_btn = page.locator(".conv-new-btn")
        assert new_btn.is_visible()

        # Empty state shows "no conversations"
        empty = page.locator(".conv-empty")
        if empty.is_visible():
            print(f"  Empty state: {empty.inner_text()}")

        # Click "New" to create a conversation
        new_btn.click()
        page.wait_for_timeout(1000)

        # Should now have a conversation in sidebar
        conv_items = page.locator(".conv-item")
        count = conv_items.count()
        print(f"  Conversations after creating: {count}")
        assert count >= 1, "Expected at least 1 conversation after clicking New"

        # Type a question
        textarea = page.locator("textarea.ant-input")
        assert textarea.is_visible()
        textarea.fill("什么是RAG技术？")

        # Click send (the icon-only button in the input bar)
        send_btn = page.get_by_role("button", name="send")
        send_btn.click()

        # Wait for response (may take a few seconds)
        page.wait_for_timeout(8000)

        # Should show answer bubble
        bubbles = page.locator(".chat-bubble.assistant")
        if bubbles.count() > 0:
            bubble_text = bubbles.last.inner_text()
            print(f"  Assistant response: {bubble_text[:80]}...")
        else:
            print("  No assistant bubble found (LLM may be slow or unavailable)")

        # Refresh the page to test persistence
        page.reload()
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(1500)

        # Conversation should still be in sidebar
        conv_items_after = page.locator(".conv-item")
        print(f"  Conversations after refresh: {conv_items_after.count()}")
        assert conv_items_after.count() >= 1, "Conversation should persist after refresh"

        page.screenshot(path="/tmp/e2e_chat.png")
        print(f"  Screenshot: /tmp/e2e_chat.png")

        # Report console errors
        severe = [e for e in errors if "favicon" not in e.lower() and "woff" not in e.lower()]
        if severe:
            print(f"  Console errors: {severe[:5]}")
        else:
            print("  No console errors")

        browser.close()

    # Clean up: delete conversations created by this test
    post_ids = {c["id"] for c in requests.get(f"{BASE}/api/conversations").json()}
    new_ids = post_ids - pre_ids
    for cid in new_ids:
        try:
            requests.delete(f"{BASE}/api/conversations/{cid}")
        except Exception:
            pass
    if new_ids:
        print(f"  Cleaned up {len(new_ids)} conversation(s)")

    return severe


def test_frontend_upload_page():
    """UI test for /upload page."""
    print("\n[8] Frontend /upload page")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.goto(f"{FRONTEND}/upload")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(1500)

        # Header
        assert page.locator(".app-header").is_visible()

        # Upload card with Dragger
        dragger = page.locator(".custom-dragger")
        assert dragger.is_visible()
        print("  Upload Dragger visible")

        # "进入问答" button
        chat_btn = page.locator("button:has-text('进入问答')")
        assert chat_btn.is_visible()

        # Upload a PDF
        file_input = page.locator("input[type=file]")
        file_input.first.set_input_files(
            os.path.join(PDF_DIR, "doc_1.pdf")
        )
        page.wait_for_timeout(5000)

        # After upload, result grid or "开始智能问答" button should appear
        result_btn = page.locator("button:has-text('开始智能问答')")
        if result_btn.is_visible():
            print("  Upload processed — result panel visible")
        else:
            print("  Upload may still be processing...")
            page.wait_for_timeout(10000)
            result_btn = page.locator("button:has-text('开始智能问答')")
            if result_btn.is_visible():
                print("  Upload processed after additional wait")

        page.screenshot(path="/tmp/e2e_upload.png")
        print(f"  Screenshot: /tmp/e2e_upload.png")

        browser.close()


def test_api_crawl():
    """POST /api/documents/crawl → returns crawled documents, Celery processes them."""
    print("\n[9] API web crawl")
    r = requests.post(f"{BASE}/api/documents/crawl", json={
        "source": "gov_zhengce", "limit": 2
    })
    assert r.status_code == 200, f"crawl failed: {r.status_code} {r.text}"
    data = r.json()
    # Allow 0 crawled if all URLs were already in DB (dedup)
    assert data["crawled"] + data["skipped"] >= 1, f"Expected at least 1 result, got {data}"
    status = "OK" if data["crawled"] >= 1 else "SKIP (all deduped)"
    print(f"  {status} — {data['crawled']} crawled, {data['skipped']} skipped")

    for item in data["items"]:
        print(f"    {item['title'][:30]}... -> {item['url']}")

    # Wait for Celery to process (crawl tasks can take 2-4 min each due to CLIP model loading)
    if data["crawled"] > 0:
        print("  Waiting for Celery processing (may take several minutes)...")
        done_ids = []
        for item in data["items"]:
            try:
                status = wait_for_status(item["id"], "done", timeout=300)
                if status["status"] == "done":
                    print(f"  {item['title'][:30]}... -> done ({status['text_chunks']} chunks)")
                    done_ids.append(item["id"])
                else:
                    print(f"  {item['title'][:30]}... -> {status['status']} (error: {status.get('error_message', '')})")
            except TimeoutError as e:
                print(f"  {item['title'][:30]}... -> timeout: {e}")
        assert len(done_ids) >= 1, "Expected at least 1 document to reach 'done' status"
        return done_ids
    return []


def test_api_crawl_query():
    """Verify crawled documents are queryable via RAG."""
    print("\n[10] API query against crawled documents")
    r = requests.post(f"{BASE}/api/query", json={
        "question": "什么是货币政策",
        "top_k": 3,
    })
    assert r.status_code == 200, f"query failed: {r.status_code} {r.text}"
    data = r.json()
    assert "answer" in data
    assert len(data["answer"]) > 20, f"Answer too short: {data['answer']}"
    assert len(data["sources"]) >= 1, f"Expected at least 1 source, got {len(data['sources'])}"
    print(f"  Answer: {data['answer'][:80]}...")
    print(f"  Sources: {len(data['sources'])}")
    for i, s in enumerate(data["sources"][:3]):
        print(f"    [{i+1}] type={s['type']} page={s['page']} score={s['score']:.3f}")


def test_frontend_knowledge_source_column():
    """UI test for source column on /knowledge page."""
    print("\n[11] Frontend /knowledge source column")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.goto(f"{FRONTEND}/knowledge")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(2000)

        # Table should be visible
        table = page.locator(".ant-table")
        assert table.is_visible()

        # Look for source tags
        source_tags = page.locator(".ant-tag")
        tag_count = source_tags.count()
        texts = []
        for i in range(min(tag_count, 20)):
            t = source_tags.nth(i).inner_text()
            texts.append(t)

        print(f"  Tags found: {texts}")
        has_crawled_tag = any("网页爬取" in t for t in texts)
        has_upload_tag = any("上传" in t for t in texts)

        if has_crawled_tag:
            print("  OK — '网页爬取' source tag visible")
        if has_upload_tag:
            print("  OK — '上传' source tag visible")

        page.screenshot(path="/tmp/e2e_knowledge_source.png")
        print(f"  Screenshot: /tmp/e2e_knowledge_source.png")

        browser.close()
        return has_crawled_tag or has_upload_tag


# ── Main ──────────────────────────────────────────────────────

def main():
    generate_test_pdfs()

    # Check backend is reachable
    try:
        r = requests.get(f"{BASE}/", timeout=5)
        print(f"Backend: {r.status_code}")
    except Exception as e:
        print(f"ERROR: Backend not reachable at {BASE}: {e}")
        sys.exit(1)

    # Check frontend is reachable
    try:
        r = requests.get(f"{FRONTEND}/", timeout=5)
        print(f"Frontend: {r.status_code}")
    except Exception as e:
        print(f"ERROR: Frontend not reachable at {FRONTEND}: {e}")
        sys.exit(1)

    results = {"pass": 0, "fail": 0, "skip": 0}

    def test(name, fn, *args):
        try:
            fn(*args)
            results["pass"] += 1
            return True
        except Exception as e:
            print(f"  FAIL [{name}] — {e}")
            results["fail"] += 1
            return False

    def test_get(name, fn, *args):
        try:
            val = fn(*args)
            results["pass"] += 1
            return val
        except Exception as e:
            print(f"  FAIL [{name}] — {e}")
            results["fail"] += 1
            return None

    # Crawl tests (run first — tasks are slow due to CLIP model loading)
    test("API web crawl", test_api_crawl)
    if requests.get(f"{BASE}/api/documents?source_type=crawled").json().get("total", 0) > 0:
        test("API crawl query", test_api_crawl_query)
    else:
        results["skip"] += 1
        print("  SKIP — no crawled documents to query")

    # API tests
    docs = test_get("API batch upload", test_api_batch_upload)
    if docs:
        doc_id = docs[0]["id"]
        test("API list documents", test_api_list_documents)
        test("API document detail", test_api_document_detail, doc_id)
        test("API delete document", test_api_delete_document, doc_id)
    test("API conversation flow", test_api_conversation_flow)

    # API: image search + multi-format
    test("API image search", test_api_image_search)
    test("API multi-format upload", test_api_upload_docx)

    # Frontend tests
    test("Frontend /knowledge", test_frontend_knowledge_page)
    test("Frontend /knowledge source column", test_frontend_knowledge_source_column)
    test("Frontend /chat", test_frontend_chat_page)
    test("Frontend /upload", test_frontend_upload_page)

    print(f"\n{'='*50}")
    print(f"Results: {results['pass']} passed, {results['fail']} failed, {results['skip']} skipped")
    print(f"{'='*50}")

    return results["fail"] == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
