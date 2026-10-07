import os
import sys
import io
import pandas as pd
import pymupdf as fitz
from docx import Document

# Ensure project root is in python path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from document_processors import (
    extract_text,
    count_word_occurrences,
    extract_pdf_text,
    extract_docx_text,
    extract_doc_text,
    extract_xlsx_text,
    extract_xls_text
)
from app import app

def create_sample_files(test_dir):
    os.makedirs(test_dir, exist_ok=True)

    # 1. Sample PDF 1: Contains AI 5 times
    pdf1_path = os.path.join(test_dir, "document1.pdf")
    doc1 = fitz.open()
    page1 = doc1.new_page()
    pdf1_text = (
        "AI is revolutionizing industries across the globe.\n"
        "Modern AI models process data rapidly.\n"
        "With AI, healthcare diagnostics have improved.\n"
        "Ethics in AI are crucial for future developments.\n"
        "Researchers continue to advance AI safety.\n"
        "Notice: words like TRAIN, CLAIM, and MAIN must not match."
    )
    page1.insert_text((50, 72), pdf1_text)
    doc1.save(pdf1_path)
    doc1.close()

    # 2. Sample PDF 2: Contains AI 2 times
    pdf2_path = os.path.join(test_dir, "document2.pdf")
    doc2 = fitz.open()
    page2 = doc2.new_page()
    pdf2_text = (
        "Renewable energy systems are expanding rapidly worldwide.\n"
        "Solar and wind energy generate clean electricity.\n"
        "Smart grids leverage AI to balance electrical loads.\n"
        "Grid efficiency increases when AI controls battery storage."
    )
    page2.insert_text((50, 72), pdf2_text)
    doc2.save(pdf2_path)
    doc2.close()

    # 3. Sample DOCX: Contains AI 3 times
    docx_path = os.path.join(test_dir, "report.docx")
    doc = Document()
    doc.add_heading("Financial Markets Overview", level=1)
    doc.add_paragraph("Global financial markets experienced growth this quarter.")
    doc.add_paragraph("Algorithmic trading using AI continues to expand in volume.")
    doc.add_paragraph("Regulators examine how AI impacts liquidity and risk.")
    doc.add_paragraph("Investors adopt AI tools for predictive portfolio management.")
    doc.save(docx_path)

    # 4. Sample XLSX: Contains AI 4 times
    xlsx_path = os.path.join(test_dir, "data.xlsx")
    df = pd.DataFrame({
        "Project": ["AI Vision", "Cloud Storage", "AI Chatbot", "Network Security", "AI Analytics"],
        "Category": ["Deep Learning", "Infrastructure", "NLP", "Cybersecurity", "Big Data"],
        "Budget_AI": [50000, 20000, 35000, 40000, 60000]
    })
    with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Projects", index=False)

    # 5. Sample Legacy DOC (RTF/binary wrapper): Contains AI 2 times
    doc_path = os.path.join(test_dir, "legacy_note.doc")
    # Clean RTF format validly recognized as .doc
    rtf_content = (
        r"{\rtf1\ansi\deff0 {\fonttbl {\f0 Courier;}}"
        r"\f0\fs24 Aerospace engineering and autonomous navigation.\par "
        r"Modern aircraft utilize AI for autopiloting assistance.\par "
        r"Safety protocols require human oversight alongside AI systems.\par}"
    )
    with open(doc_path, "w", encoding="utf-8") as f:
        f.write(rtf_content)

    # 6. Corrupted file
    corrupt_path = os.path.join(test_dir, "corrupted.pdf")
    with open(corrupt_path, "wb") as f:
        f.write(b"NOT_A_REAL_PDF_DATA_COMPLETELY_CORRUPTED")

    return {
        "pdf1": pdf1_path,
        "pdf2": pdf2_path,
        "docx": docx_path,
        "xlsx": xlsx_path,
        "doc": doc_path,
        "corrupt": corrupt_path
    }

def run_tests():
    test_dir = os.path.join(BASE_DIR, "test_docs")
    print("=== STEP 1: Creating Sample Test Documents ===")
    files = create_sample_files(test_dir)
    print("Created test files successfully.")

    print("\n=== STEP 2: Testing Word Count Logic (Whole-Word vs Substring) ===")
    test_text = "AI is great. Training models is fun. She claimed the train had AI installed."
    count_ai = count_word_occurrences(test_text, "AI")
    print(f"Text: '{test_text}'")
    print(f"Searched 'AI' -> Count: {count_ai} (Expected: 2, must not count 'Training', 'claimed', 'train')")
    assert count_ai == 2, f"Word count mismatch: expected 2, got {count_ai}"
    print("[OK] Word count whole-word boundary test passed.")

    print("\n=== STEP 3: Testing Text Extraction by Format ===")
    for key, path in files.items():
        if key == "corrupt":
            continue
        with open(path, "rb") as f:
            text = extract_text(f, os.path.basename(path))
            print(f"[{key.upper()}] {os.path.basename(path)}: Extracted {len(text)} characters.")
            assert len(text) > 0, f"Extracted text was empty for {path}"
    print("[OK] All individual file format extractions passed.")

    print("\n=== STEP 4: Testing Flask API Client ===")
    client = app.test_client()

    # TEST 6: Upload no files
    res_no_file = client.post("/analyze", data={"search_word": "AI"})
    print(f"Test 6 (No files) -> Status: {res_no_file.status_code}, Response: {res_no_file.get_json()['message']}")
    assert res_no_file.status_code == 400

    # TEST 7: Enter no search word
    with open(files["pdf1"], "rb") as f:
        res_no_word = client.post("/analyze", data={"files[]": (f, "document1.pdf"), "search_word": ""})
    print(f"Test 7 (No search word) -> Status: {res_no_word.status_code}, Response: {res_no_word.get_json()['message']}")
    assert res_no_word.status_code == 400

    # TEST 1: Upload single document (PDF)
    print("\n=== TEST 1: Single Document Upload (document1.pdf) ===")
    with open(files["pdf1"], "rb") as f:
        res_single = client.post("/analyze", data={
            "files[]": (f, "document1.pdf"),
            "search_word": "AI"
        })
    single_data = res_single.get_json()
    print(f"Test 1 result: Success={single_data['success']}, Processed={single_data['processed']}, Results count={len(single_data['results'])}")
    r0 = single_data['results'][0]
    print(f"  File: {r0['filename']} | Word: '{r0['word']}' | Count: {r0['word_count']} | Status: {r0['status']}")
    print(f"  Summary:\n{r0['summary']}")
    assert r0['word_count'] == 5, f"Expected 5, got {r0['word_count']}"

    # TEST 3 & 4: Mixed formats upload (PDF, DOCX, XLSX, DOC) + TEST 5: Corrupted file inclusion
    print("\n=== TEST 3, 4, 5: Multiple Mixed Formats + Corrupted File Handling ===")
    f_pdf1 = open(files["pdf1"], "rb")
    f_pdf2 = open(files["pdf2"], "rb")
    f_docx = open(files["docx"], "rb")
    f_xlsx = open(files["xlsx"], "rb")
    f_doc = open(files["doc"], "rb")
    f_corrupt = open(files["corrupt"], "rb")

    multi_payload = {
        "search_word": "AI",
        "files[]": [
            (f_pdf1, "document1.pdf"),
            (f_pdf2, "document2.pdf"),
            (f_docx, "report.docx"),
            (f_xlsx, "data.xlsx"),
            (f_doc, "legacy_note.doc"),
            (f_corrupt, "corrupted.pdf")
        ]
    }

    res_multi = client.post("/analyze", data=multi_payload)
    multi_data = res_multi.get_json()

    f_pdf1.close()
    f_pdf2.close()
    f_docx.close()
    f_xlsx.close()
    f_doc.close()
    f_corrupt.close()

    print(f"Multi-doc result: Total={multi_data['total_files']}, Processed={multi_data['processed']}, Failed={multi_data['failed']}")
    for r in multi_data["results"]:
        print(f"-> {r['filename']} ({r['file_type']}): Count={r['word_count']}, Status={r['status']}")
        if r['error']:
            print(f"   Error: {r['error']}")
        else:
            print(f"   Summary: {r['summary'][:60]}...")

    assert multi_data['total_files'] == 6
    assert multi_data['processed'] == 5  # 5 valid files succeeded
    assert multi_data['failed'] == 1     # corrupted.pdf failed without breaking the others!

    print("\n=== TEST BACKWARD COMPATIBILITY: Legacy /search Endpoint ===")
    with open(files["pdf1"], "rb") as f:
        res_legacy = client.post("/search", data={
            "file": (f, "document1.pdf"),
            "search_word": "AI"
        })
    print("Legacy /search response:", res_legacy.get_json())
    assert res_legacy.get_json()["found"] is True
    assert res_legacy.get_json()["count"] == 5

    print("\n=== TEST BACKWARD COMPATIBILITY: Legacy /summarize Endpoint ===")
    res_summarize = client.post("/summarize", data={
        "text": "Artificial Intelligence is transforming software development. AI models assist in debugging code. AI optimizes system performance. Modern AI applications process multimodal data. Responsible AI frameworks ensure safety.",
        "search_word": "AI"
    })
    sum_data = res_summarize.get_json()
    print("Legacy /summarize response:", sum_data)
    assert sum_data["success"] is True
    assert len(sum_data["summary"]) > 0

    print("\n==========================================")
    print("ALL TESTS PASSED SUCCESSFULLY!")
    print("==========================================")

if __name__ == "__main__":
    run_tests()

