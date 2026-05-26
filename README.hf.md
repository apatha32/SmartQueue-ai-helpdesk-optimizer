---
title: Distributed Task Queue with AI
emoji: 🚀
colorFrom: purple
colorTo: blue
sdk: docker
pinned: false
app_port: 7860
---

# Distributed Task Queue with AI/RAG

A production-grade distributed task queue with a LangGraph ReAct AI agent and hybrid RAG (BM25 + dense retrieval + cross-encoder reranking).

## Features

- **Priority task queue** backed by Redis sorted sets
- **Autoscaling workers** processing `email`, `image_resize`, `report`, and `ai_agent` job types  
- **RAG chat** — hybrid BM25 + dense retrieval, HyDE query rewriting, cross-encoder reranking, RAGAS evaluation
- **Dead letter queue** with one-click retry and AI-powered failure analysis
- **React dashboard** with real-time stats via polling

## Setup

Set your `ANTHROPIC_API_KEY` in **Settings → Secrets** for the AI and RAG features to work.  
The queue and dashboard work immediately without it.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| API | Go 1.22 + Gin |
| Workers | Go goroutines |
| Queue | Redis sorted sets |
| RAG Agent | LangGraph + Claude |
| Embeddings | sentence-transformers (MiniLM-L12) |
| Vector store | ChromaDB |
| Reranker | cross-encoder/ms-marco-MiniLM-L-6 |
| Frontend | React 18 + Vite |

## Source

[github.com/your-username/distributed-task-queue](https://github.com/your-username/distributed-task-queue)
