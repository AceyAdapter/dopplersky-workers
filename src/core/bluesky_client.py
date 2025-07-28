import requests
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass


@dataclass
class UserProfile:
    """Data class for user profile information."""
    did: str
    handle: str
    display_name: Optional[str] = None
    avatar: Optional[str] = None
    followers_count: int = 0
    following_count: int = 0
    posts_count: int = 0


class BlueskyAPIError(Exception):
    """Custom exception for Bluesky API errors."""
    pass


class BlueskyClient:
    """Client for interacting with Bluesky API."""
    
    def __init__(self, base_url: str = "https://public.api.bsky.app"):
        self.base_url = base_url
        self.logger = logging.getLogger(__name__)
    
    def _call_endpoint(self, path: str, params: str = "") -> Dict[str, Any]:
        """Make a call to the Bluesky API endpoint."""
        url = f"{self.base_url}/xrpc/{path}"
        if params:
            url += f"?{params}"
        
        try:
            response = requests.get(url)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            self.logger.error(f"API call failed for {path}: {e}")
            raise BlueskyAPIError(f"Failed to call {path}: {e}")
    
    def get_profiles(self, dids: List[str]) -> List[UserProfile]:
        """Get multiple user profiles in a single API call."""
        if not dids:
            return []
        
        # Bluesky API supports multiple actors in one call
        params = '&'.join([f"actors={did}" for did in dids])
        
        try:
            response = self._call_endpoint('app.bsky.actor.getProfiles', params)
            profiles = []
            
            for profile_data in response.get('profiles', []):
                profile = UserProfile(
                    did=profile_data['did'],
                    handle=profile_data['handle'],
                    display_name=profile_data.get('displayName'),
                    avatar=profile_data.get('avatar'),
                    followers_count=profile_data.get('followersCount', 0),
                    following_count=profile_data.get('followsCount', 0),
                    posts_count=profile_data.get('postsCount', 0)
                )
                profiles.append(profile)
            
            return profiles
            
        except BlueskyAPIError as e:
            self.logger.error(f"Failed to get profiles for {len(dids)} users: {e}")
            raise
    
    def get_single_profile(self, actor: str) -> UserProfile:
        """Get a single user profile."""
        profiles = self.get_profiles([actor])
        if not profiles:
            raise BlueskyAPIError(f"No profile found for {actor}")
        return profiles[0]