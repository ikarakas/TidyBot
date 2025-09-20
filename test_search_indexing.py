#!/usr/bin/env python3
"""
Test script for TidyBot's search, indexing, and offline capabilities
"""

import asyncio
import sys
from pathlib import Path
import json
from datetime import datetime, timedelta

# Add the ai_service directory to path
sys.path.insert(0, str(Path(__file__).parent / "tidybot" / "ai_service"))

from services.indexing_service import IndexingService
from services.search_engine import SearchEngine, SearchQuery, SearchType
from services.offline_manager import OfflineManager, OperationType


async def test_indexing():
    """Test file indexing functionality"""
    print("\n" + "="*50)
    print("Testing File Indexing")
    print("="*50)

    indexing_service = IndexingService()
    await indexing_service.start()

    # Create test directory with sample files
    test_dir = Path("test_files")
    test_dir.mkdir(exist_ok=True)

    # Create sample files
    sample_files = [
        ("invoice_2024.pdf", "Invoice #12345\nDate: 2024-01-15\nAmount: $1,500.00\nClient: Acme Corp"),
        ("report_q4.txt", "Quarterly Report Q4 2023\nSales increased by 25%\nNew customers: 150"),
        ("presentation.txt", "Marketing Strategy 2024\nTarget audience: Small businesses\nBudget: $50,000"),
        ("contract_abc.txt", "Service Agreement\nParty A: TechCorp\nParty B: ClientCo\nTerms: 12 months"),
        ("photo_metadata.txt", "IMG_001.jpg\nDate taken: 2024-01-10\nLocation: San Francisco\nCamera: Canon EOS")
    ]

    for filename, content in sample_files:
        file_path = test_dir / filename
        file_path.write_text(content)
        print(f"Created test file: {filename}")

    # Index the directory
    print(f"\nIndexing directory: {test_dir}")
    result = await indexing_service.index_directory(
        test_dir,
        recursive=True,
        monitor=True
    )

    print(f"Indexing result: {json.dumps(result, indent=2)}")

    # Get index statistics
    stats = await indexing_service.get_index_stats()
    print(f"\nIndex statistics: {json.dumps(stats, indent=2)}")

    await indexing_service.stop()
    return test_dir


async def test_search(test_dir: Path):
    """Test search functionality"""
    print("\n" + "="*50)
    print("Testing Search Engine")
    print("="*50)

    search_engine = SearchEngine()

    # Test different search types
    test_queries = [
        ("invoice from january", SearchType.NATURAL_LANGUAGE),
        ("quarterly report", SearchType.EXACT),
        ("budget 50000", SearchType.FUZZY),
        ("files about marketing", SearchType.NATURAL_LANGUAGE),
        ("documents larger than 100 bytes", SearchType.NATURAL_LANGUAGE),
        ("contracts with TechCorp", SearchType.NATURAL_LANGUAGE)
    ]

    for query_text, search_type in test_queries:
        print(f"\n--- Searching for: '{query_text}' (Type: {search_type.value}) ---")

        query = SearchQuery(
            query_text=query_text,
            search_type=search_type,
            limit=5,
            include_content=True
        )

        results = await search_engine.search(query)

        if results:
            for i, result in enumerate(results, 1):
                print(f"\n{i}. {result.file_name}")
                print(f"   Score: {result.score:.2f}")
                print(f"   Category: {result.category}")
                print(f"   Tags: {', '.join(result.tags)}")
                if result.highlights:
                    print(f"   Highlights: {result.highlights}")
                if result.content_preview:
                    print(f"   Preview: {result.content_preview[:100]}...")
        else:
            print("   No results found")

    # Test natural language parsing
    print("\n" + "="*50)
    print("Testing Natural Language Parser")
    print("="*50)

    nl_queries = [
        "find all invoices from last month",
        "show me presentations larger than 50kb",
        "images from yesterday",
        "documents created last week about sales",
        "pdf files containing budget information"
    ]

    parser = search_engine.nl_parser
    for query in nl_queries:
        print(f"\nQuery: '{query}'")
        parsed = parser.parse(query)
        print(f"Parsed: {json.dumps(parsed, indent=2, default=str)}")


async def test_offline_capabilities():
    """Test offline caching and sync"""
    print("\n" + "="*50)
    print("Testing Offline Capabilities")
    print("="*50)

    offline_manager = OfflineManager()
    await offline_manager.start()

    # Test file caching
    print("\n--- Testing File Cache ---")
    test_file_path = "/test/path/document.pdf"
    test_content = "This is test document content for caching"
    test_metadata = {
        "type": "document",
        "size": len(test_content),
        "created": datetime.now().isoformat()
    }
    test_analysis = {
        "keywords": ["test", "document", "cache"],
        "category": "test"
    }

    # Cache a file
    success = await offline_manager.cache.cache_file(
        test_file_path,
        test_content,
        test_metadata,
        test_analysis
    )
    print(f"File cached: {success}")

    # Retrieve cached file
    cached = await offline_manager.cache.get_cached_file(test_file_path)
    if cached:
        print(f"Retrieved from cache: {test_file_path}")
        print(f"  Content length: {len(cached['content'])}")
        print(f"  Metadata: {cached['metadata']}")

    # Test search result caching
    print("\n--- Testing Search Cache ---")
    test_query = "find all documents about testing"
    test_results = [
        {
            "file_path": "/test/doc1.txt",
            "file_name": "doc1.txt",
            "score": 0.95
        },
        {
            "file_path": "/test/doc2.txt",
            "file_name": "doc2.txt",
            "score": 0.85
        }
    ]

    # Cache search results
    await offline_manager.cache.cache_search_results(test_query, test_results)
    print(f"Cached search results for: '{test_query}'")

    # Retrieve cached search
    cached_search = await offline_manager.cache.get_cached_search(test_query)
    if cached_search:
        print(f"Retrieved {len(cached_search)} cached search results")

    # Test offline operations queue
    print("\n--- Testing Offline Queue ---")

    # Queue some operations
    op_id1 = await offline_manager.queue_operation(
        OperationType.UPDATE,
        "/test/file1.txt",
        {"content": "Updated content"}
    )
    print(f"Queued operation: {op_id1}")

    op_id2 = await offline_manager.queue_operation(
        OperationType.CREATE,
        "/test/file2.txt",
        {"content": "New file content"}
    )
    print(f"Queued operation: {op_id2}")

    # Get offline stats
    stats = await offline_manager.get_offline_stats()
    print(f"\nOffline statistics: {json.dumps(stats, indent=2)}")

    # Simulate going offline
    await offline_manager.set_online_status(False)
    print("\nSystem is now OFFLINE")

    # Try to queue more operations while offline
    op_id3 = await offline_manager.queue_operation(
        OperationType.DELETE,
        "/test/file3.txt",
        {}
    )
    print(f"Queued operation while offline: {op_id3}")

    # Simulate going back online
    await offline_manager.set_online_status(True)
    print("\nSystem is now ONLINE")

    # Sync operations
    print("\nSyncing offline operations...")
    sync_result = await offline_manager.sync_now()
    print(f"Sync result: {json.dumps(sync_result, indent=2)}")

    # Test cache cleanup
    print("\n--- Testing Cache Cleanup ---")
    await offline_manager.cache.cleanup_cache(max_age_days=30, max_size_mb=100)
    print("Cache cleanup completed")

    await offline_manager.stop()


async def main():
    """Run all tests"""
    print("\n" + "="*70)
    print(" TidyBot Search, Indexing & Offline Capabilities Test Suite")
    print("="*70)

    try:
        # Test indexing
        test_dir = await test_indexing()

        # Test search
        await test_search(test_dir)

        # Test offline capabilities
        await test_offline_capabilities()

        print("\n" + "="*70)
        print(" All tests completed successfully!")
        print("="*70)

        # Cleanup
        print("\nCleaning up test files...")
        import shutil
        if test_dir.exists():
            shutil.rmtree(test_dir)
        print("Test files cleaned up")

    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    # Run the async main function
    asyncio.run(main())