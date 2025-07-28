"""
DopplerSky Snapshot Runner

This script runs the snapshot collection process for Bluesky analytics.
It fetches user profiles, updates posts, and stores analytics data.

Usage:
    python scripts/run_snapshots.py [--simple-query] [--config CONFIG_FILE]
"""

import argparse
import sys
import time
import os
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    from src.config.settings import AppConfig, setup_logging
    from src.core.bluesky_client import BlueskyClient
    from src.services.database_service import DatabaseService
    from src.services.post_service import PostService
    from src.services.snapshot_service import SnapshotService
except ImportError as e:
    print(f"Import error: {e}")
    print("Make sure you're running this script from the project root directory")
    print("Try: python -m scripts.run_snapshots")
    sys.exit(1)


class SnapshotRunner:
    """Main application runner for snapshot collection."""
    
    def __init__(self, config: AppConfig):
        self.config = config
        setup_logging(config.log_level)
        
        # Initialize services
        self.bluesky_client = BlueskyClient(config.bluesky_base_url)
        self.database_service = DatabaseService(config.database)
        self.post_service = PostService(self.bluesky_client, self.database_service)
        self.snapshot_service = SnapshotService(
            self.bluesky_client,
            self.database_service,
            self.post_service,
            config.max_workers
        )
    
    def run_snapshot_collection(self, use_simple_query: bool = False) -> None:
        """Run the main snapshot collection process."""
        import logging
        logger = logging.getLogger(__name__)
        
        logger.info("Starting snapshot collection process")
        start_time = time.time()
        
        try:
            # Create snapshot log entry
            log_id = self.database_service.create_snapshot_log()
            logger.info(f"Created snapshot log with ID: {log_id}")
            
            # Run snapshot collection
            total_users_processed = self.snapshot_service.create_snapshots_batch(use_simple_query)
            
            # Calculate duration and update log
            end_time = time.time()
            duration = end_time - start_time
            
            self.database_service.update_snapshot_log(log_id, duration, total_users_processed)
            
            logger.info(f"Snapshot collection completed successfully")
            logger.info(f"Processed {total_users_processed} users in {duration:.2f} seconds")
            
        except Exception as e:
            logger.error(f"Snapshot collection failed: {e}")
            raise
    
    def health_check(self) -> bool:
        """Perform a health check on all services."""
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            # Test database connection
            with self.database_service.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
                cursor.fetchone()
            
            # Test Bluesky API
            self.bluesky_client.get_single_profile('bsky.app')
            
            logger.info("Health check passed")
            return True
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Run DopplerSky snapshot collection",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python scripts/run_snapshots.py                    # Normal run
    python scripts/run_snapshots.py --simple-query    # Use simple user query
    python scripts/run_snapshots.py --config .env.prod # Use specific config
    python scripts/run_snapshots.py --health-check    # Run health check only
        """
    )
    
    parser.add_argument(
        '--simple-query', 
        action='store_true',
        help='Use simple "SELECT did, handle FROM users" query instead of activity-based filtering'
    )
    
    parser.add_argument(
        '--config', 
        type=str,
        help='Path to environment configuration file'
    )
    
    parser.add_argument(
        '--health-check',
        action='store_true',
        help='Run health check and exit'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose logging'
    )
    
    return parser.parse_args()


def main():
    """Main entry point."""
    args = parse_arguments()
    
    try:
        # Load configuration
        config = AppConfig.from_env(args.config)
        
        # Override log level if verbose
        if args.verbose:
            config.log_level = 'DEBUG'
        
        # Initialize runner
        runner = SnapshotRunner(config)
        
        # Run health check if requested
        if args.health_check:
            success = runner.health_check()
            sys.exit(0 if success else 1)
        
        # Run snapshot collection
        runner.run_snapshot_collection(args.simple_query)
        
        print("Snapshot collection completed successfully!")
        
    except KeyboardInterrupt:
        print("\nSnapshot collection interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()