"""
ocr.py
------
OCR for scanning giveaway codes from image attachments.

Engine priority:
  1. Gemini Vision (most accurate — used when GEMINI_API_KEY is set)
  2. Tesseract (works on macOS / Linux / Android-Termux, no API key needed)
  3. macOS Vision (fallback when tesseract is absent)
"""

import asyncio
import base64
import logging
import os
import re
import shutil
import ssl
import subprocess
import tempfile
from pathlib import Path

import aiohttp
from PIL import Image

import config

# macOS Python SSL cert bug workaround (same as main.py / claimer.py)
ssl._create_default_https_context = ssl._create_unverified_context

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")
logger = logging.getLogger("LucidOCR")

_SWIFT_SOURCE = r'''
import Foundation
import Vision
import AppKit

guard CommandLine.arguments.count > 1 else { exit(2) }
let path = CommandLine.arguments[1]
let imgURL = URL(fileURLWithPath: path)
guard let img = NSImage(contentsOf: imgURL),
      let cgImg = img.cgImage(forProposedRect: nil, context: nil, hints: nil) else {
    exit(1)
}

let request = VNRecognizeTextRequest()
request.recognitionLevel = .accurate
request.usesLanguageCorrection = false
request.recognitionLanguages = ["en-US"]

let handler = VNImageRequestHandler(cgImage: cgImg, options: [:])
try? handler.perform([request])
if let observations = request.results as? [VNRecognizedTextObservation] {
    for obs in observations {
        if let candidate = obs.topCandidates(1).first {
            print(candidate.string)
        }
    }
}
'''

_BINARY_PATH = os.path.join(tempfile.gettempdir(), "lucid_ocr_bin")
_SWIFT_PATH = os.path.join(tempfile.gettempdir(), "lucid_ocr.swift")

_TESS_BINARY = "tesseract"
_TARGET_TEXT_HEIGHT = 45.0  # px: tesseract reads best around here
_PADDING = 12


def _tesseract_available() -> bool:
    return shutil.which(_TESS_BINARY) is not None


def _run(cmd: list, timeout: int = 60) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def _ocr_with_tesseract(image_path: str) -> str:
    """OCR an image using tesseract, first cropping to the code region for accuracy."""
    if not _tesseract_available():
        return ""

    img = Image.open(image_path).convert("L")
    full_text = _tesseract_full(img)

    # If codes are already readable, skip region logic
    if re.search(r'\b(?:LUCID|LBOX)-', full_text, re.IGNORECASE):
        return full_text

    # Find code region bounding box from tesseract TSV output
    region = _find_code_region(img)
    if region:
        left, top, right, bottom, avg_height = region
        pad = _PADDING
        left = max(0, left - pad)
        top = max(0, top - pad)
        right = min(img.width, right + pad)
        bottom = min(img.height, bottom + pad)
        crop = img.crop((left, top, right, bottom))

        scale = max(1.0, _TARGET_TEXT_HEIGHT / max(avg_height, 1))
        if scale > 1.0:
            crop = crop.resize(
                (int(crop.width * scale), int(crop.height * scale)),
                Image.LANCZOS,
            )

        tmp_path = os.path.join(tempfile.gettempdir(), "lucid_ocr_region.png")
        crop.save(tmp_path)
        return _tesseract_full(crop, path=tmp_path)

    return full_text


def _tesseract_full(image: Image.Image, path: str = None, psm: str = "3") -> str:
    """Run tesseract on a PIL image (saved to temp) and return stdout text."""
    if path is None:
        path = os.path.join(tempfile.gettempdir(), "lucid_ocr_tmp.png")
        image.save(path)
    try:
        result = _run([_TESS_BINARY, path, "stdout", "--psm", psm])
        return result.stdout
    except Exception as e:
        logger.error(f"⚠️ Tesseract failed: {e}")
        return ""


def _find_code_region(img: Image.Image):
    """Use tesseract TSV (psm 11) to locate lines containing LUCID- / LBOX- codes."""
    path = os.path.join(tempfile.gettempdir(), "lucid_ocr_tsv.png")
    img.save(path)
    try:
        result = _run([_TESS_BINARY, path, "stdout", "--psm", "11", "tsv"])
    except Exception as e:
        logger.error(f"⚠️ Tesseract TSV failed: {e}")
        return None

    boxes = []
    for line in result.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) < 12:
            continue
        text = parts[11].strip().upper()
        if "LUCID" in text or "LBOX" in text:
            try:
                left, top, width, height = (
                    int(parts[6]), int(parts[7]), int(parts[8]), int(parts[9]),
                )
                boxes.append((left, top, width, height))
            except ValueError:
                continue

    if not boxes:
        return None

    left = min(b[0] for b in boxes)
    top = min(b[1] for b in boxes)
    right = max(b[0] + b[2] for b in boxes)
    bottom = max(b[1] + b[3] for b in boxes)
    avg_height = sum(b[3] for b in boxes) / len(boxes)
    return left, top, right, bottom, avg_height


# ---------------------------------------------------------------------------
# macOS Vision fallback
# ---------------------------------------------------------------------------

def _ensure_vision_binary() -> str:
    if os.path.exists(_BINARY_PATH):
        return _BINARY_PATH

    with open(_SWIFT_PATH, "w") as f:
        f.write(_SWIFT_SOURCE)

    logger.info("Compiling OCR helper binary...")
    result = subprocess.run(
        ["swiftc", _SWIFT_PATH, "-o", _BINARY_PATH],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Failed to compile OCR helper: {result.stderr}")
    logger.info("OCR helper binary ready.")
    return _BINARY_PATH


async def _ocr_with_vision(image_path: str) -> str:
    binary = _ensure_vision_binary()
    try:
        proc = await asyncio.create_subprocess_exec(
            binary, image_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            logger.error(f"⚠️ Vision OCR failed (exit {proc.returncode}): {stderr.decode(errors='replace').strip()}")
            return ""
        return stdout.decode(errors="replace")
    except Exception as e:
        logger.error(f"⚠️ Vision OCR exception: {e}")
        return ""


# ---------------------------------------------------------------------------
# Gemini Vision (most accurate — used when GEMINI_API_KEY is configured)
# ---------------------------------------------------------------------------

_PROMPT = (
    "This image contains a list of giveaway redemption codes for lucidtrading.com. "
    "Extract EVERY code verbatim, exactly as written. Codes start with 'LUCID-' or "
    "LBOX-' followed by uppercase letters and digits. Do NOT correct, guess, or "
    "invent any characters — transcribe each code character-for-character. "
    "Output one code per line, nothing else."
)


def _has_gemini() -> bool:
    return bool(config.GEMINI_API_KEY)


async def _ocr_with_gemini(image_path: str) -> str:
    """Send the image to Gemini Vision and return the raw extracted text."""
    if not _has_gemini():
        return ""

    try:
        with open(image_path, "rb") as f:
            data = f.read()
    except Exception as e:
        logger.error(f"⚠️ Gemini: cannot read image: {e}")
        return ""

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{config.GEMINI_MODEL}:generateContent"
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": _PROMPT},
                    {
                        "inline_data": {
                            "mime_type": "image/png" if image_path.lower().endswith(".png") else "image/jpeg",
                            "data": base64.b64encode(data).decode("ascii"),
                        }
                    },
                ]
            }
        ],
        "generationConfig": {"temperature": 0, "maxOutputTokens": 4096},
    }
    headers = {"Content-Type": "application/json"}

    try:
        connector = aiohttp.TCPConnector(ssl=False)
        async with aiohttp.ClientSession(connector=connector) as session:
            async with session.post(
                url, json=payload, headers=headers,
                params={"key": config.GEMINI_API_KEY},
                timeout=aiohttp.ClientTimeout(total=60),
            ) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    logger.error(f"⚠️ Gemini API error (HTTP {resp.status}): {body[:300]}")
                    return ""
                result = await resp.json()
    except Exception as e:
        logger.error(f"⚠️ Gemini OCR exception: {e}")
        return ""

    try:
        parts = result["candidates"][0]["content"]["parts"]
        return "\n".join(p.get("text", "") for p in parts)
    except (KeyError, IndexError) as e:
        logger.error(f"⚠️ Gemini: unexpected response format: {e}")
        return ""


async def ocr_image(image_path: str) -> str:
    """
    Runs OCR on the given image file and returns all detected text lines
    joined by newlines. Returns "" on failure.

    Engine priority: Gemini Vision (if API key set) > Tesseract > macOS Vision.
    """
    if _has_gemini():
        text = await _ocr_with_gemini(image_path)
        if text:
            return text
        logger.info("⚠️ Gemini returned nothing, falling back to local OCR.")

    engine = "tesseract" if _tesseract_available() else "vision"
    try:
        if engine == "tesseract":
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, _ocr_with_tesseract, image_path)
        return await _ocr_with_vision(image_path)
    except Exception as e:
        logger.error(f"⚠️ OCR exception ({engine}): {e}")
        return ""