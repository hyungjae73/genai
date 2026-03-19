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
    
    def __init__(self, language: str = 'eng+jpn'):
        """
        Initialize OCR engine with language support.
        
        Args:
            language: Language codes for OCR (e.g., 'eng+jpn' for English and Japanese)
        """
        self.language = language
    
    def extract_text(self, image_path: Path) -> OCRResult:
        """
        Extract text from an image file.
        
        Args:
            image_path: Path to PNG or PDF file
            
        Returns:
            OCRResult with extracted text and confidence scores
        """
        try:
            # Convert Path to string
            image_path_str = str(image_path)
            
            # Check file format
            if image_path.suffix.lower() == '.pdf':
                return self.extract_text_from_pdf(image_path)
            
            # Open image
            image = Image.open(image_path_str)
            
            # Extract text with detailed data
            data = pytesseract.image_to_data(
                image,
                lang=self.language,
                output_type=pytesseract.Output.DICT
            )
            
            # Extract full text
            full_text = pytesseract.image_to_string(
                image,
                lang=self.language
            )
            
            # Parse regions with confidence scores
            regions = []
            n_boxes = len(data['text'])
            
            for i in range(n_boxes):
                text = data['text'][i].strip()
                conf = float(data['conf'][i])
                
                # Skip empty text or invalid confidence
                if not text or conf < 0:
                    continue
                
                # Create region
                region = OCRRegion(
                    text=text,
                    confidence=conf / 100.0,  # Convert to 0.0-1.0 range
                    bbox=(
                        data['left'][i],
                        data['top'][i],
                        data['width'][i],
                        data['height'][i]
                    )
                )
                regions.append(region)
            
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
                error_message=None
            )
        
        except FileNotFoundError:
            return OCRResult(
                full_text="",
                regions=[],
                average_confidence=0.0,
                success=False,
                error_message=f"File not found: {image_path}"
            )
        except Exception as e:
            return OCRResult(
                full_text="",
                regions=[],
                average_confidence=0.0,
                success=False,
                error_message=f"OCR extraction failed: {str(e)}"
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
            # Convert PDF to images
            images = convert_from_path(str(pdf_path))
            
            if not images:
                return OCRResult(
                    full_text="",
                    regions=[],
                    average_confidence=0.0,
                    success=True,
                    error_message=None
                )
            
            # Extract text from each page
            all_text = []
            all_regions = []
            all_confidences = []
            
            for page_num, image in enumerate(images):
                # Extract text with detailed data
                data = pytesseract.image_to_data(
                    image,
                    lang=self.language,
                    output_type=pytesseract.Output.DICT
                )
                
                # Extract full text for this page
                page_text = pytesseract.image_to_string(
                    image,
                    lang=self.language
                )
                all_text.append(page_text.strip())
                
                # Parse regions
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
                            data['height'][i]
                        )
                    )
                    all_regions.append(region)
                    all_confidences.append(region.confidence)
            
            # Calculate average confidence
            if all_confidences:
                average_confidence = sum(all_confidences) / len(all_confidences)
            else:
                average_confidence = 0.0
            
            # Combine all page text
            full_text = "\n\n".join(all_text)
            
            return OCRResult(
                full_text=full_text,
                regions=all_regions,
                average_confidence=average_confidence,
                success=True,
                error_message=None
            )
        
        except Exception as e:
            return OCRResult(
                full_text="",
                regions=[],
                average_confidence=0.0,
                success=False,
                error_message=f"PDF OCR extraction failed: {str(e)}"
            )
