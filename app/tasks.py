from celery import current_task
from app.celery_app import celery
from src.memoria.writer import MemoryWriter
from src.memoria.embeddings import EmbeddingService
from src.memoria.config import Config
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

@celery.task(bind=True, max_retries=3)
def process_memory_async(self, user_id: str, conversation_id: str, message_content: str, metadata: Optional[Dict[str, Any]] = None):
    """Process memory extraction and storage asynchronously"""
    try:
        logger.info(f"Processing memory for user {user_id}, conversation {conversation_id}")
        
        # Initialize services
        writer = MemoryWriter()
        embedding_service = EmbeddingService()
        
        # Extract memory
        memory = writer.extract_memory(
            user_id=user_id,
            conversation_id=conversation_id,
            message_content=message_content,
            metadata=metadata or {}
        )
        
        if not memory:
            logger.warning(f"No memory extracted for user {user_id}")
            return {"status": "no_memory", "message": "No memory extracted"}
        
        # Generate embedding
        embedding = embedding_service.generate_embedding(memory.content)
        
        # Store in database
        memory_id = writer.store_memory(memory, embedding)
        
        # Update user summary
        writer.update_user_summary(user_id)
        
        logger.info(f"Memory processed successfully: {memory_id}")
        return {
            "status": "success", 
            "memory_id": memory_id,
            "memory_type": memory.memory_type,
            "content_preview": memory.content[:100] + "..." if len(memory.content) > 100 else memory.content
        }
        
    except Exception as exc:
        logger.error(f"Memory processing failed: {str(exc)}", exc_info=True)
        # Exponential backoff: 60s, 120s, 240s
        countdown = 60 * (2 ** self.request.retries)
        raise self.retry(exc=exc, countdown=countdown)

@celery.task(bind=True, max_retries=3)
def correct_memory_async(self, user_id: str, memory_id: str, replacement_text: str):
    """Correct a memory asynchronously"""
    try:
        logger.info(f"Correcting memory {memory_id} for user {user_id}")
        
        # Initialize services
        writer = MemoryWriter()
        embedding_service = EmbeddingService()
        
        # Mark memory as bad
        writer.db.mark_memory_bad(user_id, memory_id)
        
        # Generate embedding for replacement text
        embedding = embedding_service.generate_embedding(replacement_text)
        
        # Store corrected memory
        new_memory_id = writer.db.add_memory(
            user_id=user_id,
            conversation_id=None,
            text=replacement_text,
            embedding=embedding,
            type_="correction",
            importance=0.6,
            confidence=0.9,
            provenance={"source": "correction", "replaces": memory_id},
        )
        
        logger.info(f"Memory corrected successfully: {new_memory_id}")
        return {
            "status": "success",
            "original_memory_id": memory_id,
            "new_memory_id": new_memory_id,
            "content_preview": replacement_text[:100] + "..." if len(replacement_text) > 100 else replacement_text
        }
        
    except Exception as exc:
        logger.error(f"Memory correction failed: {str(exc)}", exc_info=True)
        # Exponential backoff: 60s, 120s, 240s
        countdown = 60 * (2 ** self.request.retries)
        raise self.retry(exc=exc, countdown=countdown)

@celery.task(bind=True, max_retries=2)
def batch_process_embeddings(self, memory_batch: list):
    """Process multiple embeddings in batch for efficiency"""
    try:
        embedding_service = EmbeddingService()
        results = []
        
        for memory_data in memory_batch:
            embedding = embedding_service.generate_embedding(
                memory_data['content']
            )
            results.append({
                'memory_id': memory_data['id'],
                'embedding': embedding
            })
        
        return {
            "status": "success", 
            "processed": len(results),
            "results": results
        }
        
    except Exception as exc:
        logger.error(f"Batch processing failed: {str(exc)}", exc_info=True)
        raise self.retry(exc=exc, countdown=120)

@celery.task(bind=True)
def update_user_summary_async(self, user_id: str):
    """Update user summary asynchronously"""
    try:
        writer = MemoryWriter()
        writer.update_user_summary(user_id)
        return {"status": "success", "user_id": user_id}
        
    except Exception as exc:
        logger.error(f"Summary update failed: {str(exc)}", exc_info=True)
        raise self.retry(exc=exc, countdown=300)

@celery.task(bind=True)
def generate_insights_async(self, user_id: str):
    """Generate insights asynchronously"""
    try:
        writer = MemoryWriter()
        insights = writer.generate_insights(user_id)
        return {
            "status": "success", 
            "user_id": user_id,
            "insights_count": len(insights)
        }
        
    except Exception as exc:
        logger.error(f"Insight generation failed: {str(exc)}", exc_info=True)
        raise self.retry(exc=exc, countdown=600)