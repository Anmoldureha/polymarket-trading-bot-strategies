#!/usr/bin/env python3
"""Script to verify market data is being received correctly"""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.api.polymarket_client import PolymarketClient
from src.utils.api_health_check import APIHealthCheck
from src.utils.logger import setup_logger


logger = setup_logger(__name__)


def main():
    """Run market data verification"""
    print("\n" + "=" * 70)
    print("POLYMARKET MARKET DATA VERIFICATION")
    print("=" * 70)
    print()
    
    # Initialize client
    print("Initializing Polymarket client...")
    client = PolymarketClient(paper_trading=True)
    
    # Run health check
    print("\nRunning comprehensive health check...\n")
    health_check = APIHealthCheck(client)
    results = health_check.run_full_check()
    
    # Print detailed results
    print("\n" + "=" * 70)
    print("DETAILED RESULTS")
    print("=" * 70)
    
    if results['overall_status'] == 'healthy':
        print("\n✓ ALL CHECKS PASSED - Market data is being received correctly!")
    else:
        print("\n✗ SOME CHECKS FAILED - Review the errors above")
        print("\nCommon issues:")
        print("  1. API credentials may be invalid")
        print("  2. API endpoint may have changed")
        print("  3. Network connectivity issues")
        print("  4. Rate limiting may be active")
    
    print("\n" + "=" * 70)
    
    # Return exit code
    return 0 if results['overall_status'] == 'healthy' else 1


if __name__ == "__main__":
    sys.exit(main())

