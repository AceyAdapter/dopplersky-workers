import psycopg2
import logging
from typing import List, Dict, Any, Optional, Tuple
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone

from src.core.bluesky_client import UserProfile


@dataclass
class DatabaseConfig:
    """Database configuration."""
    host: str
    database: str
    user: str
    password: str
    port: int


@dataclass
class SnapshotData:
    """Data structure for user snapshot."""
    did: str
    handle: str
    date: str
    followers: int
    following: int
    posts: int
    likes: int
    replies: int
    quotes: int
    reposts: int


class DatabaseService:
    """Service for database operations."""
    
    def __init__(self, config: DatabaseConfig):
        self.config = config
        self.logger = logging.getLogger(__name__)
    
    @contextmanager
    def get_connection(self):
        """Context manager for database connections."""
        conn = None
        try:
            conn = psycopg2.connect(
                host=self.config.host,
                database=self.config.database,
                user=self.config.user,
                password=self.config.password,
                port=self.config.port
            )
            yield conn
        except psycopg2.Error as e:
            self.logger.error(f"Database error: {e}")
            if conn:
                conn.rollback()
            raise
        finally:
            if conn:
                conn.close()
    
    def safe_execute(self, cursor, query: str, params: tuple = None) -> None:
        """Safely execute a database query with error handling."""
        try:
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
        except psycopg2.Error as e:
            self.logger.error(f"Query execution failed: {e}")
            self.logger.error(f"Query: {query}")
            raise
    
    def get_active_users(self, use_simple_query: bool = False) -> List[Tuple[str, str]]:
        """Get list of users to process snapshots for."""
        if use_simple_query:
            query = "SELECT did, handle FROM users"
        else:
            query = """
                SELECT DISTINCT u.did, u.handle
                FROM users u
                JOIN views v ON u.did = v.did
                WHERE v.date >= CURRENT_DATE - INTERVAL '7 days'
                ORDER BY u.handle;
            """
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            self.safe_execute(cursor, query)
            return cursor.fetchall()
    
    def get_engagement_totals(self, did: str) -> Dict[str, int]:
        """Get engagement totals for a user from posts table."""
        query = """
            SELECT SUM(likes) as likes, SUM(replies) as replies, 
                   SUM(quotes) as quotes, SUM(reposts) as reposts
            FROM posts
            WHERE did = %s
            GROUP BY did
            LIMIT 1
        """
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            self.safe_execute(cursor, query, (did,))
            result = cursor.fetchone()
            
            if result:
                return {
                    'likes': result[0] or 0,
                    'replies': result[1] or 0,
                    'quotes': result[2] or 0,
                    'reposts': result[3] or 0
                }
            return {'likes': 0, 'replies': 0, 'quotes': 0, 'reposts': 0}
    
    def get_user_by_did(self, did: str) -> Optional[Tuple]:
        """Get user information by DID."""
        query = "SELECT * FROM users WHERE did = %s"
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            self.safe_execute(cursor, query, (did,))
            return cursor.fetchone()
    
    def update_user_profile(self, profile: UserProfile) -> None:
        """Update user profile information."""
        query = """
            UPDATE users
            SET handle = %s, "displayName" = %s, avatar = %s
            WHERE did = %s
        """
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            self.safe_execute(cursor, query, (
                profile.handle,
                profile.display_name,
                profile.avatar,
                profile.did
            ))
            conn.commit()
    
    def upsert_snapshot(self, snapshot: SnapshotData) -> None:
        """Insert or update a user snapshot using atomic upsert."""
        # Use INSERT ... ON CONFLICT to atomically insert or update
        # This prevents race conditions when multiple threads process the same user/date
        upsert_query = """
            INSERT INTO snapshots 
            (uuid, followers, following, posts, date, did, likes, replies, quotes, reposts)
            VALUES (gen_random_uuid(), %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (did, date) DO UPDATE SET
                followers = EXCLUDED.followers,
                following = EXCLUDED.following,
                posts = EXCLUDED.posts,
                likes = EXCLUDED.likes,
                replies = EXCLUDED.replies,
                quotes = EXCLUDED.quotes,
                reposts = EXCLUDED.reposts
        """
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            self.safe_execute(cursor, upsert_query, (
                snapshot.followers, snapshot.following, snapshot.posts, snapshot.date,
                snapshot.did, snapshot.likes, snapshot.replies, snapshot.quotes, snapshot.reposts
            ))
            conn.commit()
    
    def create_snapshot_log(self) -> int:
        """Create a new snapshot log entry and return the log ID."""
        date = datetime.now(timezone.utc)
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Get next log ID
            self.safe_execute(cursor, "SELECT COUNT(*) FROM snapshot_logs")
            log_id = cursor.fetchone()[0] + 1
            
            # Insert log entry
            insert_query = """
                INSERT INTO snapshot_logs (status, time_started, time_completed, total_users, id)
                VALUES (%s, %s, %s, %s, %s)
            """
            self.safe_execute(cursor, insert_query, ('in_progress', date, date, 0, log_id))
            conn.commit()
            
            return log_id
    
    def update_snapshot_log(self, log_id: int, duration: float, total_users: int) -> None:
        """Update snapshot log with completion info."""
        date = datetime.now(timezone.utc)
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            update_query = """
                UPDATE snapshot_logs
                SET status = %s, time_completed = %s, duration = %s, total_users = %s
                WHERE id = %s
            """
            self.safe_execute(cursor, update_query, ('completed', date, duration, total_users, log_id))
            conn.commit()