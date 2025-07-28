import pandas as pd
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any

from src.core.bluesky_client import BlueskyClient
from src.services.database_service import DatabaseService


class PostService:
    """Service for managing post data and updates."""
    
    def __init__(self, bluesky_client: BlueskyClient, database_service: DatabaseService):
        self.bluesky_client = bluesky_client
        self.database_service = database_service
        self.logger = logging.getLogger(__name__)
    
    def get_posts_for_actor(self, actor: str, cursor: str = "", 
                           posts: pd.DataFrame = None, fetch_all: bool = False) -> pd.DataFrame:
        """Get posts for an actor from Bluesky API."""
        if posts is None:
            posts = pd.DataFrame()
        
        try:
            response = self.bluesky_client._call_endpoint(
                'app.bsky.feed.getAuthorFeed', 
                f'actor={actor}&cursor={cursor}&limit=100'
            )
            
            if len(posts) > 0:
                self.logger.info(f"Processing posts for {actor}: {len(posts)} posts, cursor: {cursor}")
            
            # Filter posts by the actor (exclude reposts)
            for post in response['feed']:
                if post['post']['author']['did'] == actor:
                    df = pd.DataFrame([post['post']])
                    posts = pd.concat([posts, df], ignore_index=True)
            
            # Recursive call if more posts available
            if 'cursor' in response and len(posts) < 10000:
                if fetch_all:
                    posts = self.get_posts_for_actor(actor, response['cursor'], posts, fetch_all)
                else:
                    # For regular updates, only fetch recent posts (last 7 days)
                    now = datetime.now(timezone.utc)
                    time_range = now - timedelta(days=7)
                    cursor_datetime = datetime.strptime(
                        response['cursor'][0:10], '%Y-%m-%d'
                    ).replace(tzinfo=timezone.utc)
                    
                    if cursor_datetime > time_range:
                        posts = self.get_posts_for_actor(actor, response['cursor'], posts, fetch_all)
            
            return posts
            
        except Exception as e:
            self.logger.error(f"Error fetching posts for {actor}: {e}")
            return posts if posts is not None else pd.DataFrame()
    
    def update_posts_for_actor(self, did: str, update_all: bool = False) -> None:
        """Update posts for an actor in the database."""
        try:
            # Check if user has any posts; if not, grab all
            with self.database_service.get_connection() as conn:
                cursor = conn.cursor()
                self.database_service.safe_execute(
                    cursor, 
                    "SELECT count(*) FROM posts WHERE did = %s", 
                    (did,)
                )
                num_posts = cursor.fetchone()[0]
                
                # Fetch posts from API
                if num_posts == 0:
                    posts = self.get_posts_for_actor(did, fetch_all=True)
                else:
                    posts = self.get_posts_for_actor(did, fetch_all=update_all)
                
                if posts.empty:
                    return
                
                # Clean posts data
                posts = posts.drop_duplicates(subset=['uri'])
                
                # Get time range for filtering
                now = datetime.now(timezone.utc)
                time_range = now - timedelta(days=7)
                
                # Fetch existing posts from database
                if update_all:
                    existing_query = "SELECT * FROM posts WHERE did = %s"
                    query_params = (did,)
                else:
                    existing_query = "SELECT * FROM posts WHERE did = %s AND \"createdAt\" > %s"
                    query_params = (did, str(time_range)[0:10])
                
                self.database_service.safe_execute(cursor, existing_query, query_params)
                tracked_posts = cursor.fetchall()
                
                # Convert to DataFrame for easier processing
                tracked_posts_df = pd.DataFrame(
                    tracked_posts, 
                    columns=['uri', 'did', 'likes', 'replies', 'quotes', 'reposts', 'createdAt', 'updatedAt']
                )
                
                # Process new and updated posts
                posts_to_insert = []
                posts_updated = 0
                
                for _, row in posts.iterrows():
                    post_created_at = row['record']['createdAt']
                    
                    # Skip old posts if not doing full update
                    if not update_all and post_created_at <= str(time_range)[0:10]:
                        continue
                    
                    existing_post = tracked_posts_df[tracked_posts_df['uri'] == row['uri']]
                    
                    if not existing_post.empty:
                        # Update existing post if engagement changed
                        existing_row = existing_post.iloc[0]
                        if (existing_row['likes'] != row['likeCount'] or
                            existing_row['replies'] != row['replyCount'] or
                            existing_row['quotes'] != row['quoteCount'] or
                            existing_row['reposts'] != row['repostCount']):
                            
                            update_query = """
                                UPDATE posts
                                SET likes = %s, replies = %s, quotes = %s, reposts = %s, "updatedAt" = %s
                                WHERE uri = %s
                            """
                            self.database_service.safe_execute(cursor, update_query, (
                                row['likeCount'], row['replyCount'], 
                                row['quoteCount'], row['repostCount'],
                                now, row['uri']
                            ))
                            posts_updated += 1
                    else:
                        # New post to insert
                        posts_to_insert.append({
                            'uri': row['uri'],
                            'did': row['author']['did'],
                            'likes': row['likeCount'],
                            'replies': row['replyCount'],
                            'quotes': row['quoteCount'],
                            'reposts': row['repostCount'],
                            'createdAt': post_created_at,
                            'updatedAt': now
                        })
                
                # Batch insert new posts
                if posts_to_insert:
                    self.logger.info(f"{len(posts_to_insert)} new posts logged for {did}")
                    
                    insert_query = """
                        INSERT INTO posts (uri, did, likes, replies, quotes, reposts, "createdAt", "updatedAt")
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """
                    
                    for post_data in posts_to_insert:
                        self.database_service.safe_execute(cursor, insert_query, (
                            post_data['uri'], post_data['did'], post_data['likes'],
                            post_data['replies'], post_data['quotes'], post_data['reposts'],
                            post_data['createdAt'], post_data['updatedAt']
                        ))
                
                conn.commit()
                
                if posts_updated > 0:
                    self.logger.info(f"{posts_updated} posts updated for {did}")
                    
        except Exception as e:
            self.logger.error(f"Error updating posts for {did}: {e}")
            raise