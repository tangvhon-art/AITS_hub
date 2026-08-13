"""
RAG 知识库服务

文档上传 → 切分 → Embedding → FAISS 存储 → 检索
"""
import os
import json
import logging
import pickle
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime

import numpy as np

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
        # 使用轻量中文模型
        _model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
    return _model


class KnowledgeBaseService:
    """知识库服务"""

    def __init__(self, storage_dir: str = "data/knowledge_base"):
        self.storage_dir = storage_dir
        os.makedirs(storage_dir, exist_ok=True)

    def _get_project_dir(self, project_id: int) -> str:
        """获取项目知识库目录"""
        project_dir = os.path.join(self.storage_dir, f"project_{project_id}")
        os.makedirs(project_dir, exist_ok=True)
        return project_dir

    def _get_index_path(self, project_id: int) -> str:
        return os.path.join(self._get_project_dir(project_id), "faiss.index")

    def _get_chunks_path(self, project_id: int) -> str:
        return os.path.join(self._get_project_dir(project_id), "chunks.json")

    def split_text(
        self,
        text: str,
        chunk_size: int = 500,
        chunk_overlap: int = 50,
    ) -> List[str]:
        """
        文本切分

        Args:
            text: 原始文本
            chunk_size: 每块大小（字符数）
            chunk_overlap: 重叠大小

        Returns:
            文本块列表
        """
        if not text.strip():
            return []

        chunks = []
        start = 0
        text_len = len(text)

        while start < text_len:
            end = min(start + chunk_size, text_len)

            # 尝试在句号、换行处切分
            if end < text_len:
                # 向前找最近的句号或换行
                search_end = max(start + chunk_size // 2, end - 100)
                for i in range(end, search_end, -1):
                    if text[i-1] in "。！？\n":
                        end = i
                        break

            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)

            start = end - chunk_overlap if end < text_len else end
            if start >= text_len:
                break

        return chunks

    def add_document(
        self,
        project_id: int,
        doc_id: int,
        title: str,
        content: str,
    ) -> Dict[str, Any]:
        """
        添加文档到知识库

        Args:
            project_id: 项目ID
            doc_id: 文档ID
            title: 文档标题
            content: 文档内容

        Returns:
            处理结果
        """
        try:
            # 1. 切分
            chunks = self.split_text(content)
            if not chunks:
                return {"success": False, "error": "文档内容为空", "chunk_count": 0}

            # 2. 生成 Embedding
            model = _get_embedding_model()
            embeddings = model.encode(chunks, show_progress_bar=False)

            # 3. 加载或创建 FAISS 索引
            faiss = _get_faiss()
            index_path = self._get_index_path(project_id)
            chunks_path = self._get_chunks_path(project_id)

            dimension = embeddings.shape[1]
            if os.path.exists(index_path):
                index = faiss.read_index(index_path)
                # 加载现有 chunks
                with open(chunks_path, "r", encoding="utf-8") as f:
                    all_chunks = json.load(f)
            else:
                index = faiss.IndexFlatL2(dimension)
                all_chunks = []

            # 4. 添加向量
            index.add(np.array(embeddings, dtype=np.float32))

            # 5. 保存 chunk 元数据
            for i, chunk in enumerate(chunks):
                all_chunks.append({
                    "doc_id": doc_id,
                    "title": title,
                    "content": chunk,
                    "chunk_index": i,
                    "added_at": china_now_naive().isoformat(),
                })

            # 6. 保存
            faiss.write_index(index, index_path)
            with open(chunks_path, "w", encoding="utf-8") as f:
                json.dump(all_chunks, f, ensure_ascii=False, indent=2)

            return {
                "success": True,
                "chunk_count": len(chunks),
                "total_chunks": len(all_chunks),
            }

        except Exception as e:
            logger.error(f"添加文档到知识库失败: {e}")
            return {"success": False, "error": str(e), "chunk_count": 0}

    def search(
        self,
        project_id: int,
        query: str,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        检索相关文档

        Args:
            project_id: 项目ID
            query: 查询文本
            top_k: 返回数量

        Returns:
            相关文档块列表
        """
        try:
            index_path = self._get_index_path(project_id)
            chunks_path = self._get_chunks_path(project_id)

            if not os.path.exists(index_path):
                return []

            # 加载索引和 chunks
            faiss = _get_faiss()
            index = faiss.read_index(index_path)
            with open(chunks_path, "r", encoding="utf-8") as f:
                all_chunks = json.load(f)

            # 生成查询向量
            model = _get_embedding_model()
            query_vector = model.encode([query], show_progress_bar=False)

            # 检索
            distances, indices = index.search(
                np.array(query_vector, dtype=np.float32), min(top_k, len(all_chunks))
            )

            # 组装结果
            results = []
            for i, idx in enumerate(indices[0]):
                if idx >= 0 and idx < len(all_chunks):
                    chunk = all_chunks[idx]
                    results.append({
                        **chunk,
                        "score": float(distances[0][i]),
                        "similarity": float(1 / (1 + distances[0][i])),
                    })

            return results

        except Exception as e:
            logger.error(f"知识库检索失败: {e}")
            return []

    def delete_document(self, project_id: int, doc_id: int) -> Dict[str, Any]:
        """
        删除文档（重建索引）

        Args:
            project_id: 项目ID
            doc_id: 文档ID

        Returns:
            删除结果
        """
        try:
            index_path = self._get_index_path(project_id)
            chunks_path = self._get_chunks_path(project_id)

            if not os.path.exists(chunks_path):
                return {"success": True, "deleted_chunks": 0}

            with open(chunks_path, "r", encoding="utf-8") as f:
                all_chunks = json.load(f)

            # 过滤掉要删除的文档
            remaining = [c for c in all_chunks if c.get("doc_id") != doc_id]
            deleted_count = len(all_chunks) - len(remaining)

            if not remaining:
                # 删除索引文件
                if os.path.exists(index_path):
                    os.remove(index_path)
                with open(chunks_path, "w", encoding="utf-8") as f:
                    json.dump([], f)
                return {"success": True, "deleted_chunks": deleted_count}

            # 重建索引
            faiss = _get_faiss()
            model = _get_embedding_model()
            texts = [c["content"] for c in remaining]
            embeddings = model.encode(texts, show_progress_bar=False)

            dimension = embeddings.shape[1]
            index = faiss.IndexFlatL2(dimension)
            index.add(np.array(embeddings, dtype=np.float32))

            faiss.write_index(index, index_path)
            with open(chunks_path, "w", encoding="utf-8") as f:
                json.dump(remaining, f, ensure_ascii=False, indent=2)

            return {"success": True, "deleted_chunks": deleted_count}

        except Exception as e:
            logger.error(f"删除知识库文档失败: {e}")
            return {"success": False, "error": str(e)}

    def get_stats(self, project_id: int) -> Dict[str, Any]:
        """获取知识库统计信息"""
        chunks_path = self._get_chunks_path(project_id)
        if not os.path.exists(chunks_path):
            return {"total_docs": 0, "total_chunks": 0}

        with open(chunks_path, "r", encoding="utf-8") as f:
            all_chunks = json.load(f)

        doc_ids = set(c.get("doc_id") for c in all_chunks)
        return {
            "total_docs": len(doc_ids),
            "total_chunks": len(all_chunks),
        }


# 全局单例
knowledge_base_service = KnowledgeBaseService()
