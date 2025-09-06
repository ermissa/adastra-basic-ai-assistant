import os
from langchain_postgres import PGVector
from langchain_openai import ChatOpenAI , OpenAIEmbeddings
from langchain.chains import RetrievalQA
from langchain.schema import Document

class LangChainBatteryExpert:
    def __init__(self):
        DB_CONFIG = {
            'user': os.getenv('POSTGRES_USER', 'postgres'),
            'password': os.getenv('POSTGRES_PASSWORD', '123456'),
            'host': os.getenv('POSTGRES_HOST', '127.0.0.1'),
            'port': os.getenv('POSTGRES_PORT', '5432'),
            'database': os.getenv('POSTGRES_DB', 'adastradb')
        }
        db_connection_string = f"postgresql://{DB_CONFIG['user']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}"

        # EMBEDDING_MODEL = "text-embedding-ada-002"
        EMBEDDING_MODEL = "text-embedding-3-small"
        self.embedding_model = OpenAIEmbeddings(model=EMBEDDING_MODEL)
        self.vector_store = PGVector(
            collection_name="products",
            connection=db_connection_string,
            embeddings=self.embedding_model
        )
        self.llm = ChatOpenAI(
            model="gpt-4", temperature=0.7, max_tokens=200
        )
        self.qa_chain = RetrievalQA.from_chain_type(
            llm=self.llm,
            retriever=self.vector_store.as_retriever(search_kwargs={"k": 3}),
            chain_type="stuff",
            return_source_documents=False
        )

    async def get_battery_info(self, question: str) -> str:
        try:
            # Run the RAG pipeline via Langchain
            response = self.qa_chain.invoke(question)
            return response
        except Exception as e:
            # log if you have a logger
            print(f"[RAG ERROR] {str(e)}")
            raise
