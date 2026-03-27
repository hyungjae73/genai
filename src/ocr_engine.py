"""
OCR Engine for Payment Compliance Monitor.

This module extracts text from screenshot images using Tesseract OCR.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import pytesseract
from PIL import Image
from pdf2image import convert_from_path


@dataclass
class OCRRegion:
    """Represents a region of extracted text."""
    text: str
    confidence: float  # 0.0 to 1.0
    bbox: tuple[int, int, int, int]  # (x, y, width, height)


@dataclass
class OCRResult:
    """Result of OCR extraction."""
    full_text: str
    regions: list[OCRRegion]
    average_confidence: float
    success: bool
    error_message: Optional[str] = None



class OCREngine:
    """Extracts text from images using Tesseract OCR."""

    # Minimum DPI for reliable OCR output
    TARGET_DPI = 300
    # Regions below this confidence (0-100) are excluded from full_text
    MIN_REGION_CONFIDENCE = 30

    def __init__(self, language: str = 'eng+jpn'):
        """
        Initialize OCR engine with language support.

        Args:
            language: Language codes for OCR (e.g., 'eng+jpn' for English and Japanese)
        """
        self.language = language
        # Tesseract config: assume a uniform block of text, use LSTM engine
        self._tesseract_config = '--psm 6 --oem 1'

    # ------------------------------------------------------------------
    # Image preprocessing
    # ------------------------------------------------------------------

    @staticmethod
    def _preprocess_image(image: Image.Image) -> Image.Image:
        """
        Apply preprocessing steps to improve OCR accuracy.

        Steps:
        1. Convert to grayscale
        2. Up-scale small images to >= TARGET_DPI equivalent
        3. Sharpen to recover detail
        4. Adaptive thresholding (binarisation)
        """
        from PIL import ImageFilter

        # 1. Grayscale
        gray = image.convert('L')

        # 2. Up-scale if the image is small (heuristic: width < 1500px)
        if gray.width < 1500:
            scale = max(2, OCREngine.TARGET_DPI // 72)  # assume 72 dpi source
            gray = gray.resize(
                (gray.width * scale, gray.height * scale),
                Image.LANCZOS,
            )

        # 3. Sharpen
        gray = gray.filter(ImageFilter.SHARPEN)

        # 4. Adaptive thresholding via Pillow (simple binarisation)
        #    Use a threshold at the median pixel value for adaptive-like behaviour
        import numpy as np
        arr = np.array(gray)
        threshold = int(np.median(arr))
        binary = gray.point(lambda p: 255 if p > threshold else 0)

        return binary

    # ------------------------------------------------------------------
    # Core extraction
    # ------------------------------------------------------------------

    def extract_text(self, image_path: Path) -> OCRResult:
        """
        Extract text from an image file.

        Args:
            image_path: Path to PNG or PDF file

        Returns:
            OCRResult with extracted text and confidence scores
        """
        try:
            image_path_str = str(image_path)

            if image_path.suffix.lower() == '.pdf':
                return self.extract_text_from_pdf(image_path)

            image = Image.open(image_path_str)

            # Preprocess for better OCR accuracy
            processed = self._preprocess_image(image)

            # Extract text with detailed data
            data = pytesseract.image_to_data(
                processed,
                lang=self.language,
                config=self._tesseract_config,
                output_type=pytesseract.Output.DICT,
            )

            # Parse regions with confidence scores
            regions = []
            n_boxes = len(data['text'])

            for i in range(n_boxes):
                text = data['text'][i].strip()
                conf = float(data['conf'][i])

                if not text or conf < 0:
                    continue

                region = OCRRegion(
                    text=text,
                    confidence=conf / 100.0,
                    bbox=(
                        data['left'][i],
                        data['top'][i],
                        data['width'][i],
                        data['height'][i],
                    ),
                )
                regions.append(region)

            # Build full_text only from regions above the confidence threshold
            high_conf_regions = [
                r for r in regions
                if r.confidence >= self.MIN_REGION_CONFIDENCE / 100.0
            ]
            full_text = ' '.join(r.text for r in high_conf_regions)

            # Calculate average confidence
            if regions:
                average_confidence = sum(r.confidence for r in regions) / len(regions)
            else:
                average_confidence = 0.0

            return OCRResult(
                full_text=full_text.strip(),
                regions=regions,
                average_confidence=average_confidence,
                success=True,
                error_message=None,
            )

        except FileNotFoundError:
            return OCRResult(
                full_text="",
                regions=[],
                average_confidence=0.0,
                success=False,
                error_message=f"File not found: {image_path}",
            )
        except Exception as e:
            return OCRResult(
                full_text="",
                regions=[],
                average_confidence=0.0,
                success=False,
                error_message=f"OCR extraction failed: {str(e)}",
            )

    def extract_text_from_pdf(self, pdf_path: Path) -> OCRResult:
        """
        Extract text from PDF by converting to images first.

        Args:
            pdf_path: Path to PDF file

        Returns:
            OCRResult with extracted text from all pages
        """
        try:
            images = convert_from_path(str(pdf_path), dpi=self.TARGET_DPI)

            if not images:
                return OCRResult(
                    full_text="",
                    regions=[],
                    average_confidence=0.0,
                    success=True,
                    error_message=None,
                )

            all_text = []
            all_regions = []
            all_confidences = []

            for page_num, image in enumerate(images):
                processed = self._preprocess_image(image)

                data = pytesseract.image_to_data(
                    processed,
                    lang=self.language,
                    config=self._tesseract_config,
                    output_type=pytesseract.Output.DICT,
                )

                n_boxes = len(data['text'])
                page_regions = []
                for i in range(n_boxes):
                    text = data['text'][i].strip()
                    conf = float(data['conf'][i])

                    if not text or conf < 0:
                        continue

                    region = OCRRegion(
                        text=text,
                        confidence=conf / 100.0,
                        bbox=(
                            data['left'][i],
                            data['top'][i],
                            data['width'][i],
                            data['height'][i],
                        ),
                    )
                    page_regions.append(region)
                    all_confidences.append(region.confidence)

                all_regions.extend(page_regions)

                # Build page text from high-confidence regions only
                high_conf = [
                    r for r in page_regions
                    if r.confidence >= self.MIN_REGION_CONFIDENCE / 100.0
                ]
                all_text.append(' '.join(r.text for r in high_conf))

            if all_confidences:
                average_confidence = sum(all_confidences) / len(all_confidences)
            else:
                average_confidence = 0.0

            full_text = "\n\n".join(all_text)

            return OCRResult(
                full_text=full_text,
                regions=all_regions,
                average_confidence=average_confidence,
                success=True,
                error_message=None,
            )

        except Exception as e:
            return OCRResult(
                full_text="",
                regions=[],
                average_confidence=0.0,
                success=False,
                error_message=f"PDF OCR extraction failed: {str(e)}",
            )

