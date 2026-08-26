"""
RAG 知识库服务

文档上传 → 切分 → Embedding → 存入数据库 → 内存 FAISS 检索

切片和向量存储在 knowledge_chunks 表中，文档全量内容存储在 knowledge_docs 表中。
按 project_id 维护内存 FAISS 索引缓存，增删文档后自动失效重建。
"""
import json
import logging
import os
import threading
from typing import List, Dict, Any, Optional, Tuple

import numpy as np

# 强制离线模式：模型已在本地缓存，避免每次加载时访问 HuggingFace 网络检查更新（网络不通时会卡死超时）
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

logger = logging.getLogger(__name__)

# FAISS 和 sentence-transformers 延迟导入
_faiss = None
_model = None


def _get_faiss():
    global _faiss
    if _faiss is None:
        import faiss
        _faiss = faiss
    return _faiss


def _get_embedding_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        # local_files_only 从本地缓存加载，不走网络，首次加载从分钟级降到秒级
        _model = SentenceTransformer(
            "paraphrase-multilingual-MiniLM-L12-v2", local_files_only=True
        )
    return _model


class KnowledgeBaseService:
    """知识库服务（数据库存储切片 + 内存 FAISS 缓存）"""

    # 默认切片参数
    DEFAULT_CHUNK_SIZE = 500
    DEFAULT_CHUNK_OVERLAP = 50

    def __init__(self):
        # 按 project_id 缓存 FAISS 索引和 chunk 元数据
        self._index_cache: Dict[int, Dict[str, Any]] = {}
        self._cache_lock = threading.Lock()

    def split_text(
        self,
        text: str,
        chunk_size: int = 500,
        chunk_overlap: int = 50,
    ) -> List[str]:
        """文本切分（按字符数，在句号/换行处断句）"""
        if not text.strip():
            return []

        chunks = []
        start = 0
        text_len = len(text)

        while start < text_len:
            end = min(start + chunk_size, text_len)

            if end < text_len:
                search_end = max(start + chunk_size // 2, end - 100)
                for i in range(end, search_end, -1):
                    if text[i - 1] in "。！？\n":
                        end = i
                        break

            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)

            start = end - chunk_overlap if end < text_len else end
            if start >= text_len:
                break

        return chunks

    def _invalidate_cache(self, project_id: int):
        """使某个项目的 FAISS 缓存失效"""
        with self._cache_lock:
            self._index_cache.pop(project_id, None)

    def _build_index(self, db, project_id: int) -> Optional[Dict[str, Any]]:
        """从数据库加载切片向量，构建内存 FAISS 索引"""
        from app.models.knowledge_doc import KnowledgeChunk

        chunks = db.query(KnowledgeChunk).filter(
            KnowledgeChunk.project_id == project_id
        ).all()

        if not chunks:
            return None

        # 收集有效向量
        vectors = []
        chunk_meta = []
        for c in chunks:
            if c.embedding:
                vectors.append(c.embedding)
                chunk_meta.append({
                    "chunk_id": c.id,
                    "doc_id": c.doc_id,
                    "chunk_index": c.chunk_index,
                    "content": c.content,
                    "token_count": c.token_count,
                })

        if not vectors:
            return None

        vectors_np = np.array(vectors, dtype=np.float32)
        dimension = vectors_np.shape[1]
        faiss = _get_faiss()
        index = faiss.IndexFlatL2(dimension)
        index.add(vectors_np)

        return {"index": index, "chunks": chunk_meta}

    def _get_index(self, db, project_id: int) -> Optional[Dict[str, Any]]:
        """获取项目的 FAISS 索引（带缓存）"""
        with self._cache_lock:
            if project_id in self._index_cache:
                return self._index_cache[project_id]

        # 缓存未命中，构建
        result = self._build_index(db, project_id)
        with self._cache_lock:
            self._index_cache[project_id] = result
        return result

    def warmup(self, db, project_ids: List[int]):
        """预热：预加载 Embedding 模型并构建指定项目的 FAISS 索引，避免首次检索卡顿"""
        import time
        start = time.time()
        try:
            _get_embedding_model()
            logger.info(f"知识库 Embedding 模型预加载完成，耗时 {time.time() - start:.1f}s")
        except Exception as e:
            logger.warning(f"知识库 Embedding 模型预加载失败: {e}")
            return
        for pid in project_ids:
            try:
                self._get_index(db, pid)
            except Exception as e:
                logger.warning(f"知识库项目 {pid} 索引预热失败: {e}")

    def add_document(
        self,
        db,
        project_id: int,
        doc_id: int,
        title: str,
        content: str,
        chunk_size: int = None,
        chunk_overlap: int = None,
    ) -> Dict[str, Any]:
        """
        添加文档到知识库：切分 → 向量化 → 存入数据库

        Args:
            db: 数据库会话
            project_id: 项目ID
            doc_id: 文档ID
            title: 文档标题
            content: 文档内容
            chunk_size: 切片大小
            chunk_overlap: 重叠大小

        Returns:
            处理结果
        """
        try:
            from app.models.knowledge_doc import KnowledgeChunk, KnowledgeDoc

            cs = chunk_size or self.DEFAULT_CHUNK_SIZE
            co = chunk_overlap or self.DEFAULT_CHUNK_OVERLAP

            # 1. 切分
            chunks = self.split_text(content, chunk_size=cs, chunk_overlap=co)
            if not chunks:
                return {"success": False, "error": "文档内容为空", "chunk_count": 0}

            # 2. 生成 Embedding
            model = _get_embedding_model()
            embeddings = model.encode(chunks, show_progress_bar=False)

            # 3. 删除旧切片（如有）
            db.query(KnowledgeChunk).filter(
                KnowledgeChunk.doc_id == doc_id
            ).delete()

            # 4. 存入数据库
            for i, chunk in enumerate(chunks):
                emb = embeddings[i]
                db_chunk = KnowledgeChunk(
                    doc_id=doc_id,
                    project_id=project_id,
                    chunk_index=i,
                    content=chunk,
                    token_count=len(chunk),
                    embedding=emb.tolist() if hasattr(emb, "tolist") else list(emb),
                )
                db.add(db_chunk)

            # 5. 更新文档切片数和策略
            doc = db.query(KnowledgeDoc).filter(KnowledgeDoc.id == doc_id).first()
            if doc:
                doc.chunk_count = len(chunks)
                doc.chunk_strategy = "fixed"
                doc.chunk_size = cs
                doc.overlap = co
                doc.status = "ready"

            db.commit()

            # 6. 使缓存失效
            self._invalidate_cache(project_id)

            return {
                "success": True,
                "chunk_count": len(chunks),
            }

        except Exception as e:
            db.rollback()
            logger.error(f"添加文档到知识库失败: {e}")
            return {"success": False, "error": str(e), "chunk_count": 0}

    def search(
        self,
        db,
        project_id: int,
        query: str,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        检索相关文档块

        Args:
            db: 数据库会话
            project_id: 项目ID
            query: 查询文本
            top_k: 返回数量

        Returns:
            相关文档块列表
        """
        try:
            cached = self._get_index(db, project_id)
            if not cached:
                return []

            index = cached["index"]
            chunk_meta = cached["chunks"]

            # 生成查询向量
            model = _get_embedding_model()
            query_vector = model.encode([query], show_progress_bar=False)

            # 检索
            distances, indices = index.search(
                np.array(query_vector, dtype=np.float32), min(top_k, len(chunk_meta))
            )

            # 组装结果
            results = []
            for i, idx in enumerate(indices[0]):
                if 0 <= idx < len(chunk_meta):
                    chunk = chunk_meta[idx]
                    results.append({
                        "doc_id": chunk["doc_id"],
                        "chunk_id": chunk["chunk_id"],
                        "title": "",
                        "content": chunk["content"],
                        "chunk_index": chunk["chunk_index"],
                        "score": float(distances[0][i]),
                        "similarity": float(1 / (1 + distances[0][i])),
                    })

            # 补充文档标题
            if results:
                from app.models.knowledge_doc import KnowledgeDoc
                doc_ids = set(r["doc_id"] for r in results)
                docs = db.query(KnowledgeDoc).filter(KnowledgeDoc.id.in_(doc_ids)).all()
                title_map = {d.id: d.title for d in docs}
                for r in results:
                    r["title"] = title_map.get(r["doc_id"], "")

            return results

        except Exception as e:
            logger.error(f"知识库检索失败: {e}")
            return []

    def delete_document(self, db, project_id: int, doc_id: int) -> Dict[str, Any]:
        """
        删除文档的所有切片

        Args:
            db: 数据库会话
            project_id: 项目ID
            doc_id: 文档ID

        Returns:
            删除结果
        """
        try:
            from app.models.knowledge_doc import KnowledgeChunk

            deleted = db.query(KnowledgeChunk).filter(
                KnowledgeChunk.doc_id == doc_id
            ).delete()
            db.commit()

            # 使缓存失效
            self._invalidate_cache(project_id)

            return {"success": True, "deleted_chunks": deleted}

        except Exception as e:
            db.rollback()
            logger.error(f"删除知识库文档失败: {e}")
            return {"success": False, "error": str(e)}

    def get_stats(self, db, project_id: int) -> Dict[str, Any]:
        """获取知识库统计信息"""
        try:
            from app.models.knowledge_doc import KnowledgeDoc, KnowledgeChunk

            total_docs = db.query(KnowledgeDoc).filter(
                KnowledgeDoc.project_id == project_id,
                KnowledgeDoc.is_deleted == False,
            ).count()

            total_chunks = db.query(KnowledgeChunk).filter(
                KnowledgeChunk.project_id == project_id
            ).count()

            return {
                "total_docs": total_docs,
                "total_chunks": total_chunks,
            }

        except Exception as e:
            logger.error(f"获取知识库统计失败: {e}")
            return {"total_docs": 0, "total_chunks": 0}


# 全局单例
knowledge_base_service = KnowledgeBaseService()
