"""
Comprehensive test script for the Metaculus forecasting bot.
This script tests each function individually and shows their outputs.
"""

import sys
import os
import traceback
import asyncio
import dotenv

dotenv.load_dotenv()

# Color codes for terminal output
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


def print_section(title: str):
    """Print a formatted section header."""
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'='*80}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{title.center(80)}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'='*80}{Colors.ENDC}\n")


def print_success(message: str):
    """Print a success message."""
    print(f"{Colors.OKGREEN}[OK] {message}{Colors.ENDC}")


def print_error(message: str):
    """Print an error message."""
    print(f"{Colors.FAIL}[ERR] {message}{Colors.ENDC}")


def print_warning(message: str):
    """Print a warning message."""
    print(f"{Colors.WARNING}[WARN] {message}{Colors.ENDC}")


def print_info(message: str):
    """Print an info message."""
    print(f"{Colors.OKCYAN}[INFO] {message}{Colors.ENDC}")


def test_environment_variables():
    """Test if all required environment variables are set."""
    print_section("Testing Environment Variables")
    
    required_vars = {
        "METACULUS_TOKEN": "Required for API access",
        "OPENROUTER_API_KEY": "Required for LLM calls",
    }
    
    optional_vars = {
        "PERPLEXITY_API_KEY": "For Perplexity research",
        "ASKNEWS_CLIENT_ID": "For AskNews research",
        "ASKNEWS_SECRET": "For AskNews research",
        "EXA_API_KEY": "For Exa research",
        "OPENAI_API_KEY": "For Exa Smart Searcher",
    }
    
    # Check required variables
    all_required_set = True
    for var, description in required_vars.items():
        value = os.getenv(var)
        if value:
            print_success(f"{var}: {value[:15]}... ({description})")
        else:
            print_error(f"{var} NOT set - {description}")
            all_required_set = False
    
    # Check optional variables
    print_info("\nOptional API Keys:")
    research_keys_available = False
    for var, description in optional_vars.items():
        value = os.getenv(var)
        if value:
            print_success(f"{var}: {value[:15]}... ({description})")
            if var in ["PERPLEXITY_API_KEY", "ASKNEWS_CLIENT_ID", "EXA_API_KEY"]:
                research_keys_available = True
        else:
            print_warning(f"{var} not set ({description})")
    
    if not research_keys_available:
        print_warning("\nNo research API keys found. Bot will run with 'No research done'")
    
    return all_required_set


def test_api_connection():
    """Test if we can connect to the Metaculus API with rate limiting."""
    print_section("Testing Metaculus API Connection & Rate Limiting")
    
    import requests
    import time
    
    METACULUS_TOKEN = os.getenv("METACULUS_TOKEN")
    if not METACULUS_TOKEN:
        print_error("METACULUS_TOKEN not set, skipping API tests")
        return False
    
    headers = {"Authorization": f"Token {METACULUS_TOKEN}"}
    
    try:
        # Test 1: Basic connection
        print_info("Test 1: Basic API connection...")
        response = requests.get(
            "https://www.metaculus.com/api/posts/",
            headers=headers,
            params={"limit": 1},
            timeout=10
        )
        
        if response.ok:
            print_success(f"Connected to Metaculus API (Status: {response.status_code})")
            data = response.json()
            print_info(f"Response contains {len(data.get('results', []))} results")
        else:
            print_error(f"API request failed with status {response.status_code}")
            print_error(f"Response: {response.text[:200]}")
            return False
        
        # Test 2: Rate limiting behavior (make 3 rapid requests)
        print_info("\nTest 2: Testing rate limiting (3 rapid requests)...")
        request_times = []
        for i in range(3):
            start = time.time()
            response = requests.get(
                "https://www.metaculus.com/api/posts/",
                headers=headers,
                params={"limit": 1},
                timeout=10
            )
            end = time.time()
            request_times.append(end - start)
            
            if response.ok:
                print_success(f"Request {i+1}: {response.status_code} (took {end-start:.2f}s)")
            else:
                print_warning(f"Request {i+1}: {response.status_code}")
            
            # Small delay between requests
            time.sleep(0.5)
        
        avg_time = sum(request_times) / len(request_times)
        print_info(f"Average request time: {avg_time:.2f}s")
        
        return True
            
    except requests.exceptions.Timeout:
        print_error("API request timed out")
        return False
    except Exception as e:
        print_error(f"API connection error: {str(e)}")
        traceback.print_exc()
        return False


async def test_async_api_functions():
    """Test async API functions with rate limiting."""
    print_section("Testing Async API Functions with Rate Limiting")
    
    METACULUS_TOKEN = os.getenv("METACULUS_TOKEN")
    if not METACULUS_TOKEN:
        print_error("METACULUS_TOKEN not set, skipping async tests")
        return False
    
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("forecasting_bot", "forecasting_bot.py")
        if spec is None or spec.loader is None:
            print_error("Could not load forecasting_bot.py")
            return False
            
        bot = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(bot)
        
        # Test 1: Check rate limiter exists
        print_info("Test 1: Checking rate limiter configuration...")
        if hasattr(bot, 'METACULUS_API_RATE_LIMITER'):
            print_success("METACULUS_API_RATE_LIMITER is configured")
        else:
            print_warning("METACULUS_API_RATE_LIMITER not found - rate limiting may not be active")
        
        # Test 2: Test get_post_details (should be async now)
        print_info("\nTest 2: Testing async get_post_details()...")
        
        # Get a sample post ID from example questions
        if bot.EXAMPLE_QUESTIONS:
            test_post_id = bot.EXAMPLE_QUESTIONS[0][1]
            print_info(f"Fetching post {test_post_id}...")
            
            import time
            start = time.time()
            post_details = await bot.get_post_details(test_post_id)
            end = time.time()
            
            if post_details and 'question' in post_details:
                print_success(f"Retrieved post details in {end-start:.2f}s")
                print_info(f"  Title: {post_details['question']['title'][:60]}...")
                print_info(f"  Type: {post_details['question']['type']}")
            else:
                print_error("Failed to retrieve valid post details")
                return False
        
        # Test 3: Test concurrent requests with rate limiting
        print_info("\nTest 3: Testing concurrent API calls with rate limiting...")
        if len(bot.EXAMPLE_QUESTIONS) >= 3:
            test_post_ids = [q[1] for q in bot.EXAMPLE_QUESTIONS[:3]]
            print_info(f"Making 3 concurrent requests for posts: {test_post_ids}")
            
            import time
            start = time.time()
            results = await asyncio.gather(*[
                bot.get_post_details(post_id) 
                for post_id in test_post_ids
            ])
            end = time.time()
            
            successful = sum(1 for r in results if r and 'question' in r)
            print_success(f"Completed {successful}/3 concurrent requests in {end-start:.2f}s")
            
            if end - start < 1.0:
                print_warning("Requests completed very quickly - rate limiting may not be working")
            else:
                print_success(f"Rate limiting appears to be working (took {end-start:.2f}s for 3 requests)")
        
        return True
        
    except Exception as e:
        print_error(f"Error testing async functions: {str(e)}")
        traceback.print_exc()
        return False


async def test_llm_connection():
    """Test LLM API connection."""
    print_section("Testing LLM Connection")
    
    OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
    if not OPENROUTER_API_KEY:
        print_error("OPENROUTER_API_KEY not set, skipping LLM tests")
        return False
    
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("forecasting_bot", "forecasting_bot.py")
        if spec is None or spec.loader is None:
            print_error("Could not load forecasting_bot.py")
            return False
            
        bot = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(bot)
        
        print_info("Testing LLM call with simple prompt...")
        test_prompt = "Say 'test successful' and nothing else."
        
        import time
        start = time.time()
        response = await bot.call_llm(test_prompt, temperature=0.0)
        end = time.time()
        
        if response:
            print_success(f"LLM responded in {end-start:.2f}s")
            print_info(f"Response: {response[:100]}...")
            return True
        else:
            print_error("LLM returned empty response")
            return False
            
    except Exception as e:
        print_error(f"Error testing LLM: {str(e)}")
        traceback.print_exc()
        return False


async def test_tournament_questions():
    """Test fetching questions from a tournament."""
    print_section("Testing Tournament Question Retrieval")
    
    METACULUS_TOKEN = os.getenv("METACULUS_TOKEN")
    if not METACULUS_TOKEN:
        print_error("METACULUS_TOKEN not set, skipping tournament tests")
        return False
    
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("forecasting_bot", "forecasting_bot.py")
        if spec is None or spec.loader is None:
            print_error("Could not load forecasting_bot.py")
            return False
            
        bot = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(bot)
        
        print_info(f"Fetching open questions from default tournament...")
        print_info(f"Tournament ID: {bot.DEFAULT_TOURNAMENT_ID}")
        
        questions = bot.get_open_question_ids_from_tournament(bot.DEFAULT_TOURNAMENT_ID)
        
        if questions:
            print_success(f"Found {len(questions)} open questions")
            print_info("\nFirst 3 questions:")
            for i, (q_id, p_id) in enumerate(questions[:3], 1):
                print(f"  {i}. Question ID: {q_id}, Post ID: {p_id}")
            return True
        else:
            print_warning("No open questions found in tournament")
            return False
            
    except Exception as e:
        print_error(f"Error testing tournament questions: {str(e)}")
        traceback.print_exc()
        return False


async def test_resolution_scraper():
    """Test resolution scraper extraction, adapter wiring, and scrape flow."""
    print_section("Testing Resolution Scraper")

    try:
        from resolution_scraper import (
            ResolutionScraper,
            ScraperConfig,
            format_resolution_snapshot,
            format_scrape_errors,
        )
        from resolution_scraper.extraction import classify_url, extract_resolution_urls
    except Exception as e:
        print_error(f"Failed importing resolution scraper modules: {str(e)}")
        traceback.print_exc()
        return False

    try:
        # Test 1: URL extraction and classification
        print_info("Test 1: URL extraction/classification...")
        criteria = (
            "Resolve from [Wikipedia](https://en.wikipedia.org/wiki/Wikipedia). "
            "Backup source: https://en.wikipedia.org/wiki/Wikipedia."
        )
        fine_print = "JSON source: https://api.github.com/repos/python/cpython."
        description = "CSV source (example): https://people.sc.fsu.edu/~jburkardt/data/csv/airtravel.csv"

        urls = extract_resolution_urls(criteria, fine_print, description)
        print_info(f"Extracted URLs ({len(urls)}): {urls}")
        if not urls:
            print_error("No URLs extracted by extract_resolution_urls()")
            return False

        url_types = {url: classify_url(url) for url in urls}
        print_info(f"Classified URL types: {url_types}")
        print_success("URL extraction/classification works")

        # Test 2: Scraper initialization and adapter setup
        print_info("\nTest 2: Scraper initialization...")
        scraper = ResolutionScraper(
            ScraperConfig(
                use_browser_fallback=False,
                max_parallel_fetches=2,
                max_retries=1,
                request_timeout_s=12.0,
            )
        )
        adapter_names = [adapter.name for adapter in scraper.adapters]
        print_info(f"Loaded adapters: {adapter_names}")
        if len(adapter_names) < 3:
            print_error("Expected multiple adapters, but found too few")
            return False
        print_success("ResolutionScraper initialized correctly")

        # Test 3: End-to-end scrape flow on synthetic question details
        print_info("\nTest 3: End-to-end scrape flow...")
        question_details = {
            "id": 999999,
            "title": "Resolution scraper health check",
            "type": "numeric",
            "scheduled_resolve_time": None,
            "resolution_criteria": criteria,
            "fine_print": fine_print,
            "description": description,
        }

        results = await scraper.scrape_question_sources(question_details)
        print_info(f"Scrape results count: {len(results)}")
        if not isinstance(results, list):
            print_error("scrape_question_sources() did not return a list")
            return False

        signals = scraper.flatten_signals(results)
        snapshot = format_resolution_snapshot(signals)
        scrape_errors = format_scrape_errors(results)

        print_info(f"Signals extracted: {len(signals)}")
        print_info(f"Snapshot preview: {snapshot[:300]}")
        if scrape_errors:
            print_warning(f"Scrape errors (if any): {scrape_errors[:300]}")

        # Consider scraper healthy if pipeline executes and returns either signals
        # or meaningful structured errors.
        if signals:
            print_success("Resolution scraper extracted structured signals")
            return True

        if results and all(hasattr(r, "ok") for r in results):
            print_warning(
                "No signals extracted, but scraper pipeline executed with structured results."
            )
            return True

        print_error("Resolution scraper pipeline did not return expected structured output")
        return False

    except Exception as e:
        print_error(f"Error testing resolution scraper: {str(e)}")
        traceback.print_exc()
        return False


async def run_all_tests():
    """Run all tests and provide a summary."""
    print(f"\n{Colors.BOLD}{Colors.HEADER}")
    print("+" + "=" * 78 + "+")
    print("|         METACULUS FORECASTING BOT - COMPREHENSIVE TEST SUITE                  |")
    print("+" + "=" * 78 + "+")
    print(f"{Colors.ENDC}\n")
    
    results = {}
    
    # Run all tests
    results["Environment Variables"] = test_environment_variables()
    results["API Connection"] = test_api_connection()
    results["Async API Functions"] = await test_async_api_functions()
    results["LLM Connection"] = await test_llm_connection()
    results["Tournament Questions"] = await test_tournament_questions()
    results["Resolution Scraper"] = await test_resolution_scraper()
    
    # Print summary
    print_section("TEST SUMMARY")
    
    passed = sum(1 for result in results.values() if result)
    total = len(results)
    
    for test_name, result in results.items():
        if result:
            print_success(f"{test_name}")
        else:
            print_error(f"{test_name}")
    
    print(f"\n{Colors.BOLD}Overall: {passed}/{total} tests passed{Colors.ENDC}")
    
    if passed == total:
        print(f"\n{Colors.OKGREEN}{Colors.BOLD}All tests passed! Your forecasting bot is ready to use.{Colors.ENDC}")
        print_info("\nNext steps:")
        print_info("  1. Run: python forecasting_bot.py --mode examples --no-submit")
        print_info("  2. Check the outputs to verify everything works")
        print_info("  3. Run: python forecasting_bot.py --mode tournament")
    elif passed >= 3:
        print(f"\n{Colors.OKGREEN}{Colors.BOLD}Core functionality working. Some optional features failed.{Colors.ENDC}")
        print_info("\nYou can proceed with caution. Check failed tests above.")
    else:
        print(f"\n{Colors.FAIL}{Colors.BOLD}Critical tests failed. Please fix the errors above.{Colors.ENDC}")
        print_info("\nCommon issues:")
        print_info("  1. Missing METACULUS_TOKEN or OPENROUTER_API_KEY in .env file")
        print_info("  2. Invalid API keys")
        print_info("  3. Network connectivity issues")
        print_info("  4. Rate limiting not implemented in forecasting_bot.py")
    
    return passed == total


if __name__ == "__main__":
    try:
        success = asyncio.run(run_all_tests())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print(f"\n\n{Colors.WARNING}Tests interrupted by user{Colors.ENDC}")
        sys.exit(1)
    except Exception as e:
        print(f"\n{Colors.FAIL}Unexpected error: {str(e)}{Colors.ENDC}")
        traceback.print_exc()
        sys.exit(1)

