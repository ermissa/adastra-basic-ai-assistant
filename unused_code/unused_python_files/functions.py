import os
import time
import json
import math
import asyncio
import pandas as pd
from datetime import datetime, timezone, timedelta
from decimal import Decimal
import pytz
from openai import OpenAI
from google.oauth2 import service_account
from googleapiclient.discovery import build
import dateutil.parser
import dropbox
from dotenv import load_dotenv
from utils.db import VectorDB
from utils.logger import Logger

# Load environment variables
load_dotenv()

class Functions:
    SERVICE_ACCOUNT_FILE = '.credentials.json'
    CALENDAR_ID = 'adastraaicenter@gmail.com'
    AMSTERDAM_TZ = pytz.timezone("Europe/Amsterdam")
    SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']
    MEETING_DURATION_MIN = 30
    WORK_START_HOUR = 9
    WORK_END_HOUR = 17
    
    EMBEDDING_MODEL = "text-embedding-3-small"
    COMPLETION_MODEL = "gpt-4-turbo-preview"
    PRODUCTS_FILE = "products.csv"
    
    def __init__(self):
        # Initialize OpenAI client
        self.openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        
        # Initialize Dropbox client
        self.dbx = dropbox.Dropbox(os.getenv('DROPBOX_ACCESS_TOKEN'))
        
        # Initialize Google Calendar credentials
        self.credentials = service_account.Credentials.from_service_account_file(
            self.SERVICE_ACCOUNT_FILE, 
            scopes=self.SCOPES + ['https://www.googleapis.com/auth/calendar.events']
        )
        self.calendar_service = build('calendar', 'v3', credentials=self.credentials)
        self.logger = Logger()
        # Initialize Vector DB
        self.vector_db = VectorDB(os.getenv('DATABASE_URL'))
        
    async def initialize(self):
        """Initialize vector database and load product embeddings"""
        start_time = time.time()
        
        # Initialize vector database
        await self.vector_db.initialize()
        
        try:
            # Load and process products
            df = pd.read_csv(self.PRODUCTS_FILE)
            products = df.to_dict('records')
            
            # Create text representations for embedding
            texts = [
                f"Product: {p['name']}\n"
                f"Description: {p.get('description', '')}\n"
                f"Price: ${p.get('price', 0)}\n"
                f"Warranty: {p.get('warranty', '')}\n"
                f"Specifications: {json.dumps(p.get('specifications', {}))}"
                for p in products
            ]
            
            # Get embeddings in batches
            batch_size = 100
            all_embeddings = []
            
            for i in range(0, len(texts), batch_size):
                batch = texts[i:i + batch_size]
                response = self.openai_client.embeddings.create(
                    model=self.EMBEDDING_MODEL,
                    input=batch
                )
                batch_embeddings = [e.embedding for e in response.data]
                all_embeddings.extend(batch_embeddings)
                
                self.logger.info(message=f"Embedded batch {i//batch_size + 1}/{math.ceil(len(texts)/batch_size)}", 
                          category="Embedding")
            
            # Store products and embeddings
            await self.vector_db.store_embeddings(products, all_embeddings)
            
            elapsed = time.time() - start_time
            self.logger.info(message=f"Embedding process completed in {elapsed:.2f} seconds", category="Embedding")
            
        except Exception as e:
            self.logger.error(message=f"Failed to initialize product embeddings: {str(e)}", category="Embedding")
            raise

    async def get_battery_info(self, question: str, phone_number: str = None) -> str:
        """Get battery information using RAG"""
        try:
            # Get question embedding
            response = self.openai_client.embeddings.create(
                model=self.EMBEDDING_MODEL,
                input=question
            )
            query_embedding = response.data[0].embedding
            
            # Search similar products
            results = await self.vector_db.search_similar(query_embedding, limit=3)
            
            if not results:
                return "I apologize, but I couldn't find any relevant battery information for your question."
            
            # Build context from results
            context = "Available battery products:\n\n" + "\n\n".join([
                f"Product: {r['name']}\n"
                f"Description: {r['description']}\n"
                f"Price: ${r['price']}\n"
                f"Warranty: {r['warranty']}\n"
                f"Specifications: {json.dumps(r['specifications'])}"
                for r in results
            ])
            
            # Generate response using completion API
            prompt = f"""You are a helpful battery expert. Answer the user's question using ONLY the information provided in the context below. 
                    If you cannot answer the question using the provided context, say so.
                    Be concise and direct in your response.

                    Context:
                    {context}

                    Question: {question}

                    Answer:"""
            
            response = self.openai_client.chat.completions.create(
                model=self.COMPLETION_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=200
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            self.logger.error(message=f"Error in RAG pipeline: {str(e)}", category="RAG")
            raise

    # ... [rest of the existing calendar-related methods] ... 