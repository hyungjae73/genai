#!/usr/bin/env python
"""
Verification script for Alembic migration.

This script verifies that the Alembic migration can be loaded and contains
the expected tables and indexes.
"""

import sys
from pathlib import Path

# Add the parent directory to the path
sys.path.insert(0, str(Path(__file__).parent))

from alembic.config import Config
from alembic.script import ScriptDirectory


def verify_migration():
    """Verify the Alembic migration setup."""
    print("🔍 Verifying Alembic migration setup...\n")
    
    # Load Alembic configuration
    alembic_cfg = Config("alembic.ini")
    script = ScriptDirectory.from_config(alembic_cfg)
    
    # Get all revisions
    revisions = list(script.walk_revisions())
    
    print(f"✅ Found {len(revisions)} migration(s)")
    
    for rev in revisions:
        print(f"\n📄 Migration: {rev.revision}")
        print(f"   Description: {rev.doc}")
        print(f"   Down revision: {rev.down_revision}")
        
        # Load the migration module
        module = rev.module
        
        # Check if upgrade and downgrade functions exist
        if hasattr(module, 'upgrade'):
            print("   ✅ upgrade() function found")
        else:
            print("   ❌ upgrade() function missing")
            return False
            
        if hasattr(module, 'downgrade'):
            print("   ✅ downgrade() function found")
        else:
            print("   ❌ downgrade() function missing")
            return False
    
    # Verify expected tables in the initial migration
    initial_rev = revisions[-1]  # First migration
    module = initial_rev.module
    
    # Read the source code to check for expected tables
    import inspect
    source = inspect.getsource(module.upgrade)
    
    expected_tables = [
        'monitoring_sites',
        'contract_conditions',
        'crawl_results',
        'violations',
        'alerts'
    ]
    
    print("\n📊 Checking for expected tables:")
    all_found = True
    for table in expected_tables:
        if table in source:
            print(f"   ✅ {table}")
        else:
            print(f"   ❌ {table} - NOT FOUND")
            all_found = False
    
    # Check for indexes
    print("\n🔍 Checking for indexes:")
    expected_indexes = [
        'ix_monitoring_sites_domain',
        'ix_contract_conditions_site_id',
        'ix_crawl_results_site_id',
        'ix_violations_validation_result_id',
        'ix_alerts_violation_id'
    ]
    
    for index in expected_indexes:
        if index in source:
            print(f"   ✅ {index}")
        else:
            print(f"   ❌ {index} - NOT FOUND")
            all_found = False
    
    if all_found:
        print("\n✅ All verification checks passed!")
        print("\n📝 Next steps:")
        print("   1. Start the database: docker-compose up -d postgres")
        print("   2. Run migrations: alembic upgrade head")
        print("   3. Verify in database: docker-compose exec postgres psql -U payment_monitor -d payment_monitor -c '\\dt'")
        return True
    else:
        print("\n❌ Some verification checks failed!")
        return False


if __name__ == "__main__":
    success = verify_migration()
    sys.exit(0 if success else 1)
