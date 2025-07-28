import concurrent.futures
import logging
from datetime import datetime, timezone
from typing import List, Optional

from src.core.bluesky_client import BlueskyClient, UserProfile
from src.services.database_service import DatabaseService, SnapshotData
from src.services.post_service import PostService


class SnapshotService:
    """Service for creating user snapshots."""
    
    def __init__(self, 
                 bluesky_client: BlueskyClient,
                 database_service: DatabaseService,
                 post_service: PostService,
                 max_workers: int = 10):
        self.bluesky_client = bluesky_client
        self.database_service = database_service
        self.post_service = post_service
        self.max_workers = max_workers
        self.logger = logging.getLogger(__name__)
    
    def process_user_profile(self, profile: UserProfile, curr_date: str) -> Optional[SnapshotData]:
        """Process a single user profile and return snapshot data."""
        try:
            self.logger.info(f"Processing user: {profile.handle}")
            
            # Get user from database to check if update needed
            user_data = self.database_service.get_user_by_did(profile.did)
            if not user_data:
                self.logger.warning(f"User {profile.handle} not found in database")
                return None
            
            # Check if user should be skipped
            skip_user = user_data[7]  # Assuming skip_user is at index 7
            if skip_user:
                self.logger.info(f"Skipping {profile.handle}")
                return None
            
            # Check if user profile needs updating
            if self._should_update_user(profile, user_data):
                self.database_service.update_user_profile(profile)
            
            # Update posts for this user
            self.post_service.update_posts_for_actor(profile.did, update_all=False)
            
            # Get engagement totals
            engagement = self.database_service.get_engagement_totals(profile.did)
            
            # Create snapshot data
            snapshot = SnapshotData(
                did=profile.did,
                handle=profile.handle,
                date=curr_date,
                followers=profile.followers_count,
                following=profile.following_count,
                posts=profile.posts_count,
                likes=engagement['likes'],
                replies=engagement['replies'],
                quotes=engagement['quotes'],
                reposts=engagement['reposts']
            )
            
            # Save snapshot to database
            self.database_service.upsert_snapshot(snapshot)
            
            return snapshot
            
        except Exception as e:
            self.logger.error(f"Error processing user {profile.handle}: {e}")
            return None
    
    def _should_update_user(self, profile: UserProfile, user_data: tuple) -> bool:
        """Check if user profile needs updating."""
        # Assuming user_data structure: [did, handle, displayName, avatar, ...]
        current_handle = user_data[1]
        current_display_name = user_data[2]
        current_avatar = user_data[3]
        
        return (
            profile.handle != current_handle or
            profile.display_name != current_display_name or
            profile.avatar != current_avatar
        )
    
    def create_snapshots_batch(self, use_simple_query: bool = False) -> int:
        """Create snapshots for all active users."""
        curr_date = datetime.now(timezone.utc).strftime('%Y-%m-%d')
        
        # Get users to process
        users = self.database_service.get_active_users(use_simple_query)
        if not users:
            self.logger.warning("No users found to process")
            return 0
        
        # Batch users into chunks of 25 for API efficiency
        user_chunks = self._chunk_users(users, chunk_size=25)
        
        # Collect all profiles
        all_profiles = []
        self.logger.info("Fetching user data from Bluesky API")
        
        for chunk in user_chunks:
            dids = [user[0] for user in chunk]
            try:
                profiles = self.bluesky_client.get_profiles(dids)
                all_profiles.extend(profiles)
            except Exception as e:
                self.logger.error(f"Failed to fetch profiles for chunk: {e}")
                continue
        
        self.logger.info(f"Collected data for {len(all_profiles)} users")
        
        # Process profiles in parallel
        processed_count = 0
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = [
                executor.submit(self.process_user_profile, profile, curr_date)
                for profile in all_profiles
            ]
            
            for future in concurrent.futures.as_completed(futures):
                try:
                    result = future.result()
                    if result:
                        processed_count += 1
                except Exception as e:
                    self.logger.error(f"Future execution failed: {e}")
        
        self.logger.info(f"Successfully processed {processed_count} profiles")
        return processed_count
    
    def _chunk_users(self, users: List[tuple], chunk_size: int = 25) -> List[List[tuple]]:
        """Split users into chunks for batch processing."""
        chunks = []
        for i in range(0, len(users), chunk_size):
            chunks.append(users[i:i + chunk_size])
        return chunks