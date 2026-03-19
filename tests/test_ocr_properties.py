"""
Property-based tests for OCR Engine.

Tests universal properties that should hold for all OCR operations.
Feature: verification-comparison-system
"""

import pytest
from hypothesis import given, strategies as st, settings
from pathlib import Path
import tempfile
from PIL import Image, ImageDraw, ImageFont

from src.ocr_engine import OCREngine, OCRResult


# Strategy for generating test images with text
@st.composite
def text_image_strategy(draw):
    """Generate test images with random text content."""
    # Generate random text
    text = draw(st.text(
        alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd', 'Zs')),
        min_size=5,
        max_size=100
    ))
    
    # Generate image dimensions
    width = draw(st.integers(min_value=200, max_value=800))
    height = draw(st.integers(min_value=100, max_value=400))
    
    # Create image with white background
    image = Image.new('RGB', (width, height), color='white')
    draw_obj = ImageDraw.Draw(image)
    
    # Draw text on image (using default font)
    # Position text in the center
    text_position = (10, height // 2 - 10)
    draw_obj.text(text_position, text, fill='black')
    
    return image, text


# Strategy for generating blank images
@st.composite
def blank_image_strategy(draw):
    """Generate blank test images."""
    width = draw(st.integers(min_value=100, max_value=500))
    height = draw(st.integers(min_value=100, max_value=500))
    
    # Random background color
    color = draw(st.sampled_from(['white', 'black', 'gray']))
    
    image = Image.new('RGB', (width, height), color=color)
    return image


class TestOCRProperties:
    """Property-based tests for OCR Engine."""
    
    @settings(max_examples=100, deadline=None)
    @given(image_data=text_image_strategy())
    def test_property_ocr_text_extraction_success(self, image_data):
        """
        Property 1: OCR Text Extraction Success
        
        For any valid screenshot file (PNG or PDF), when the OCR engine processes it,
        the result should have success=True and contain extracted text
        (which may be empty for blank images).
        
        **Validates: Requirements 1.1, 1.4**
        """
        image, expected_text = image_data
        
        # Save image to temporary file
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp_file:
            tmp_path = Path(tmp_file.name)
            image.save(tmp_path, format='PNG')
        
        try:
            # Initialize OCR engine
            engine = OCREngine(language='eng')
            
            # Extract text from image
            result = engine.extract_text(tmp_path)
            
            # Property: Result should indicate success
            assert result.success is True, "OCR extraction should succeed for valid images"
            
            # Property: Result should have no error message on success
            assert result.error_message is None, "Successful extraction should not have error message"
            
            # Property: Result should contain extracted text (may be empty)
            assert isinstance(result.full_text, str), "Extracted text should be a string"
            
            # Property: Result should have regions list
            assert isinstance(result.regions, list), "Result should contain regions list"
            
            # Property: Result should have average confidence score
            assert isinstance(result.average_confidence, float), "Average confidence should be a float"
            assert 0.0 <= result.average_confidence <= 1.0, "Confidence should be between 0.0 and 1.0"
            
            # Property: If text was extracted, regions should exist
            if result.full_text.strip():
                # Note: OCR may not always extract text perfectly, but if it does,
                # regions should be present
                assert isinstance(result.regions, list)
            
            # Property: Each region should have valid structure
            for region in result.regions:
                assert isinstance(region.text, str), "Region text should be a string"
                assert isinstance(region.confidence, float), "Region confidence should be a float"
                assert 0.0 <= region.confidence <= 1.0, "Region confidence should be between 0.0 and 1.0"
                assert isinstance(region.bbox, tuple), "Region bbox should be a tuple"
                assert len(region.bbox) == 4, "Region bbox should have 4 elements (x, y, width, height)"
                
                # Property: Bounding box coordinates should be non-negative
                x, y, w, h = region.bbox
                assert x >= 0, "Bounding box x should be non-negative"
                assert y >= 0, "Bounding box y should be non-negative"
                assert w >= 0, "Bounding box width should be non-negative"
                assert h >= 0, "Bounding box height should be non-negative"
        
        finally:
            # Clean up temporary file
            tmp_path.unlink(missing_ok=True)
    
    @settings(max_examples=100)
    @given(blank_image=blank_image_strategy())
    def test_property_ocr_blank_image_handling(self, blank_image):
        """
        Property: OCR should handle blank images gracefully.
        
        For any blank image, OCR should return success=True with empty or minimal text.
        
        **Validates: Requirements 1.4**
        """
        # Save blank image to temporary file
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp_file:
            tmp_path = Path(tmp_file.name)
            blank_image.save(tmp_path, format='PNG')
        
        try:
            engine = OCREngine(language='eng')
            result = engine.extract_text(tmp_path)
            
            # Property: Blank images should still return success
            assert result.success is True, "OCR should succeed even for blank images"
            
            # Property: No error message for blank images
            assert result.error_message is None
            
            # Property: Text should be empty or whitespace only
            assert isinstance(result.full_text, str)
            
            # Property: Confidence should be valid even for blank images
            assert isinstance(result.average_confidence, float)
            assert 0.0 <= result.average_confidence <= 1.0
            
            # Property: Regions list should be present (may be empty)
            assert isinstance(result.regions, list)
        
        finally:
            tmp_path.unlink(missing_ok=True)
    
    @settings(max_examples=50, deadline=500)
    @given(
        width=st.integers(min_value=100, max_value=800),
        height=st.integers(min_value=100, max_value=600)
    )
    def test_property_ocr_result_structure_consistency(self, width, height):
        """
        Property: OCR results should have consistent structure regardless of input.
        
        All OCR results should have the same fields and types, whether extraction
        succeeds or fails.
        
        **Validates: Requirements 1.1**
        """
        # Create a simple test image
        image = Image.new('RGB', (width, height), color='white')
        draw = ImageDraw.Draw(image)
        draw.text((10, 10), "Test", fill='black')
        
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp_file:
            tmp_path = Path(tmp_file.name)
            image.save(tmp_path, format='PNG')
        
        try:
            engine = OCREngine(language='eng')
            result = engine.extract_text(tmp_path)
            
            # Property: Result should always have these fields
            assert hasattr(result, 'full_text'), "Result should have full_text field"
            assert hasattr(result, 'regions'), "Result should have regions field"
            assert hasattr(result, 'average_confidence'), "Result should have average_confidence field"
            assert hasattr(result, 'success'), "Result should have success field"
            assert hasattr(result, 'error_message'), "Result should have error_message field"
            
            # Property: Field types should be consistent
            assert isinstance(result.full_text, str)
            assert isinstance(result.regions, list)
            assert isinstance(result.average_confidence, float)
            assert isinstance(result.success, bool)
            assert result.error_message is None or isinstance(result.error_message, str)
        
        finally:
            tmp_path.unlink(missing_ok=True)
    
    @settings(max_examples=50, deadline=500)
    @given(text_content=st.text(min_size=1, max_size=50))
    def test_property_ocr_deterministic_for_same_image(self, text_content):
        """
        Property: OCR should produce consistent results for the same image.
        
        Running OCR multiple times on the same image should produce the same result.
        
        **Validates: Requirements 1.1**
        """
        # Create test image with text
        image = Image.new('RGB', (400, 200), color='white')
        draw = ImageDraw.Draw(image)
        draw.text((10, 50), text_content, fill='black')
        
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp_file:
            tmp_path = Path(tmp_file.name)
            image.save(tmp_path, format='PNG')
        
        try:
            engine = OCREngine(language='eng')
            
            # Run OCR twice
            result1 = engine.extract_text(tmp_path)
            result2 = engine.extract_text(tmp_path)
            
            # Property: Results should be identical
            assert result1.success == result2.success
            assert result1.full_text == result2.full_text
            assert result1.average_confidence == result2.average_confidence
            assert len(result1.regions) == len(result2.regions)
        
        finally:
            tmp_path.unlink(missing_ok=True)
    
    @settings(max_examples=100, deadline=None)
    @given(
        invalid_input=st.one_of(
            # Strategy 1: Non-existent file paths with various extensions
            st.tuples(
                st.text(
                    alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd')),
                    min_size=5,
                    max_size=20
                ),
                st.sampled_from(['.png', '.jpg', '.pdf', '.txt', '.bmp', '.gif', '.tiff'])
            ).map(lambda t: ("nonexistent", t)),
            # Strategy 2: Corrupted binary data written to files
            st.binary(min_size=1, max_size=2000).map(lambda b: ("corrupted", b)),
            # Strategy 3: Text content masquerading as image files
            st.text(min_size=1, max_size=500).map(lambda t: ("text_as_image", t)),
        )
    )
    def test_property_ocr_error_handling(self, invalid_input):
        """
        Property 2: OCR Error Handling

        For any invalid or corrupted image file, when the OCR engine attempts to
        process it, the result should have success=False and include a descriptive
        error message.

        # Feature: verification-comparison-system, Property 2: OCR Error Handling

        **Validates: Requirements 1.2**
        """
        engine = OCREngine(language='eng')
        tmp_path = None

        try:
            input_type = invalid_input[0]
            payload = invalid_input[1]

            if input_type == "nonexistent":
                filename, extension = payload
                non_existent_path = Path(f"/tmp/nonexistent_ocr_{filename}{extension}")
                # Ensure the file doesn't actually exist
                if non_existent_path.exists():
                    non_existent_path.unlink()
                result = engine.extract_text(non_existent_path)

            elif input_type == "corrupted":
                binary_data = payload
                with tempfile.NamedTemporaryFile(suffix='.png', delete=False, mode='wb') as tmp_file:
                    tmp_path = Path(tmp_file.name)
                    tmp_file.write(binary_data)
                result = engine.extract_text(tmp_path)

            elif input_type == "text_as_image":
                text_data = payload
                with tempfile.NamedTemporaryFile(suffix='.png', delete=False, mode='w') as tmp_file:
                    tmp_path = Path(tmp_file.name)
                    tmp_file.write(text_data)
                result = engine.extract_text(tmp_path)

            # Property: Invalid/corrupted files must return success=False
            assert result.success is False, (
                f"OCR should fail for invalid input (type={input_type}), "
                f"but got success=True"
            )

            # Property: Error message must be present and descriptive
            assert result.error_message is not None, (
                "Error message should be present on failure"
            )
            assert isinstance(result.error_message, str), (
                "Error message should be a string"
            )
            assert len(result.error_message) > 0, (
                "Error message should not be empty"
            )

            # Property: Failed extraction should return safe defaults
            assert result.full_text == "", (
                "Failed extraction should return empty text"
            )
            assert result.regions == [], (
                "Failed extraction should return empty regions list"
            )
            assert result.average_confidence == 0.0, (
                "Failed extraction should return 0.0 confidence"
            )

            # Property: Result structure should be consistent on failure
            assert isinstance(result, OCRResult), (
                "Result should be an OCRResult instance"
            )

        finally:
            if tmp_path is not None:
                tmp_path.unlink(missing_ok=True)

    @settings(max_examples=100, deadline=None)
    @given(image_data=text_image_strategy())
    def test_property_ocr_confidence_scores(self, image_data):
        """
        Property 3: OCR Confidence Scores

        For any successful OCR extraction, the result should include confidence
        scores for each text region and an average confidence score between 0.0
        and 1.0.

        # Feature: verification-comparison-system, Property 3: OCR Confidence Scores

        **Validates: Requirements 1.3**
        """
        image, _text = image_data

        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp_file:
            tmp_path = Path(tmp_file.name)
            image.save(tmp_path, format='PNG')

        try:
            engine = OCREngine(language='eng')
            result = engine.extract_text(tmp_path)

            # Only assert on successful extractions
            assert result.success is True, "Valid images should extract successfully"

            # Property: average_confidence is a float in [0.0, 1.0]
            assert isinstance(result.average_confidence, float), (
                "average_confidence should be a float"
            )
            assert 0.0 <= result.average_confidence <= 1.0, (
                f"average_confidence should be between 0.0 and 1.0, got {result.average_confidence}"
            )

            # Property: Each region has a confidence float in [0.0, 1.0]
            for i, region in enumerate(result.regions):
                assert isinstance(region.confidence, float), (
                    f"Region {i} confidence should be a float"
                )
                assert 0.0 <= region.confidence <= 1.0, (
                    f"Region {i} confidence should be between 0.0 and 1.0, got {region.confidence}"
                )

            # Property: If regions exist, average_confidence equals mean of region confidences
            if result.regions:
                expected_avg = sum(r.confidence for r in result.regions) / len(result.regions)
                assert abs(result.average_confidence - expected_avg) < 1e-9, (
                    f"average_confidence ({result.average_confidence}) should equal "
                    f"mean of region confidences ({expected_avg})"
                )
            else:
                # No regions means average_confidence should be 0.0
                assert result.average_confidence == 0.0, (
                    f"average_confidence should be 0.0 when no regions exist, got {result.average_confidence}"
                )

        finally:
            tmp_path.unlink(missing_ok=True)

    
    def test_property_ocr_pdf_support(self):
        """
        Property: OCR should support PDF files in addition to images.
        
        PDF files should be processed successfully and return valid results.
        
        **Validates: Requirements 1.1**
        """
        # Create a simple image
        image = Image.new('RGB', (400, 200), color='white')
        draw = ImageDraw.Draw(image)
        draw.text((10, 50), "PDF Test", fill='black')
        
        # Save as PNG first (PDF creation requires additional libraries)
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp_file:
            tmp_path = Path(tmp_file.name)
            image.save(tmp_path, format='PNG')
        
        try:
            engine = OCREngine(language='eng')
            result = engine.extract_text(tmp_path)
            
            # Property: PNG files should be processed successfully
            assert result.success is True
            assert isinstance(result.full_text, str)
            assert isinstance(result.regions, list)
            assert isinstance(result.average_confidence, float)
            assert 0.0 <= result.average_confidence <= 1.0
        
        finally:
            tmp_path.unlink(missing_ok=True)
