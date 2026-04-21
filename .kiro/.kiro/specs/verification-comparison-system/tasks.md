# Implementation Plan: Verification and Comparison System

## Overview

This implementation adds OCR-based verification capabilities to the existing payment compliance monitor. The system extracts payment data from both HTML and screenshots, compares them to detect discrepancies, and validates both sources against contract conditions. Implementation reuses existing components (analyzer.py, validator.py, screenshot_capture.py, models.py) and adds new OCR and verification services.

## Tasks

- [x] 1. Set up OCR dependencies and engine
  - [x] 1.1 Install pytesseract and Tesseract OCR dependencies
    - Add pytesseract, Pillow, pdf2image to requirements.txt
    - Document Tesseract installation for Ubuntu/macOS in README
    - _Requirements: 1.1, 1.5_
  
  - [x] 1.2 Implement OCR engine with text extraction
    - Create genai/src/ocr_engine.py with OCREngine class
    - Implement extract_text() method for PNG files
    - Implement extract_text_from_pdf() method for PDF files
    - Return OCRResult with full_text, regions, confidence scores
    - _Requirements: 1.1, 1.3, 1.4_
  
  - [x] 1.3 Write property test for OCR text extraction
    - **Property 1: OCR Text Extraction Success**
    - **Validates: Requirements 1.1, 1.4**
    - Test that valid images return success=True with extracted text
  
  - [x] 1.4 Write property test for OCR error handling
    - **Property 2: OCR Error Handling**
    - **Validates: Requirements 1.2**
    - Test that invalid/corrupted files return success=False with error message
  
  - [x]* 1.5 Write property test for OCR confidence scores
    - **Property 3: OCR Confidence Scores**
    - **Validates: Requirements 1.3**
    - Test that successful extractions include confidence scores between 0.0 and 1.0

- [x] 2. Create database model and migration
  - [x] 2.1 Add VerificationResult model to models.py
    - Add VerificationResult class with all required fields
    - Define relationships to MonitoringSite
    - Add indexes for site_id, created_at, status
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_
  
  - [x] 2.2 Create Alembic migration for verification_results table
    - Generate migration script with alembic revision
    - Create verification_results table with JSONB columns
    - Add foreign key to monitoring_sites
    - Add all required indexes
    - _Requirements: 5.1_
  
  - [x]* 2.3 Write unit tests for VerificationResult model
    - Test model creation and field validation
    - Test relationships and queries
    - _Requirements: 5.1, 5.2_

- [x] 3. Checkpoint - Verify database setup
  - Ensure migration runs successfully, ask the user if questions arise.

- [x] 4. Implement verification service with comparison logic
  - [x] 4.1 Create verification service skeleton
    - Create genai/src/verification_service.py with VerificationService class
    - Define Discrepancy and VerificationData dataclasses
    - Initialize with dependencies (analyzer, validator, ocr_engine, screenshot_capture, db_session)
    - _Requirements: 3.1, 3.6_
  
  - [x] 4.2 Implement payment extraction from OCR text
    - Implement _extract_payment_from_ocr() method
    - Reuse ContentAnalyzer patterns for price, currency, payment method extraction
    - Handle missing data gracefully with null values
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_
  
  - [x]* 4.3 Write property test for extraction pattern consistency
    - **Property 4: Extraction Pattern Consistency**
    - **Validates: Requirements 2.1, 2.2, 2.3, 2.4**
    - Test that identical text produces identical PaymentInfo from HTML and OCR paths
  
  - [x]* 4.4 Write property test for graceful missing data handling
    - **Property 5: Graceful Missing Data Handling**
    - **Validates: Requirements 2.5**
    - Test that text without payment info returns PaymentInfo with null/empty values
  
  - [x] 4.5 Implement field-by-field comparison logic
    - Implement _compare_payment_data() method
    - Compare prices, payment_methods, fees, subscription_terms fields
    - Generate Discrepancy objects with field_name, values, difference_type, severity
    - _Requirements: 3.4, 3.5, 3.6_
  
  - [x]* 4.6 Write property test for field-by-field comparison
    - **Property 7: Field-by-Field Comparison**
    - **Validates: Requirements 3.4**
    - Test that comparison checks all PaymentInfo fields
  
  - [x]* 4.7 Write property test for discrepancy detection
    - **Property 8: Discrepancy Detection**
    - **Validates: Requirements 3.5**
    - Test that differing field values generate Discrepancy objects
  
  - [x]* 4.8 Write property test for discrepancy structure
    - **Property 9: Discrepancy Structure Completeness**
    - **Validates: Requirements 3.6**
    - Test that Discrepancies include all required fields
  
  - [x] 4.9 Implement complete verification workflow
    - Implement run_verification() method with all workflow steps
    - Extract HTML data using ContentAnalyzer
    - Capture screenshot using ScreenshotCapture
    - Extract OCR data from screenshot
    - Compare HTML and OCR data
    - Validate both sources against contract
    - Store VerificationResult in database
    - Handle errors with partial_failure and failure statuses
    - _Requirements: 3.1, 3.2, 3.3, 4.1, 4.2, 5.1, 5.5_
  
  - [x]* 4.10 Write property test for complete verification workflow
    - **Property 6: Complete Verification Workflow**
    - **Validates: Requirements 3.1, 3.2, 3.3**
    - Test that all workflow steps execute for valid sites
  
  - [x]* 4.11 Write property test for dual source validation
    - **Property 10: Dual Source Validation**
    - **Validates: Requirements 4.1, 4.2**
    - Test that validation runs for both HTML and OCR data
  
  - [x]* 4.12 Write property test for violation source attribution
    - **Property 11: Violation Source Attribution**
    - **Validates: Requirements 4.3**
    - Test that violations include data_source field
  
  - [x]* 4.13 Write property test for violation structure
    - **Property 12: Violation Structure Completeness**
    - **Validates: Requirements 4.4**
    - Test that violations include all required fields
  
  - [x]* 4.14 Write property test for independent violation recording
    - **Property 13: Independent Violation Recording**
    - **Validates: Requirements 4.5**
    - Test that same condition violations from different sources create separate records
  
  - [x]* 4.15 Write unit tests for verification service
    - Test error handling for screenshot failures
    - Test error handling for OCR failures
    - Test partial_failure status scenarios
    - _Requirements: 3.1, 3.2, 3.3, 5.5_

- [x] 5. Checkpoint - Verify core verification logic
  - Ensure all tests pass, ask the user if questions arise.

- [x] 6. Implement verification API endpoints
  - [x] 6.1 Create verification API router
    - Create genai/src/api/verification.py with FastAPI router
    - Define request/response schemas (VerificationTriggerRequest, VerificationResultResponse, etc.)
    - _Requirements: 6.1, 7.1_
  
  - [x] 6.2 Implement POST /api/verification/run endpoint
    - Accept site_id and optional parameters (screenshot_resolution, ocr_language)
    - Validate site_id exists, return 404 if not found
    - Check for concurrent verification, return 409 if already running
    - Trigger verification in background task
    - Return 202 status with job_id
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_
  
  - [x]* 6.3 Write property test for API verification trigger
    - **Property 17: API Verification Trigger**
    - **Validates: Requirements 6.1, 6.2**
    - Test that valid site_id returns 202 and initiates job
  
  - [x]* 6.4 Write property test for API site validation
    - **Property 18: API Site Validation**
    - **Validates: Requirements 6.3**
    - Test that non-existent site_id returns 404
  
  - [x]* 6.5 Write property test for API concurrency control
    - **Property 19: API Concurrency Control**
    - **Validates: Requirements 6.4**
    - Test that concurrent requests for same site return 409
  
  - [x]* 6.6 Write property test for API optional parameters
    - **Property 20: API Optional Parameters**
    - **Validates: Requirements 6.5**
    - Test that optional parameters are accepted and used
  
  - [x] 6.7 Implement GET /api/verification/results/{site_id} endpoint
    - Accept site_id and pagination parameters (limit, offset)
    - Query VerificationResult from database
    - Return 404 if no results exist
    - Return results with pagination metadata
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5_
  
  - [x]* 6.8 Write property test for API results retrieval
    - **Property 21: API Results Retrieval**
    - **Validates: Requirements 7.1, 7.2**
    - Test that existing results return 200 with JSON data
  
  - [x]* 6.9 Write property test for API no results handling
    - **Property 22: API No Results Handling**
    - **Validates: Requirements 7.3**
    - Test that missing results return 404
  
  - [x]* 6.10 Write property test for API pagination
    - **Property 23: API Pagination Support**
    - **Validates: Requirements 7.4, 7.5**
    - Test that limit parameter controls result count and metadata is included
  
  - [x] 6.11 Implement GET /api/verification/status/{job_id} endpoint
    - Accept job_id
    - Return job status (processing, completed, failed)
    - Return result if completed
    - _Requirements: 6.2_
  
  - [x] 6.12 Register verification router in main.py
    - Import verification router
    - Add router to FastAPI app with /api/verification prefix
    - _Requirements: 6.1, 7.1_
  
  - [x]* 6.13 Write integration tests for API endpoints
    - Test complete verification flow via API
    - Test error responses and status codes
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 7.1, 7.2, 7.3_

- [x] 7. Checkpoint - Verify API functionality
  - Ensure all tests pass, ask the user if questions arise.

- [x] 8. Implement frontend verification UI
  - [x] 8.1 Create Verification page component
    - Create genai/frontend/src/pages/Verification.tsx
    - Define VerificationState interface and component structure
    - Add site selector dropdown
    - Add "Run Verification" button with loading state
    - _Requirements: 8.1, 8.2, 8.3_
  
  - [x] 8.2 Implement API integration in frontend
    - Add verification API methods to services/api.ts
    - Implement triggerVerification() function
    - Implement fetchVerificationResults() function
    - Implement pollVerificationStatus() function
    - _Requirements: 8.2, 8.9_
  
  - [x] 8.3 Create comparison table component
    - Create ComparisonTable sub-component
    - Display three columns: HTML Data, OCR Data, Contract Conditions
    - Align matching fields in same row
    - Display "Not Found" for missing values
    - _Requirements: 8.4, 8.5, 9.1, 9.2, 9.3_
  
  - [x] 8.4 Implement discrepancy and violation highlighting
    - Add color coding: green for matches, yellow for discrepancies, red for violations
    - Display warning icons in Status column for violations
    - Show which data source has violations (HTML, OCR, or both)
    - Highlight discrepancy rows in red
    - Display OCR confidence scores next to OCR values
    - _Requirements: 8.6, 8.7, 8.8, 9.4, 9.5_
  
  - [x] 8.5 Implement error handling and display
    - Display error messages when verification fails
    - Show user-friendly error messages
    - _Requirements: 8.10_
  
  - [x] 8.6 Create historical results component
    - Create HistoricalResults sub-component
    - Display list of previous verification runs with timestamps
    - Show summary count of discrepancies and violations
    - Implement result selection to display in comparison table
    - _Requirements: 10.1, 10.2, 10.3_
  
  - [x] 8.7 Implement filtering and export features
    - Add date range filter for historical results
    - Implement CSV export functionality
    - _Requirements: 10.4, 10.5_
  
  - [x] 8.8 Add Verification route to App.tsx
    - Import Verification component
    - Add route for /verification path
    - Add navigation link in app menu
    - _Requirements: 8.1_
  
  - [x]* 8.9 Write unit tests for Verification component
    - Test site selection and verification triggering
    - Test comparison table rendering
    - Test error display
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.10_
  
  - [x]* 8.10 Write unit tests for API integration
    - Test API method calls with mock responses
    - Test error handling
    - _Requirements: 8.2, 8.9_

- [x] 9. Checkpoint - Verify frontend functionality
  - Ensure all tests pass, ask the user if questions arise.

- [x] 10. Property-based test infrastructure setup
  - [x]* 10.1 Configure hypothesis for backend tests
    - Add hypothesis to requirements.txt
    - Configure pytest for property-based tests
    - Set minimum 100 iterations per property test
    - Add feature tags to all property tests
  
  - [x]* 10.2 Configure fast-check for frontend tests
    - Add fast-check to package.json
    - Configure vitest for property-based tests
    - Set minimum 100 iterations per property test
    - Add feature tags to all property tests

- [x] 11. Integration and final testing
  - [x] 11.1 Create end-to-end integration test
    - Test complete flow: trigger verification → capture screenshot → OCR extraction → comparison → validation → storage → retrieval
    - Verify database records created correctly
    - Verify screenshot files saved correctly
    - _Requirements: 3.1, 3.2, 3.3, 5.1, 6.1, 7.1_
  
  - [x]* 11.2 Write property test for verification result persistence
    - **Property 14: Verification Result Persistence**
    - **Validates: Requirements 5.1**
    - Test that completed verifications create database records
  
  - [x]* 11.3 Write property test for complete result storage
    - **Property 15: Complete Result Storage**
    - **Validates: Requirements 5.2, 5.3, 5.4**
    - Test that stored results include all required fields
  
  - [x]* 11.4 Write property test for error message storage
    - **Property 16: Error Message Storage**
    - **Validates: Requirements 5.5**
    - Test that failed verifications include error_message
  
  - [x] 11.5 Create sample test data
    - Create sample payment HTML files
    - Create sample screenshots with known content
    - Create sample contract conditions
    - _Requirements: 3.1, 3.2_
  
  - [x]* 11.6 Run performance benchmarks
    - Verify OCR extraction completes in < 5 seconds
    - Verify complete verification completes in < 15 seconds
    - Verify API response time < 100ms
    - _Requirements: 1.5_

- [x] 12. Final checkpoint - Complete system verification
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation at key milestones
- Property tests validate universal correctness properties using hypothesis (Python) and fast-check (TypeScript)
- Unit tests validate specific examples and edge cases
- The implementation reuses existing components: analyzer.py, validator.py, screenshot_capture.py, models.py
- New components: ocr_engine.py, verification_service.py, api/verification.py, Verification.tsx
- Database migration required for verification_results table
- Tesseract OCR must be installed on the system before running
