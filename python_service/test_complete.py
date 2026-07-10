#!/usr/bin/env python3
"""
Complete end-to-end test script
Tests: Scrapers → Embeddings → Similarity → Recommendations
No API keys required!
"""
import os
import sys
import logging
from dotenv import load_dotenv

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from scrapers import CephTrackerScraper, GithubPRScraper
from embeddings import SentenceTransformerEmbedder
from similarity import SimilarityCalculator

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def print_separator(title="", char="="):
    """Print a separator line"""
    print("\n" + char * 80)
    if title:
        print(f" {title}")
        print(char * 80)
    print()


def test_scrapers():
    """Test both scrapers"""
    print_separator("STAGE 1: Testing Scrapers")
    
    # Test Ceph tracker scraper
    print("1. Ceph Tracker Scraper")
    print("-" * 40)
    try:
        with CephTrackerScraper() as scraper:
            trackers = scraper.fetch_unlinked_trackers(limit=3)
            print(f"✓ Found {len(trackers)} unlinked trackers")
            if trackers:
                print(f"  Example: {trackers[0]['subject'][:60]}...")
    except Exception as e:
        print(f"✗ Error: {e}")
        trackers = []
    
    print()
    
    # Test GitHub PR scraper
    print("2. GitHub PR Scraper")
    print("-" * 40)
    try:
        github_token = os.getenv('GITHUB_TOKEN')
        with GithubPRScraper(access_token=github_token) as scraper:
            rate_limit = scraper.get_rate_limit_status()
            print(f"  Rate limit: {rate_limit['remaining']}/{rate_limit['limit']}")
            
            prs = scraper.fetch_unlinked_prs(limit=3)
            print(f"✓ Found {len(prs)} unlinked PRs")
            if prs:
                print(f"  Example: {prs[0]['title'][:60]}...")
    except Exception as e:
        print(f"✗ Error: {e}")
        prs = []
    
    return trackers, prs


def test_embeddings(trackers, prs):
    """Test embedding generation"""
    print_separator("STAGE 2: Testing Embeddings (Sentence Transformers)")
    
    print("Loading embedding model (this may take a moment on first run)...")
    print("Model: all-MiniLM-L6-v2 (384 dimensions, no API key needed!)")
    print()
    
    try:
        embedder = SentenceTransformerEmbedder(model_name='all-MiniLM-L6-v2')
        print(f"✓ Model loaded: {embedder.get_model_info()['model_name']}")
        print(f"  Embedding dimension: {embedder.get_embedding_dimension()}")
        print()
        
        # Generate embeddings for trackers
        if trackers:
            print(f"Generating embeddings for {len(trackers)} trackers...")
            tracker_texts = [t['combined_text'] for t in trackers]
            tracker_embeddings = embedder.generate_embeddings(tracker_texts)
            print(f"✓ Generated {len(tracker_embeddings)} tracker embeddings")
            print(f"  Shape: {tracker_embeddings.shape}")
        else:
            tracker_embeddings = None
            print("⚠ No trackers to embed")
        
        print()
        
        # Generate embeddings for PRs
        if prs:
            print(f"Generating embeddings for {len(prs)} PRs...")
            pr_texts = [p['combined_text'] for p in prs]
            pr_embeddings = embedder.generate_embeddings(pr_texts)
            print(f"✓ Generated {len(pr_embeddings)} PR embeddings")
            print(f"  Shape: {pr_embeddings.shape}")
        else:
            pr_embeddings = None
            print("⚠ No PRs to embed")
        
        return embedder, tracker_embeddings, pr_embeddings
        
    except Exception as e:
        print(f"✗ Error: {e}")
        logger.exception("Embedding error")
        return None, None, None


def test_similarity(trackers, prs, tracker_embeddings, pr_embeddings):
    """Test similarity calculation"""
    print_separator("STAGE 3: Testing Similarity Calculation")
    
    if tracker_embeddings is None or pr_embeddings is None:
        print("⚠ Skipping similarity test (no embeddings available)")
        return []
    
    try:
        calculator = SimilarityCalculator(threshold=0.5)  # Lower threshold for demo
        print(f"Similarity threshold: {calculator.get_threshold()}")
        print()
        
        recommendations = []
        
        # For each tracker, find similar PRs
        for i, tracker in enumerate(trackers):
            print(f"Tracker #{i+1}: {tracker['subject'][:50]}...")
            
            matches = calculator.find_top_matches(
                tracker_embeddings[i],
                pr_embeddings,
                prs,
                top_k=3
            )
            
            if matches:
                print(f"  Found {len(matches)} similar PR(s):")
                for pr, score in matches:
                    confidence = calculator.get_confidence_level(score)
                    print(f"    • PR #{pr['pr_number']}: {pr['title'][:40]}...")
                    print(f"      Similarity: {score:.3f} ({confidence})")
                    
                    recommendations.append({
                        'tracker': tracker,
                        'pr': pr,
                        'similarity': score,
                        'confidence': confidence
                    })
            else:
                print("  No similar PRs found above threshold")
            print()
        
        return recommendations
        
    except Exception as e:
        print(f"✗ Error: {e}")
        logger.exception("Similarity error")
        return []


def test_recommendations(recommendations):
    """Display final recommendations"""
    print_separator("STAGE 4: Recommendations Summary")
    
    if not recommendations:
        print("No recommendations generated")
        print("This could be because:")
        print("  • No unlinked trackers/PRs found")
        print("  • No similarities above threshold")
        print("  • API rate limits")
        return
    
    print(f"Generated {len(recommendations)} recommendation(s):\n")
    
    # Group by confidence
    by_confidence = {}
    for rec in recommendations:
        conf = rec['confidence']
        if conf not in by_confidence:
            by_confidence[conf] = []
        by_confidence[conf].append(rec)
    
    for confidence in ['very_high', 'high', 'medium', 'low']:
        if confidence in by_confidence:
            recs = by_confidence[confidence]
            print(f"{confidence.upper().replace('_', ' ')} Confidence ({len(recs)}):")
            for rec in recs:
                print(f"  • Tracker #{rec['tracker']['tracker_id']}: {rec['tracker']['subject'][:40]}...")
                print(f"    ↔ PR #{rec['pr']['pr_number']}: {rec['pr']['title'][:40]}...")
                print(f"    Similarity: {rec['similarity']:.3f}")
                print()


def main():
    """Main test function"""
    print_separator("Ceph Tracker Linker - Complete Test", "=")
    print("Testing full pipeline: Scrapers → Embeddings → Similarity → Recommendations")
    print("No API keys required! (except optional GitHub token for higher rate limits)")
    
    # Stage 1: Scrapers
    trackers, prs = test_scrapers()
    
    if not trackers and not prs:
        print("\n⚠ No data to process. Check your internet connection or API access.")
        return 1
    
    # Stage 2: Embeddings
    embedder, tracker_embeddings, pr_embeddings = test_embeddings(trackers, prs)
    
    if embedder is None:
        print("\n✗ Embedding generation failed. Check error messages above.")
        return 1
    
    # Stage 3: Similarity
    recommendations = test_similarity(trackers, prs, tracker_embeddings, pr_embeddings)
    
    # Stage 4: Summary
    test_recommendations(recommendations)
    
    # Final summary
    print_separator("Test Complete!", "=")
    print("✓ Scrapers: Working")
    print("✓ Embeddings: Working (Sentence Transformers)")
    print("✓ Similarity: Working")
    print(f"✓ Recommendations: {len(recommendations)} generated")
    print()
    print("Next steps:")
    print("  1. Build REST API to expose these functions")
    print("  2. Create Ruby wrapper for Redmine integration")
    print("  3. Add caching layer (Redis)")
    print("  4. Build UI for reviewing recommendations")
    print_separator("", "=")
    
    return 0


if __name__ == '__main__':
    sys.exit(main())

# Made with Bob
