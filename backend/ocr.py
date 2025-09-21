# ===============================
# Enhanced OCR with Table Support (EC2-friendly)
# ===============================

import os
import gc
import json
import tempfile
from typing import List

import cv2
import numpy as np
from PIL import Image
from pdf2image import convert_from_path
import pytesseract

# -------------------------------
# Config (tweak as needed)
# -------------------------------
DPI = 250  # 200-300 is plenty for most tables; 400 can OOM small instances
POPPLER_PATH = "/usr/bin"  # Ubuntu poppler-utils installs here
TESS_LANG = "eng"          # e.g., "eng+msa" if you installed both
OMP_THREADS = "1"          # limit Tesseract/OpenMP threads to reduce spikes
os.environ.setdefault("OMP_THREAD_LIMIT", OMP_THREADS)

# -------------------------------
# Step 1: PDF -> image file paths (disk-backed)
# -------------------------------
def pdf_to_image_paths(pdf_path: str, dpi: int = DPI, poppler_path: str = POPPLER_PATH) -> List[str]:
    """
    Convert PDF pages to PNG files on disk (no big in-memory PIL list).
    """
    outdir = tempfile.mkdtemp(prefix="ocr_pages_")
    paths = convert_from_path(
        pdf_path,
        dpi=dpi,
        fmt="png",
        output_folder=outdir,
        output_file="page",
        paths_only=True,     # <--- important to avoid keeping PIL images in RAM
        thread_count=1,      # Poppler threading can spike RAM on small instances
        poppler_path=poppler_path
    )
    return paths

# -------------------------------
# Step 3: Enhanced image processing for tables
# -------------------------------
def enhance_for_tables(image_path: str) -> Image.Image:
    """
    Enhance image specifically for table recognition (grayscale-only to save RAM).
    """
    img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)  # grayscale saves RAM
    if img is None:
        raise RuntimeError(f"Failed to read image: {image_path}")

    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(img)
    denoised = cv2.medianBlur(enhanced, 3)
    kernel = np.array([[-1,-1,-1],
                       [-1, 9,-1],
                       [-1,-1,-1]], dtype=np.int32)
    sharpened = cv2.filter2D(denoised, -1, kernel)
    return Image.fromarray(sharpened)

# -------------------------------
# Step 2: Multiple OCR approaches (per image)
# -------------------------------
def extract_with_multiple_methods(image_path: str, lang: str = TESS_LANG):
    """
    Try multiple OCR configurations to find the best one for tables.
    Processes a single image and returns results dict.
    """
    img = Image.open(image_path)
    results = {}

    def run(cfg: str, key: str):
        try:
            txt = pytesseract.image_to_string(img, lang=lang, config=cfg)
            results[key] = {
                'config': cfg, 'text': txt.strip(), 'char_count': len(txt.strip())
            }
        except Exception as e:
            results[key] = {'error': str(e)}

    run('--oem 3 --psm 1',  'method_1_document')  # default document
    run('--oem 3 --psm 6',  'method_2_block')     # single uniform block
    run('--oem 3 --psm 11', 'method_3_sparse')    # sparse text

    # Enhanced pass
    try:
        enh = enhance_for_tables(image_path)
        txt = pytesseract.image_to_string(enh, lang=lang, config='--oem 3 --psm 6 -c tessedit_create_tsv=1')
        results['method_4_enhanced'] = {
            'config': '--oem 3 --psm 6 -c tessedit_create_tsv=1',
            'text': txt.strip(),
            'char_count': len(txt.strip())
        }
        del enh
    except Exception as e:
        results['method_4_enhanced'] = {'error': str(e)}

    # Structured tokens (words/boxes)
    try:
        data_dict = pytesseract.image_to_data(img, lang=lang, config='--oem 3 --psm 6', output_type=pytesseract.Output.DICT)
        results['method_5_structured'] = {
            'config': 'structured_data', 'data': data_dict, 'word_count': len(data_dict.get('text', []))
        }
    except Exception as e:
        results['method_5_structured'] = {'error': str(e)}

    img.close()
    return results

# -------------------------------
# Step 4: Parse table-ish rows from OCR text
# -------------------------------
def parse_table_data(ocr_results):
    best_method, max_chars = None, 0
    for method_name, result in ocr_results.items():
        if isinstance(result, dict) and result.get('char_count', 0) > max_chars:
            max_chars = result['char_count']
            best_method = method_name
    if not best_method:
        return {"error": "No valid OCR results found"}

    text = ocr_results[best_method]['text']
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]

    table_data, in_table = [], False
    for line in lines:
        upper = line.upper()
        if any(k in upper for k in ['TEST', 'RESULT', 'REFERENCE', 'RANGE']):
            in_table = True
            if len(line.split()) > 2:
                table_data.append(['Header', line])
            continue
        if in_table and any(c.isdigit() for c in line):
            parts = line.split()
            if len(parts) >= 2:
                table_data.append(['Data', line])
        if 'CLINICAL' in upper or 'NOTES' in upper:
            in_table = False

    return {
        'best_method': best_method,
        'best_config': ocr_results[best_method].get('config', ''),
        'full_text': text,
        'table_data': table_data,
        'all_methods': ocr_results
    }

# -------------------------------
# Step 5: Main pipeline (page-by-page, low memory)
# -------------------------------
def enhanced_ocr_pipeline(pdf_path: str):
    print("[INFO] Converting PDF to images (disk-backed)...")
    image_paths = pdf_to_image_paths(pdf_path)

    all_results = []
    for idx, img_path in enumerate(image_paths, 1):
        print(f"[INFO] Processing {os.path.basename(img_path)} ({idx}/{len(image_paths)})...")
        try:
            ocr_results = extract_with_multiple_methods(img_path)
            parsed = parse_table_data(ocr_results)
            all_results.append({'page': img_path, 'parsed_results': parsed})
        finally:
            # Free image file ASAP to keep /tmp small
            try: os.remove(img_path)
            except: pass
            gc.collect()

    with open('enhanced_ocr_results.json', 'w', encoding='utf-8') as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False, default=str)

    print("[INFO] Enhanced results saved to 'enhanced_ocr_results.json'")
    return all_results

# -------------------------------
# Step 6: Display helper
# -------------------------------
def display_results(results):
    for i, page_result in enumerate(results, 1):
        print("\n" + "=" * 80)
        print(f"PAGE {i}: {page_result['page']}")
        print("=" * 80)
        parsed = page_result['parsed_results']
        if 'error' in parsed:
            print(f"Error: {parsed['error']}")
            continue
        print(f"Best Method: {parsed['best_method']}")
        print(f"Config Used: {parsed['best_config']}")
        print("\nFULL TEXT:\n" + "-" * 40)
        print(parsed['full_text'])
        if parsed['table_data']:
            print("\nEXTRACTED TABLE DATA:\n" + "-" * 40)
            for row_type, row_data in parsed['table_data']:
                print(f"{row_type}: {row_data}")
        print("\n" + "=" * 80)

# -------------------------------
# CLI entry
# -------------------------------
if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python ocr.py <file.pdf>")
        sys.exit(1)
    pdf_file = sys.argv[1]
    print("Starting Enhanced OCR Pipeline...")
    results = enhanced_ocr_pipeline(pdf_file)
    print("\nDisplaying Results:")
    display_results(results)
