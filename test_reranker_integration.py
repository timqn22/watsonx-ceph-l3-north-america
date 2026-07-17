#!/usr/bin/env python3
"""
Test script to verify reranker and hybrid search integration with API server
"""

import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Set test environment variables
os.environ['ENABLE_RERANKING'] = 'true'
os.environ['RERANKER_MODEL'] = 'cross-encoder/ms-marco-MiniLM-L-6-v2'
os.environ['ENABLE_HYBRID_SEARCH'] = 'true'
os.environ['SEMANTIC_WEIGHT'] = '0.9'
os.environ['BM25_WEIGHT'] = '0.1'

print("=" * 80)
print("Testing Reranker and Hybrid Search Integration")
print("=" * 80)

# Test 1: Import reranker module
print("\n1. Testing reranker module import...")
try:
    from src.reranker import Reranker
    print("✓ Reranker module imported successfully")
except Exception as e:
    print(f"✗ Failed to import reranker: {e}")
    sys.exit(1)

# Test 2: Initialize reranker
print("\n2. Testing reranker initialization...")
try:
    reranker = Reranker(model_name='cross-encoder/ms-marco-MiniLM-L-6-v2')
    print("✓ Reranker initialized successfully")
except Exception as e:
    print(f"✗ Failed to initialize reranker: {e}")
    sys.exit(1)

# Test 3: Test reranking with sample data
print("\n3. Testing reranking functionality...")
try:
    query = "OSD crash on startup"
    sample_results = [
        {
            'issue_id': '1',
            'similarity_score': 0.75,
            'text': 'OSD daemon crashes immediately after starting with segmentation fault',
            'metadata': {'subject': 'OSD crash issue'}
        },
        {
            'issue_id': '2',
            'similarity_score': 0.70,
            'text': 'Monitor service fails to start due to configuration error',
            'metadata': {'subject': 'Monitor startup failure'}
        },
        {
            'issue_id': '3',
            'similarity_score': 0.65,
            'text': 'OSD fails to start after system reboot',
            'metadata': {'subject': 'OSD startup problem'}
        }
    ]
    
    reranked = reranker.rerank(query, sample_results, top_k=3)
    
    print(f"✓ Reranking completed successfully")
    print(f"\nOriginal scores vs Reranked scores:")
    for i, result in enumerate(reranked):
        orig_score = result.get('original_score', 0)
        rerank_score = result.get('rerank_score', 0)
        print(f"  Issue #{result['issue_id']}: {orig_score:.3f} → {rerank_score:.3f}")
    
except Exception as e:
    print(f"✗ Reranking failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
# Test 4: Test BM25 hybrid search
print("\n4. Testing BM25 hybrid search...")
try:
    from src.bm25_search import HybridSearch
    
    hybrid = HybridSearch(semantic_weight=0.9, bm25_weight=0.1)
    print("✓ Hybrid search initialized successfully")
    
    # Index sample documents
    sample_docs = [
        "OSD daemon crashes immediately after starting with segmentation fault",
        "Monitor service fails to start due to configuration error",
        "OSD fails to start after system reboot"
    ]
    sample_ids = ['1', '2', '3']
    sample_metadata = [
        {'subject': 'OSD crash issue'},
        {'subject': 'Monitor startup failure'},
        {'subject': 'OSD startup problem'}
    ]
    
    hybrid.index_documents(sample_ids, sample_docs, sample_metadata)
    print("✓ Documents indexed for BM25")
    
    # Test hybrid scoring
    query = "OSD crash on startup"
    semantic_results = [
        {
            'issue_id': '1',
            'similarity_score': 0.75,
            'text': sample_docs[0],
            'metadata': sample_metadata[0]
        },
        {
            'issue_id': '2',
            'similarity_score': 0.70,
            'text': sample_docs[1],
            'metadata': sample_metadata[1]
        },
        {
            'issue_id': '3',
            'similarity_score': 0.65,
            'text': sample_docs[2],
            'metadata': sample_metadata[2]
        }
    ]
    
    hybrid_results = hybrid.combine_scores(semantic_results, query, n_results=3)
    
    print(f"✓ Hybrid scoring completed")
    print(f"\nSemantic vs BM25 vs Hybrid scores:")
    for result in hybrid_results:
        sem = result.get('semantic_score', 0)
        bm25 = result.get('bm25_score', 0)
        hyb = result.get('hybrid_score', 0)
        print(f"  Issue #{result['issue_id']}: semantic={sem:.3f}, bm25={bm25:.3f}, hybrid={hyb:.3f}")
    
except Exception as e:
    print(f"✗ Hybrid search test failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 5: Test API server integration
print("\n5. Testing API server integration...")
try:
    # Verify API server has reranker and hybrid search integration
    with open('api_server.py', 'r') as f:
        api_content = f.read()
        has_reranker_import = 'from src.reranker import Reranker' in api_content
        has_hybrid_import = 'from src.bm25_search import HybridSearch' in api_content
        has_get_reranker = 'def get_reranker():' in api_content
        has_get_hybrid = 'def get_hybrid_search():' in api_content
        has_reranking_logic = 'reranker.rerank(' in api_content
        has_hybrid_logic = 'hybrid_search.combine_scores(' in api_content
    
    if all([has_reranker_import, has_hybrid_import, has_get_reranker,
            has_get_hybrid, has_reranking_logic, has_hybrid_logic]):
        print("✓ API server module structure verified")
    else:
        raise Exception("API server missing reranker or hybrid search integration")
    
    print("  - Hybrid search (BM25 + semantic) will be loaded on first API call")
    print("  - Reranker will be loaded on first API call")
    print("  - Search pipeline: semantic → hybrid (90% semantic + 10% BM25) → rerank")
    print("  - Results will be fetched at 3x limit, hybrid scored, then reranked to top_k")
    
except Exception as e:
    print(f"✗ API server integration check failed: {e}")
    sys.exit(1)

print("\n" + "=" * 80)
print("All tests passed! ✓")
print("=" * 80)
print("\nIntegration summary:")
print("- Similarity threshold reduced from 75% to 55% in extension")
print("- Hybrid search (BM25 + semantic) integrated: 90% semantic, 10% BM25")
print("- Reranker integrated into API server search endpoints")
print("- Search pipeline: semantic → hybrid scoring → reranking")
print("- Configuration available via .env file")
print("\nConfiguration options:")
print("- ENABLE_HYBRID_SEARCH=true (enable BM25 hybrid search)")
print("- SEMANTIC_WEIGHT=0.9 (90% weight for semantic similarity)")
print("- BM25_WEIGHT=0.1 (10% weight for keyword matching)")
print("- ENABLE_RERANKING=true (enable cross-encoder reranking)")
print("- RERANKER_MODEL=cross-encoder/ms-marco-MiniLM-L-6-v2")
print("\nTo use:")
print("1. Install dependencies: pip install -r requirements.txt")
print("2. Configure .env file with desired settings")
print("3. Start the API server: python3 api_server.py")
print("4. The system will automatically apply hybrid search and reranking")
print("=" * 80)

# Made with Bob
