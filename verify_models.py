#!/usr/bin/env python3
"""
Simple script to verify that all SQLAlchemy models are correctly defined.
"""

import sys

try:
    from src.models import (
        MonitoringSite,
        ContractCondition,
        CrawlResult,
        ValidationResult,
        Violation,
        Alert,
        Base
    )
    
    print("✓ All models imported successfully")
    
    # Verify table names
    expected_tables = {
        'monitoring_sites': MonitoringSite,
        'contract_conditions': ContractCondition,
        'crawl_results': CrawlResult,
        'validation_results': ValidationResult,
        'violations': Violation,
        'alerts': Alert,
    }
    
    for table_name, model_class in expected_tables.items():
        if model_class.__tablename__ == table_name:
            print(f"✓ {model_class.__name__} has correct table name: {table_name}")
        else:
            print(f"✗ {model_class.__name__} has incorrect table name: {model_class.__tablename__} (expected: {table_name})")
            sys.exit(1)
    
    # Verify relationships
    print("\n✓ Checking relationships...")
    
    # MonitoringSite relationships
    assert hasattr(MonitoringSite, 'contract_conditions'), "MonitoringSite missing contract_conditions relationship"
    assert hasattr(MonitoringSite, 'crawl_results'), "MonitoringSite missing crawl_results relationship"
    print("✓ MonitoringSite relationships defined")
    
    # ContractCondition relationships
    assert hasattr(ContractCondition, 'site'), "ContractCondition missing site relationship"
    print("✓ ContractCondition relationships defined")
    
    # CrawlResult relationships
    assert hasattr(CrawlResult, 'site'), "CrawlResult missing site relationship"
    assert hasattr(CrawlResult, 'validation_results'), "CrawlResult missing validation_results relationship"
    print("✓ CrawlResult relationships defined")
    
    # ValidationResult relationships
    assert hasattr(ValidationResult, 'crawl_result'), "ValidationResult missing crawl_result relationship"
    assert hasattr(ValidationResult, 'contract_condition'), "ValidationResult missing contract_condition relationship"
    assert hasattr(ValidationResult, 'violations'), "ValidationResult missing violations relationship"
    print("✓ ValidationResult relationships defined")
    
    # Violation relationships
    assert hasattr(Violation, 'validation_result'), "Violation missing validation_result relationship"
    assert hasattr(Violation, 'alerts'), "Violation missing alerts relationship"
    print("✓ Violation relationships defined")
    
    # Alert relationships
    assert hasattr(Alert, 'violation'), "Alert missing violation relationship"
    print("✓ Alert relationships defined")
    
    # Verify key columns
    print("\n✓ Checking key columns...")
    
    # MonitoringSite columns
    assert hasattr(MonitoringSite, 'id'), "MonitoringSite missing id column"
    assert hasattr(MonitoringSite, 'company_name'), "MonitoringSite missing company_name column"
    assert hasattr(MonitoringSite, 'domain'), "MonitoringSite missing domain column"
    assert hasattr(MonitoringSite, 'target_url'), "MonitoringSite missing target_url column"
    assert hasattr(MonitoringSite, 'is_active'), "MonitoringSite missing is_active column"
    assert hasattr(MonitoringSite, 'created_at'), "MonitoringSite missing created_at column"
    print("✓ MonitoringSite columns defined")
    
    # ContractCondition columns
    assert hasattr(ContractCondition, 'id'), "ContractCondition missing id column"
    assert hasattr(ContractCondition, 'site_id'), "ContractCondition missing site_id column"
    assert hasattr(ContractCondition, 'version'), "ContractCondition missing version column"
    assert hasattr(ContractCondition, 'prices'), "ContractCondition missing prices column"
    assert hasattr(ContractCondition, 'payment_methods'), "ContractCondition missing payment_methods column"
    assert hasattr(ContractCondition, 'fees'), "ContractCondition missing fees column"
    assert hasattr(ContractCondition, 'subscription_terms'), "ContractCondition missing subscription_terms column"
    assert hasattr(ContractCondition, 'is_current'), "ContractCondition missing is_current column"
    assert hasattr(ContractCondition, 'created_at'), "ContractCondition missing created_at column"
    print("✓ ContractCondition columns defined")
    
    # CrawlResult columns
    assert hasattr(CrawlResult, 'id'), "CrawlResult missing id column"
    assert hasattr(CrawlResult, 'site_id'), "CrawlResult missing site_id column"
    assert hasattr(CrawlResult, 'url'), "CrawlResult missing url column"
    assert hasattr(CrawlResult, 'html_content'), "CrawlResult missing html_content column"
    assert hasattr(CrawlResult, 'status_code'), "CrawlResult missing status_code column"
    assert hasattr(CrawlResult, 'crawled_at'), "CrawlResult missing crawled_at column"
    print("✓ CrawlResult columns defined")
    
    # Violation columns
    assert hasattr(Violation, 'id'), "Violation missing id column"
    assert hasattr(Violation, 'validation_result_id'), "Violation missing validation_result_id column"
    assert hasattr(Violation, 'violation_type'), "Violation missing violation_type column"
    assert hasattr(Violation, 'severity'), "Violation missing severity column"
    assert hasattr(Violation, 'field_name'), "Violation missing field_name column"
    assert hasattr(Violation, 'expected_value'), "Violation missing expected_value column"
    assert hasattr(Violation, 'actual_value'), "Violation missing actual_value column"
    assert hasattr(Violation, 'detected_at'), "Violation missing detected_at column"
    print("✓ Violation columns defined")
    
    # Alert columns
    assert hasattr(Alert, 'id'), "Alert missing id column"
    assert hasattr(Alert, 'violation_id'), "Alert missing violation_id column"
    assert hasattr(Alert, 'alert_type'), "Alert missing alert_type column"
    assert hasattr(Alert, 'severity'), "Alert missing severity column"
    assert hasattr(Alert, 'message'), "Alert missing message column"
    assert hasattr(Alert, 'email_sent'), "Alert missing email_sent column"
    assert hasattr(Alert, 'slack_sent'), "Alert missing slack_sent column"
    assert hasattr(Alert, 'created_at'), "Alert missing created_at column"
    print("✓ Alert columns defined")
    
    print("\n" + "="*50)
    print("✓ All models are correctly defined!")
    print("="*50)
    
except ImportError as e:
    print(f"✗ Import error: {e}")
    sys.exit(1)
except AssertionError as e:
    print(f"✗ Assertion error: {e}")
    sys.exit(1)
except Exception as e:
    print(f"✗ Unexpected error: {e}")
    sys.exit(1)
