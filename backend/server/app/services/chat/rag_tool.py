"""
FarmShield Chat — RAG Tool (Phase 6).

Builds or loads a FAISS vector index from the committed .md knowledge files.
The index is persisted via docker-compose.override.yml bind mount, so it
survives container restarts and only needs to be rebuilt when knowledge changes.

Key implementation notes:
- FAISS.from_documents() is synchronous. It is wrapped in asyncio.to_thread()
  to avoid blocking the FastAPI event loop during index build on first startup.
- Index build calls Gemini Embeddings API (10–30 s on first run). Logged clearly.
- FAISS.load_local() is also sync but fast (~100 ms) — not wrapped.

Correction from PRD verification (Q1): uses bind mount path from settings.
"""

import asyncio
from collections.abc import Callable
from pathlib import Path

import structlog
from langchain.tools import tool
from langchain_community.vectorstores import FAISS
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_text_splitters import CharacterTextSplitter
from langchain_community.document_loaders import TextLoader

logger = structlog.get_logger(__name__)

# Directory containing committed .md knowledge files (relative to this file)
_KNOWLEDGE_DIR = Path(__file__).parent / "knowledge"


class RagTool:
    """Encapsulates FAISS index lifecycle and exposes a LangChain tool."""

    def __init__(self) -> None:
        self._retriever = None
        self._ready = False

    async def load_or_build_index(self, settings) -> None:
        """
        Load the FAISS index from disk if it exists, otherwise build it.
        Must be awaited during app startup (inside lifespan).
        """
        index_path = Path(settings.faiss_index_path)
        embeddings = GoogleGenerativeAIEmbeddings(
            model=settings.gemini_embedding_model,
            google_api_key=settings.gemini_api_key,
        )

        if index_path.exists() and any(index_path.iterdir()):
            logger.info("faiss_index_loading_from_disk", path=str(index_path))
            vectorstore = FAISS.load_local(
                str(index_path),
                embeddings,
                allow_dangerous_deserialization=True,
            )
            logger.info("faiss_index_loaded")
        else:
            logger.info(
                "faiss_index_building_from_scratch",
                knowledge_dir=str(_KNOWLEDGE_DIR),
                note="Calling Gemini Embeddings API — this may take 10-30 s",
            )
            docs = self._load_knowledge_docs()
            chunks = CharacterTextSplitter(
                chunk_size=500, chunk_overlap=50
            ).split_documents(docs)
            logger.info("faiss_index_chunked", chunk_count=len(chunks))

            # FAISS.from_documents is sync — wrap to avoid blocking event loop
            vectorstore = await asyncio.to_thread(
                FAISS.from_documents, chunks, embeddings
            )

            index_path.mkdir(parents=True, exist_ok=True)
            vectorstore.save_local(str(index_path))
            logger.info("faiss_index_built_and_saved", path=str(index_path))

        self._retriever = vectorstore.as_retriever(search_kwargs={"k": 3})
        self._ready = True

    def get_tool(self) -> Callable:
        """Return the search_farming_knowledge LangChain tool."""
        retriever = self._retriever

        @tool
        def search_farming_knowledge(query: str) -> str:
            """
            Search the FarmShield agricultural knowledge base for general farming
            information. Use for questions about crop care, soil science, irrigation
            best practices, NPK nutrients, pH recommendations, and pest management.
            Do NOT use for current sensor readings — use the SQL tools for that.
            Input: a natural language question about farming or agriculture.
            Output: relevant text excerpts from the knowledge base.
            """
            if retriever is None:
                return "Knowledge base not ready. Please try again shortly."
            docs = retriever.invoke(query)
            if not docs:
                return "No relevant information found in the knowledge base."
            return "\n\n".join(d.page_content for d in docs)

        return search_farming_knowledge

    @staticmethod
    def _load_knowledge_docs() -> list:
        """Load all .md files from the knowledge directory."""
        md_files = sorted(_KNOWLEDGE_DIR.glob("*.md"))
        if not md_files:
            raise FileNotFoundError(
                f"No .md knowledge files found in {_KNOWLEDGE_DIR}. "
                "Cannot build FAISS index."
            )
        docs = []
        for path in md_files:
            loader = TextLoader(str(path), encoding="utf-8")
            docs.extend(loader.load())
            logger.debug("knowledge_file_loaded", file=path.name)
        logger.info("knowledge_docs_loaded", file_count=len(md_files), doc_count=len(docs))
        return docs
