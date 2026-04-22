# Requirements Document

## Introduction

The Verification and Comparison System extends the payment compliance monitor to detect discrepancies between HTML-extracted payment data and image-embedded payment data. This system uses OCR to extract text from screenshots, compares multiple data sources against contract conditions, and identifies potential hidden information that differs between visual and programmatic representations.

## Glossary

- **Verification_Service**: The service that orchestrates data extraction from multiple sources and performs comparison
- **OCR_Engine**: The component that extracts text from screenshot images (PNG/PDF format)
- **Content_Analyzer**: The existing component (analyzer.py) that extracts payment information from HTML
- **Validation_Engine**: The existing component (validator.py) that compares extracted data against contract conditions
- **Screenshot_Capture**: The existing component (screenshot_capture.py) that captures site screenshots using Playwright
- **HTML_Data**: Payment information extracted from HTML source code
- **OCR_Data**: Payment information extracted from screenshot images via OCR
- **Contract_Conditions**: The agreed-upon payment terms stored in the contract
- **Discrepancy**: A difference between HTML_Data and OCR_Data for the same payment field
- **Violation**: A difference between extracted data (HTML or OCR) and Contract_Conditions
- **Verification_Result**: The complete output of a verification run including all comparisons and discrepancies
- **Site**: A customer payment website being monitored

## Requirements

### Requirement 1: OCR Text Extraction

**User Story:** As a compliance officer, I want to extract text from payment page screenshots, so that I can verify visual payment information matches the HTML content.

#### Acceptance Criteria

1. WHEN a screenshot file (PNG or PDF) is provided, THE OCR_Engine SHALL extract all visible text from the image
2. WHEN OCR extraction fails, THE OCR_Engine SHALL return a descriptive error message
3. THE OCR_Engine SHALL return extracted text with confidence scores for each text region
4. WHEN a screenshot contains no readable text, THE OCR_Engine SHALL return an empty result with success status
5. THE OCR_Engine SHALL process screenshots within 10 seconds for standard payment pages

### Requirement 2: Payment Data Extraction from OCR Text

**User Story:** As a compliance officer, I want to parse payment information from OCR-extracted text, so that I can identify payment terms displayed visually.

#### Acceptance Criteria

1. WHEN OCR text is provided, THE Verification_Service SHALL extract payment amounts using the same patterns as Content_Analyzer
2. WHEN OCR text is provided, THE Verification_Service SHALL extract payment frequencies (monthly, annual, one-time)
3. WHEN OCR text is provided, THE Verification_Service SHALL extract currency codes
4. WHEN OCR text is provided, THE Verification_Service SHALL extract payment method information
5. WHEN payment data cannot be extracted from OCR text, THE Verification_Service SHALL return null values for missing fields

### Requirement 3: Multi-Source Data Comparison

**User Story:** As a compliance officer, I want to compare HTML-extracted data with OCR-extracted data, so that I can detect hidden information in images.

#### Acceptance Criteria

1. WHEN verification runs for a Site, THE Verification_Service SHALL extract HTML_Data using Content_Analyzer
2. WHEN verification runs for a Site, THE Verification_Service SHALL capture a screenshot using Screenshot_Capture
3. WHEN verification runs for a Site, THE Verification_Service SHALL extract OCR_Data from the captured screenshot
4. WHEN both HTML_Data and OCR_Data are available, THE Verification_Service SHALL compare each payment field
5. WHEN a payment field differs between HTML_Data and OCR_Data, THE Verification_Service SHALL record a Discrepancy
6. THE Verification_Service SHALL include the field name, HTML value, OCR value, and difference type in each Discrepancy

### Requirement 4: Contract Compliance Validation

**User Story:** As a compliance officer, I want to validate both HTML and OCR data against contract conditions, so that I can identify violations from any data source.

#### Acceptance Criteria

1. WHEN HTML_Data is extracted, THE Verification_Service SHALL validate it against Contract_Conditions using Validation_Engine
2. WHEN OCR_Data is extracted, THE Verification_Service SHALL validate it against Contract_Conditions using Validation_Engine
3. WHEN validation detects a Violation, THE Verification_Service SHALL record the data source (HTML or OCR)
4. THE Verification_Service SHALL record all Violations with field name, expected value, actual value, and severity
5. WHEN both HTML_Data and OCR_Data violate the same condition differently, THE Verification_Service SHALL record both Violations separately

### Requirement 5: Verification Result Storage

**User Story:** As a compliance officer, I want verification results stored in the database, so that I can track compliance history over time.

#### Acceptance Criteria

1. WHEN verification completes for a Site, THE Verification_Service SHALL store a Verification_Result in the database
2. THE Verification_Result SHALL include timestamp, site_id, HTML_Data, OCR_Data, all Discrepancies, and all Violations
3. THE Verification_Result SHALL include screenshot file path and OCR confidence scores
4. THE Verification_Result SHALL include verification status (success, partial_failure, failure)
5. WHEN verification fails completely, THE Verification_Service SHALL store the error message in Verification_Result

### Requirement 6: Verification Trigger API

**User Story:** As a compliance officer, I want to trigger verification for a specific site via API, so that I can run on-demand compliance checks.

#### Acceptance Criteria

1. WHEN a POST request is sent to /api/verification/run with site_id, THE API SHALL initiate verification for that Site
2. WHEN verification is triggered, THE API SHALL return a 202 status with verification job identifier
3. WHEN site_id does not exist, THE API SHALL return a 404 error
4. WHEN verification is already running for a Site, THE API SHALL return a 409 conflict error
5. THE API SHALL accept optional parameters for screenshot resolution and OCR engine settings

### Requirement 7: Verification Results Retrieval API

**User Story:** As a compliance officer, I want to retrieve verification results via API, so that I can display them in the frontend.

#### Acceptance Criteria

1. WHEN a GET request is sent to /api/verification/results/{site_id}, THE API SHALL return the most recent Verification_Result for that Site
2. THE API SHALL return Verification_Result in JSON format with all Discrepancies and Violations
3. WHEN no verification results exist for a Site, THE API SHALL return a 404 error
4. THE API SHALL support query parameter "limit" to retrieve multiple historical results
5. THE API SHALL include pagination metadata when returning multiple results

### Requirement 8: Verification UI Display

**User Story:** As a compliance officer, I want to view verification results in a clear table format, so that I can quickly identify compliance issues.

#### Acceptance Criteria

1. THE Verification_UI SHALL display a site selector dropdown to choose which Site to verify
2. WHEN the "Run Verification" button is clicked, THE Verification_UI SHALL trigger verification via the API
3. WHEN verification is running, THE Verification_UI SHALL display a loading indicator
4. WHEN verification completes, THE Verification_UI SHALL display results in a comparison table
5. THE comparison table SHALL have columns: Field Name, HTML Value, OCR Value, Contract Value, Status
6. WHEN a Discrepancy exists, THE Verification_UI SHALL highlight the row in red
7. WHEN a Violation exists, THE Verification_UI SHALL display a warning icon in the Status column
8. THE Verification_UI SHALL display which data source (HTML, OCR, or both) has Violations
9. THE Verification_UI SHALL refresh results automatically when verification completes
10. WHEN verification fails, THE Verification_UI SHALL display the error message to the user

### Requirement 9: Side-by-Side Comparison View

**User Story:** As a compliance officer, I want to see HTML data, OCR data, and contract conditions side-by-side, so that I can understand the exact differences.

#### Acceptance Criteria

1. THE Verification_UI SHALL display three columns: HTML Data, OCR Data, Contract Conditions
2. WHEN a field has different values across sources, THE Verification_UI SHALL align them in the same row
3. WHEN a field exists in one source but not another, THE Verification_UI SHALL display "Not Found" for missing values
4. THE Verification_UI SHALL use color coding: green for matches, yellow for discrepancies, red for violations
5. THE Verification_UI SHALL display OCR confidence scores next to OCR_Data values

### Requirement 10: Verification History

**User Story:** As a compliance officer, I want to view historical verification results, so that I can track compliance trends over time.

#### Acceptance Criteria

1. THE Verification_UI SHALL display a list of previous verification runs with timestamps
2. WHEN a historical result is selected, THE Verification_UI SHALL display that result in the comparison table
3. THE Verification_UI SHALL display a summary count of Discrepancies and Violations for each historical run
4. THE Verification_UI SHALL support filtering results by date range
5. THE Verification_UI SHALL support exporting verification results to CSV format
