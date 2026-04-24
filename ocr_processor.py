"""
OBE Exam Sheet OCR Processor.

Strategy
--------
1. Run multi-pipeline full-image OCR to find:
   - "Maximum Marks" row → derive column x-positions.
   - "Achieved Marks" row → derive row y-center.
2. Crop each question cell individually from the "Achieved Marks" row
   and run OCR on the crop (×3 upscale) — avoids digit merging.
3. Return the achieved marks array.
   Roll number / name NOT extracted — teacher provides those.

NOTE: Images must be vertical (portrait orientation).
"""

import cv2
import numpy as np
import easyocr
import re

_reader = None


def _get_reader() -> easyocr.Reader:
    global _reader
    if _reader is None:
        _reader = easyocr.Reader(["en"], gpu=False, verbose=False)
    return _reader


# ─── Spatial helpers ──────────────────────────────────────────────────────────

def _yc(bbox) -> float:  return (bbox[0][1] + bbox[2][1]) / 2.0
def _xc(bbox) -> float:  return (bbox[0][0] + bbox[2][0]) / 2.0
def _xr(bbox) -> float:  return float(bbox[2][0])
def _xl(bbox) -> float:  return float(bbox[0][0])
def _yt(bbox) -> float:  return float(bbox[0][1])
def _yb(bbox) -> float:  return float(bbox[2][1])


# ─── Image utilities ──────────────────────────────────────────────────────────

def _upscale(img: np.ndarray, target: int = 2000) -> np.ndarray:
    h, w = img.shape[:2]
    if max(h, w) < target:
        scale = target / max(h, w)
        img   = cv2.resize(img, None, fx=scale, fy=scale,
                           interpolation=cv2.INTER_CUBIC)
    return img


def _to_gray(img: np.ndarray) -> np.ndarray:
    if len(img.shape) == 3:
        return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return img




# ─── Preprocessing pipelines ──────────────────────────────────────────────────

def _pipeline_raw(img: np.ndarray) -> np.ndarray:
    return _upscale(img.copy())


def _pipeline_gray(img: np.ndarray) -> np.ndarray:
    return _to_gray(_upscale(img.copy()))


def _pipeline_clahe(img: np.ndarray) -> np.ndarray:
    g     = _to_gray(_upscale(img.copy()))
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    return clahe.apply(g)


def _pipeline_thresh(img: np.ndarray) -> np.ndarray:
    g = _to_gray(_upscale(img.copy()))
    return cv2.adaptiveThreshold(
        g, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY, blockSize=31, C=11
    )


PIPELINES = [
    ("raw",    _pipeline_raw),
    ("gray",   _pipeline_gray),
    ("clahe",  _pipeline_clahe),
    ("thresh", _pipeline_thresh),
]


# ─── EasyOCR call helper ──────────────────────────────────────────────────────

def _ocr(reader, img, text_threshold=0.4, low_text=0.3, link_threshold=0.3):
    return reader.readtext(
        img, detail=1, paragraph=False,
        text_threshold=text_threshold,
        low_text=low_text,
        link_threshold=link_threshold,
    )


# ─── Full-image OCR (multi-pipeline) ─────────────────────────────────────────

def _score_mc(results: list) -> int:
    return sum(1 for _, text, _ in results if len(text.strip()) >= 3)


def _run_best_pipeline(oriented_img: np.ndarray) -> tuple:
    """
    Run 4 preprocessing pipelines.
    Returns (best_results, best_pipeline_img).
    """
    reader       = _get_reader()
    best_results = []
    best_img     = None
    best_score   = -1

    for name, fn in PIPELINES:
        try:
            processed = fn(oriented_img)
            results   = _ocr(reader, processed)
            score     = _score_mc(results)
            if score > best_score:
                best_score   = score
                best_results = results
                best_img     = processed
        except Exception:
            pass

    return best_results, best_img


# ─── Column position detection ────────────────────────────────────────────────

def _find_column_positions(results: list, setup_questions: list) -> list:
    """
    Derive x-centers of each question column from the "Maximum Marks" row,
    matching detected values against expected max marks from setup.

    Falls back to "Question" number row (1, 2, 3, …, N).
    Returns a sorted list of x-centers (one per question, in question order).
    """
    num_q    = len(setup_questions)
    max_vals = [float(q["maxMarks"]) for q in setup_questions]

    # ── Strategy 1: Maximum Marks row ────────────────────────────────────────
    label_bbox = None
    for bbox, text, _ in results:
        if re.search(r'max(imum)?\s*(mark)?', text, re.IGNORECASE):
            label_bbox = bbox
            break

    if label_bbox is not None:
        lbl_y  = _yc(label_bbox)
        lbl_xr = _xr(label_bbox)
        candidates = []
        for bbox, text, conf in results:
            if abs(_yc(bbox) - lbl_y) <= 120 and _xc(bbox) > lbl_xr:
                for num in re.findall(r'\d+(?:\.\d+)?', text):
                    candidates.append((_xc(bbox), float(num), conf))

        candidates.sort(key=lambda c: c[0])
        if candidates:
            matched_x = _match_columns_to_values(candidates, max_vals)
            if matched_x:
                return matched_x

    # ── Strategy 2: Question number row (1, 2, 3, …) ─────────────────────────
    for bbox, text, _ in results:
        if re.search(r'^question', text, re.IGNORECASE):
            lbl_y  = _yc(bbox)
            lbl_xr = _xr(bbox)
            nums   = [
                (_xc(b), float(t.strip()), c)
                for b, t, c in results
                if abs(_yc(b) - lbl_y) <= 60 and _xc(b) > lbl_xr
                and re.match(r'^\d+$', t.strip())
                and 1 <= int(t.strip()) <= num_q
            ]
            nums.sort(key=lambda x: x[1])
            if len(nums) == num_q:
                return [x for x, _, _ in nums]

    return []


def _match_columns_to_values(candidates, target_vals):
    """
    Greedily match left-to-right candidates to target_vals.
    Returns x-positions in question order if match succeeds, else [].
    """
    if len(candidates) < len(target_vals):
        return []

    # Try sequential matching: first N candidates that match target values
    result = []
    ci     = 0
    for target in target_vals:
        while ci < len(candidates) and abs(candidates[ci][1] - target) > 0.5:
            ci += 1
        if ci >= len(candidates):
            return []
        result.append(candidates[ci][0])
        ci += 1

    return result


# ─── Achieved marks row y ────────────────────────────────────────────────────

def _find_marks_label_y(results: list, after_y: float) -> float:
    """Find the y of the 'Marks' label that appears below 'Achieved'."""
    for bbox, text, _ in sorted(results, key=lambda r: _yc(r[0])):
        ym = _yc(bbox)
        if ym > after_y + 30 and re.search(r'^marks?$', text.strip(), re.IGNORECASE):
            return ym
    return -1.0


def _find_achieved_row_y(results: list) -> float:
    """
    Find the y-center of the "Achieved Marks" row.
    The label is two lines: "Achieved" (y1) and "Marks" (y2).
    Returns y1 so the crop lands on the handwritten digits.
    """
    achieved_y = -1.0

    for bbox, text, _ in sorted(results, key=lambda r: _yc(r[0])):
        if re.search(r'achiev|obtain', text, re.IGNORECASE) and achieved_y < 0:
            achieved_y = _yc(bbox)
            break

    return achieved_y


# ─── Cell-by-cell crop OCR ────────────────────────────────────────────────────

def _crop_cell_ocr(pipeline_img: np.ndarray, cx: float,
                   y1_abs: float, y2_abs: float,
                   half_w: float, cell_idx: int) -> tuple:
    """
    Crop a single cell from pipeline_img using absolute y bounds, upscale ×3, and run OCR.
    Returns (best_value, confidence).
    """
    h, w = pipeline_img.shape[:2]

    x1 = max(0, int(cx - half_w))
    x2 = min(w, int(cx + half_w))
    y1 = max(0, int(y1_abs))
    y2 = min(h, int(y2_abs))

    crop = pipeline_img[y1:y2, x1:x2]
    if crop.size == 0:
        return 0.0, 0.0

    # Upscale 3× for better single-digit OCR
    big = cv2.resize(crop, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)

    # Trim 9% top+bottom from color image too (removes table border lines)
    h_b   = big.shape[0]
    trim  = max(1, int(h_b * 0.09))
    big_t = big[trim:h_b - trim, :]

    # Grayscale + Otsu threshold (removes colour but keeps ink edges)
    if len(big_t.shape) == 3:
        gray = cv2.cvtColor(big_t, cv2.COLOR_BGR2GRAY)
    else:
        gray = big_t.copy()
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    # Red-channel isolation: highlights red pen ink while suppressing black table lines
    if len(big.shape) == 3:
        b, g, r = cv2.split(big)
        # "Redness" = how much more red the pixel is than the other channels
        redness   = cv2.subtract(r, cv2.max(b, g))
        _, red_mask = cv2.threshold(redness, 25, 255, cv2.THRESH_BINARY)
        red_inv   = cv2.bitwise_not(red_mask)        # black digit on white
        # Add white padding so EasyOCR has context around the digit
        pad     = 40
        red_pad = cv2.copyMakeBorder(red_inv, pad, pad, pad, pad,
                                     cv2.BORDER_CONSTANT, value=255)
    else:
        red_pad = thresh.copy()

    reader = _get_reader()
    best_v = 0.0
    best_c = 0.0

    # Try each image variant; use allowlist='0123456789' to prevent
    # EasyOCR from returning letters (e.g. "B" for "8", "S" for "5").
    for img_variant in [thresh, red_pad, big_t]:
        try:
            results = reader.readtext(
                img_variant, detail=1, paragraph=False,
                text_threshold=0.2, low_text=0.15, link_threshold=0.2,
                allowlist='0123456789',
            )
        except Exception:
            results = _ocr(reader, img_variant, text_threshold=0.2,
                           low_text=0.15, link_threshold=0.2)

        for _, text, conf in results:
            nums = re.findall(r'\d+(?:\.\d+)?', text.strip())
            if nums:
                val = float(nums[0])
                if conf > best_c:
                    best_c = conf
                    best_v = val

    return best_v, round(best_c * 100, 1)


# ─── Public entry point ────────────────────────────────────────────────────────

def process_image(image_path: str, setup: dict) -> dict:
    """
    Extract achieved marks from one OBE exam sheet image.
    Returns: { marks: [{questionNo, clo, maxMarks, obtained, confidence}, …] }
    Image must be in portrait (vertical) orientation.
    """
    questions     = setup.get("questions", [])
    num_questions = len(questions)

    # ── Load image ────────────────────────────────────────────────────────────
    oriented = cv2.imread(image_path)
    if oriented is None:
        raise ValueError(f"Cannot read image: {image_path}")

    # ── Full-image OCR (best pipeline) ────────────────────────────────────────
    full_results, pipeline_img = _run_best_pipeline(oriented)

    # ── Find column positions ─────────────────────────────────────────────────
    col_x = _find_column_positions(full_results, questions)

    # ── Find achieved row y ───────────────────────────────────────────────────
    achieved_y = _find_achieved_row_y(full_results)

    # ── Extract marks ─────────────────────────────────────────────────────────
    marks = []

    if col_x and achieved_y > 0 and pipeline_img is not None:
        if len(col_x) > 1:
            min_gap = min(col_x[i+1] - col_x[i] for i in range(len(col_x)-1))
            half_w  = min_gap * 0.45
        else:
            half_w = 120

        marks_y = _find_marks_label_y(full_results, achieved_y)
        crop_y1 = achieved_y - 120
        crop_y2 = (marks_y + 80) if marks_y > 0 else (achieved_y + 180)

        for idx, q in enumerate(questions):
            q_max = float(q.get("maxMarks", 0))
            if idx < len(col_x):
                val, conf = _crop_cell_ocr(pipeline_img, col_x[idx],
                                           crop_y1, crop_y2, half_w, idx)
                if q_max > 0 and val > q_max:
                    val, conf = q_max, 25.0
            else:
                val, conf = 0.0, 0.0

            marks.append({
                "questionNo": int(q.get("no", idx + 1)),
                "clo":        int(q.get("clo", 1)),
                "maxMarks":   q_max,
                "obtained":   val,
                "confidence": conf,
            })

    else:
        # Fallback: full-row extraction (less accurate)
        achieved = _find_row_values(full_results,
                                    [r'achiev', r'obtain'],
                                    y_tolerance=55,
                                    max_values=num_questions)
        for idx, q in enumerate(questions):
            q_max    = float(q.get("maxMarks", 0))
            obtained = achieved[idx]["value"]      if idx < len(achieved) else 0.0
            conf     = achieved[idx]["confidence"] if idx < len(achieved) else 0.0
            if q_max > 0 and obtained > q_max:
                obtained, conf = q_max, 25.0
            marks.append({
                "questionNo": int(q.get("no", idx + 1)),
                "clo":        int(q.get("clo", 1)),
                "maxMarks":   q_max,
                "obtained":   obtained,
                "confidence": conf,
            })

    return {"marks": marks}


# ─── Fallback row extraction ──────────────────────────────────────────────────

def _find_row_values(results, keyword_patterns, y_tolerance=50, max_values=None):
    label_item = None
    for bbox, text, conf in results:
        for pat in keyword_patterns:
            if re.search(pat, text, re.IGNORECASE):
                label_item = (bbox, text, conf)
                break
        if label_item:
            break

    if label_item is None:
        return []

    label_bbox, _, _ = label_item
    label_y  = _yc(label_bbox)
    label_xr = _xr(label_bbox)

    items = []
    for bbox, text, conf in results:
        cy = _yc(bbox)
        cx = _xc(bbox)
        if abs(cy - label_y) <= y_tolerance and cx > label_xr:
            for num in re.findall(r'\d+(?:\.\d+)?', text):
                items.append({"value": float(num), "confidence": round(conf * 100, 1), "x": cx})

    items.sort(key=lambda i: i["x"])
    if items and len(items) > 1:
        items = items[:-1]   # drop rightmost (usually a totals column)
    if max_values is not None:
        items = items[:max_values]
    return items
