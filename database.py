import os
import psycopg2
from psycopg2.extras import RealDictCursor
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)

class Database:
    def __init__(self):
        self.database_url = os.getenv('DATABASE_URL')
        if not self.database_url:
            raise ValueError("DATABASE_URL environment variable is not set!")
        
        # Fix for Render's postgres:// vs postgresql:// issue
        if self.database_url.startswith('postgres://'):
            self.database_url = self.database_url.replace('postgres://', 'postgresql://', 1)
        
        self._create_tables()
    
    def get_connection(self):
        """Get database connection"""
        return psycopg2.connect(self.database_url, cursor_factory=RealDictCursor)
    
    def _create_tables(self):
        """Create necessary tables if they don't exist"""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        user_id BIGINT PRIMARY KEY,
                        first_name VARCHAR(255) NOT NULL,
                        last_name VARCHAR(255) NOT NULL,
                        username VARCHAR(255),
                        approved BOOLEAN DEFAULT FALSE,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                conn.commit()
        logger.info("Database tables created/verified")
    
    def add_user(self, user_id: int, first_name: str, last_name: str, username: Optional[str] = None):
        """Add a new user to the database"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO users (user_id, first_name, last_name, username, approved)
                        VALUES (%s, %s, %s, %s, FALSE)
                        ON CONFLICT (user_id) DO NOTHING
                        """,
                        (user_id, first_name, last_name, username)
                    )
                    conn.commit()
            logger.info(f"User {user_id} ({first_name} {last_name}) added to database")
        except Exception as e:
            logger.error(f"Error adding user: {e}")
            raise
    
    def get_user(self, user_id: int) -> Optional[Dict]:
        """Get user by ID"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT * FROM users WHERE user_id = %s",
                        (user_id,)
                    )
                    return cur.fetchone()
        except Exception as e:
            logger.error(f"Error getting user: {e}")
            return None
    
    def approve_user(self, user_id: int):
        """Approve a user"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE users SET approved = TRUE WHERE user_id = %s",
                        (user_id,)
                    )
                    conn.commit()
            logger.info(f"User {user_id} approved")
        except Exception as e:
            logger.error(f"Error approving user: {e}")
            raise
    
    def delete_user(self, user_id: int):
        """Delete a user"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "DELETE FROM users WHERE user_id = %s",
                        (user_id,)
                    )
                    conn.commit()
            logger.info(f"User {user_id} deleted")
        except Exception as e:
            logger.error(f"Error deleting user: {e}")
            raise
    
    def get_approved_users(self, exclude_user_id: Optional[int] = None) -> List[Dict]:
        """Get all approved users, optionally excluding one user"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    if exclude_user_id:
                        cur.execute(
                            """
                            SELECT * FROM users 
                            WHERE approved = TRUE AND user_id != %s
                            ORDER BY first_name, last_name
                            """,
                            (exclude_user_id,)
                        )
                    else:
                        cur.execute(
                            """
                            SELECT * FROM users 
                            WHERE approved = TRUE
                            ORDER BY first_name, last_name
                            """
                        )
                    return cur.fetchall()
        except Exception as e:
            logger.error(f"Error getting approved users: {e}")
            return []
    
    def get_total_users(self) -> int:
        """Get total number of users"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT COUNT(*) as count FROM users")
                    result = cur.fetchone()
                    return result['count'] if result else 0
        except Exception as e:
            logger.error(f"Error getting total users: {e}")
            return 0
    
    def get_approved_count(self) -> int:
        """Get number of approved users"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT COUNT(*) as count FROM users WHERE approved = TRUE")
                    result = cur.fetchone()
                    return result['count'] if result else 0
        except Exception as e:
            logger.error(f"Error getting approved count: {e}")
            return 0
