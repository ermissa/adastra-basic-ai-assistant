import logging
import os
import time
import asyncio
import asyncpg
import numpy as np
import pandas as pd
from typing import List, Dict, Any, Optional
from .logger import Logger

logger = logging.getLogger(__name__)

class VectorDB:
    def __init__(self, dsn: Optional[str] = None):
        self.dsn = dsn
        self.pool = None

    async def connect_to_db(self) -> str:
        """Create database connection string from environment variables or use default docker-compose values"""
        # Default values from docker-compose
        DB_CONFIG = {
            'user': os.getenv('POSTGRES_USER', 'postgres'),
            'password': os.getenv('POSTGRES_PASSWORD', '123456'),
            'host': os.getenv('POSTGRES_HOST', '127.0.0.1'),
            'port': os.getenv('POSTGRES_PORT', '5432'),
            'database': os.getenv('POSTGRES_DB', 'adastradb')
        }
        
        try:
            # Test connection
            dsn = f"postgresql://{DB_CONFIG['user']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}"
            conn = await asyncpg.connect(dsn)
            await conn.close()
            
            logger.info("Successfully tested database connection")
            return dsn
            
        except Exception as e:
            logger.error(f"Failed to connect to database: {str(e)}")
            raise



    async def initialize(self):
        """Initialize database connection pool and create necessary extensions/tables"""
        try:
            # Get connection string if not provided
            if not self.dsn:
                self.dsn = await self.connect_to_db()
            
            # Create connection pool
            self.pool = await asyncpg.create_pool(self.dsn)
            
            # Initialize vector extension and create table
            async with self.pool.acquire() as conn:
                # Create pgvector extension if it doesn't exist
                await conn.execute('CREATE EXTENSION IF NOT EXISTS vector;')
                
                # Create products table with vector support
                await conn.execute('''
                    CREATE TABLE IF NOT EXISTS products (
                        id SERIAL PRIMARY KEY,
                        name TEXT UNIQUE,
                        description TEXT,
                        price DECIMAL,
                        warranty TEXT,
                        specifications TEXT,
                        embedding vector(1536),
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                    );
                ''')
                
                # Create vector index for similarity search
                await conn.execute('''
                    CREATE INDEX IF NOT EXISTS products_embedding_idx 
                    ON products 
                    USING ivfflat (embedding vector_cosine_ops)
                    WITH (lists = 100);
                ''')
                
            logger.info(message="Vector database initialized successfully")
            
        except Exception as e:
            logger.error(message=f"Failed to initialize vector database: {str(e)}")
            raise


    async def store_embeddings(self, products: List[Dict[str, Any]], embeddings: List[List[float]]):
        """Store product data and their embeddings"""
        if len(products) != len(embeddings):
            logger.error("Products and embeddings count mismatch")
            raise ValueError("Products and embeddings list must be the same length")

        try:
            async with self.pool.acquire() as conn:
                await conn.executemany('''
                    INSERT INTO products (name, description, price, warranty, specifications, embedding)
                    VALUES ($1, $2, $3, $4, $5, $6)
                    ON CONFLICT (name) DO UPDATE 
                    SET description = $2, price = $3, warranty = $4, specifications = $5, embedding = $6;
                ''', [
                    (
                        product['name'],
                        product.get('description', ''),
                        float(product.get('price', 0)),
                        product.get('warranty', ''),
                        product.get('specifications', {}),
                        f"[{', '.join(map(str, embedding))}]"  # Convert list to string for storage
                    )
                    for product, embedding in zip(products, embeddings)
                ])

            logger.info(f"Stored {len(products)} products with embeddings")

        except Exception as e:
            import traceback
            logger.error(f"Failed to store embeddings:\n{traceback.format_exc()}")
            raise    

    async def search_similar(self, query_embedding: List[float], limit: int = 3) -> List[Dict[str, Any]]:
        """Search for similar products using vector similarity"""
        try:
            async with self.pool.acquire() as conn:
                # Perform similarity search
                rows = await conn.fetch('''
                    SELECT 
                        name, description, price, warranty, specifications,
                        1 - (embedding <=> $1) as similarity
                    FROM products
                    ORDER BY embedding <=> $1
                    LIMIT $2;
                ''', query_embedding, limit)
                
                # Convert to list of dicts
                results = [
                    {
                        'name': row['name'],
                        'description': row['description'],
                        'price': float(row['price']),
                        'warranty': row['warranty'],
                        'specifications': row['specifications'],
                        'similarity': row['similarity']
                    }
                    for row in rows
                ]
                
                return results
                
        except Exception as e:
            logger.error(message=f"Failed to search similar products: {str(e)}")
            raise

    async def close(self):
        """Close database connection pool"""
        if self.pool:
            await self.pool.close() 