"""
RAG Service for Clinic Information Retrieval
This module handles loading clinic data, creating embeddings, and querying the knowledge base.
"""

import os  # ADD THIS LINE
from typing import Optional
from pathlib import Path

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import TextLoader
from langchain_community.vectorstores import FAISS
from langchain_openai import AzureOpenAIEmbeddings
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Azure OpenAI Configuration
AZURE_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_EMBEDDING_DEPLOYMENT = os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-3-small")
AZURE_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-01")

class ClinicRAGService:
    """
    Service class to handle RAG operations for clinic information.
    Uses FAISS for vector storage and Azure OpenAI for embeddings.
    """
    
    def __init__(self, knowledge_file: str = "clinic_data.txt", vector_store_path: str = "./faiss_index"):
        """
        Initialize the RAG service.
        
        Args:
            knowledge_file: Path to the clinic information text file
            vector_store_path: Path to save/load FAISS index
        """
        self.knowledge_file = knowledge_file
        self.vector_store_path = vector_store_path
        self.vectorstore: Optional[FAISS] = None
        
        # Initialize Azure OpenAI Embeddings
        self.embeddings = AzureOpenAIEmbeddings(
            azure_endpoint=AZURE_ENDPOINT,
            api_key=AZURE_API_KEY,
            azure_deployment=AZURE_EMBEDDING_DEPLOYMENT,
            api_version=AZURE_API_VERSION,
        )
        
        # Load or create vector store
        self._initialize_vectorstore()
    
    def _initialize_vectorstore(self):
        """
        Initialize or load the FAISS vector store.
        If index exists, load it. Otherwise, create a new one.
        """
        try:
            # Check if FAISS index already exists
            if Path(self.vector_store_path).exists():
                print("Loading existing FAISS index...")
                self.vectorstore = FAISS.load_local(
                    self.vector_store_path, 
                    self.embeddings,
                    allow_dangerous_deserialization=True
                )
                print("✅ FAISS index loaded successfully!")
            else:
                print("Creating new FAISS index from knowledge base...")
                self._create_vectorstore()
                print("✅ FAISS index created and saved!")
        
        except Exception as e:
            print(f"❌ Error initializing vector store: {e}")
            raise
    
    def _create_vectorstore(self):
        """
        Create a new FAISS vector store from the knowledge base file.
        Steps:
        1. Load the text file
        2. Split into chunks
        3. Create embeddings
        4. Store in FAISS
        5. Save to disk
        """
        try:
            # Step 1: Load the knowledge base file
            if not Path(self.knowledge_file).exists():
                raise FileNotFoundError(f"Knowledge base file not found: {self.knowledge_file}")
            
            loader = TextLoader(self.knowledge_file, encoding='utf-8')
            documents = loader.load()
            
            # Step 2: Split text into chunks
            # chunk_size: Maximum characters per chunk
            # chunk_overlap: Overlap between chunks to maintain context
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=500,  # Smaller chunks for more precise retrieval
                chunk_overlap=50,
                length_function=len,
                separators=["\n\n", "\n", ".", "!", "?", ",", " ", ""]
            )
            
            chunks = text_splitter.split_documents(documents)
            print(f"📄 Split knowledge base into {len(chunks)} chunks")
            
            # Step 3 & 4: Create embeddings and store in FAISS
            self.vectorstore = FAISS.from_documents(
                documents=chunks,
                embedding=self.embeddings
            )
            
            # Step 5: Save to disk for future use
            self.vectorstore.save_local(self.vector_store_path)
            
        except Exception as e:
            print(f"❌ Error creating vector store: {e}")
            raise
    
    def query_knowledge_base(self, query: str, k: int = 3) -> str:
        """
        Query the knowledge base and return relevant information.
        
        Args:
            query: User's question about the clinic
            k: Number of relevant chunks to retrieve
            
        Returns:
            Combined text from the most relevant chunks
        """
        try:
            if not self.vectorstore:
                raise ValueError("Vector store not initialized")
            
            # Perform similarity search
            relevant_docs = self.vectorstore.similarity_search(query, k=k)
            
            # Combine relevant chunks into a single context
            context = "\n\n".join([doc.page_content for doc in relevant_docs])
            
            return context
        
        except Exception as e:
            print(f"❌ Error querying knowledge base: {e}")
            return f"Error retrieving information: {str(e)}"
    
    def refresh_vectorstore(self):
        """
        Refresh the vector store by recreating it from the knowledge base.
        Useful when the clinic_data.txt file is updated.
        """
        try:
            print("🔄 Refreshing vector store...")
            
            # Delete existing index
            if Path(self.vector_store_path).exists():
                import shutil
                shutil.rmtree(self.vector_store_path)
            
            # Recreate
            self._create_vectorstore()
            print("✅ Vector store refreshed successfully!")
        
        except Exception as e:
            print(f"❌ Error refreshing vector store: {e}")
            raise


# Global instance (singleton pattern)
rag_service: Optional[ClinicRAGService] = None

def get_rag_service() -> ClinicRAGService:
    """
    Get or create the global RAG service instance.
    This ensures we only load the vector store once.
    """
    global rag_service
    if rag_service is None:
        rag_service = ClinicRAGService()
    return rag_service


# Test function
if __name__ == "__main__":
    # Test the RAG service
    service = ClinicRAGService()
    
    # Test queries
    test_queries = [
        "What are the consultation fees?",
        "Which insurance plans do you accept?",
        "What are Dr. Sarah Johnson's timings?",
        "How do I cancel an appointment?",
        "Is parking available?"
    ]
    
    for query in test_queries:
        print(f"\n🔍 Query: {query}")
        result = service.query_knowledge_base(query)
        print(f"📝 Answer:\n{result}\n{'-'*80}")