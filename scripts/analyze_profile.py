#!/usr/bin/env python3
"""Analyze and visualize profiling results."""
import argparse
import pstats
from pathlib import Path
import sys


def analyze_profile(prof_file: Path, top_n: int = 30):
    """
    Analyze a .prof file and print detailed statistics.
    
    Args:
        prof_file: Path to .prof file
        top_n: Number of top functions to display
    """
    if not prof_file.exists():
        print(f"Error: Profile file not found: {prof_file}")
        sys.exit(1)
    
    print("=" * 80)
    print(f"Analyzing: {prof_file.name}")
    print("=" * 80)
    
    stats = pstats.Stats(str(prof_file))
    
    # Print overall statistics
    print(f"\nTotal function calls: {stats.total_calls:,}")
    print(f"Primitive calls: {stats.prim_calls:,}")
    print(f"Total time: {stats.total_tt:.3f} seconds")
    
    # Top functions by cumulative time
    print("\n" + "=" * 80)
    print(f"TOP {top_n} FUNCTIONS BY CUMULATIVE TIME")
    print("=" * 80)
    stats.sort_stats('cumulative')
    stats.print_stats(top_n)
    
    # Top functions by internal time
    print("\n" + "=" * 80)
    print(f"TOP {top_n} FUNCTIONS BY INTERNAL TIME")
    print("=" * 80)
    stats.sort_stats('tottime')
    stats.print_stats(top_n)
    
    # Show callers
    print("\n" + "=" * 80)
    print("CALLERS OF TOP 10 FUNCTIONS (by cumulative time)")
    print("=" * 80)
    stats.sort_stats('cumulative')
    stats.print_callers(10)
    
    # Show callees
    print("\n" + "=" * 80)
    print("CALLEES OF TOP 10 FUNCTIONS (by cumulative time)")
    print("=" * 80)
    stats.print_callees(10)


def compare_profiles(prof_file1: Path, prof_file2: Path):
    """
    Compare two profile files to see performance differences.
    
    Args:
        prof_file1: First profile file (baseline)
        prof_file2: Second profile file (comparison)
    """
    if not prof_file1.exists() or not prof_file2.exists():
        print("Error: One or both profile files not found")
        sys.exit(1)
    
    print("=" * 80)
    print("PROFILE COMPARISON")
    print("=" * 80)
    print(f"Baseline:   {prof_file1.name}")
    print(f"Comparison: {prof_file2.name}")
    print("=" * 80)
    
    stats1 = pstats.Stats(str(prof_file1))
    stats2 = pstats.Stats(str(prof_file2))
    
    print(f"\nBaseline total time:   {stats1.total_tt:.3f} seconds")
    print(f"Comparison total time: {stats2.total_tt:.3f} seconds")
    
    time_diff = stats2.total_tt - stats1.total_tt
    pct_change = (time_diff / stats1.total_tt * 100) if stats1.total_tt > 0 else 0
    
    print(f"Difference: {time_diff:+.3f} seconds ({pct_change:+.1f}%)")
    
    if time_diff < 0:
        print("✓ Performance IMPROVED")
    elif time_diff > 0:
        print("✗ Performance DEGRADED")
    else:
        print("= No change")


def list_profiles(profile_dir: Path):
    """
    List all available profile files.
    
    Args:
        profile_dir: Directory containing profile files
    """
    if not profile_dir.exists():
        print(f"Profile directory not found: {profile_dir}")
        return
    
    prof_files = sorted(profile_dir.glob("*.prof"), reverse=True)
    
    if not prof_files:
        print(f"No profile files found in {profile_dir}")
        return
    
    print("=" * 80)
    print("AVAILABLE PROFILE FILES")
    print("=" * 80)
    
    for i, prof_file in enumerate(prof_files, 1):
        stats = pstats.Stats(str(prof_file))
        size_kb = prof_file.stat().st_size / 1024
        print(f"{i:2d}. {prof_file.name}")
        print(f"    Size: {size_kb:.1f} KB | Total time: {stats.total_tt:.3f}s | Calls: {stats.total_calls:,}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Analyze profiling results from Reddit scraper'
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Command to run')
    
    # Analyze command
    analyze_parser = subparsers.add_parser('analyze', help='Analyze a profile file')
    analyze_parser.add_argument('profile_file', type=str, help='Path to .prof file')
    analyze_parser.add_argument('--top', type=int, default=30, help='Number of top functions to show')
    
    # Compare command
    compare_parser = subparsers.add_parser('compare', help='Compare two profile files')
    compare_parser.add_argument('baseline', type=str, help='Baseline profile file')
    compare_parser.add_argument('comparison', type=str, help='Comparison profile file')
    
    # List command
    list_parser = subparsers.add_parser('list', help='List available profile files')
    list_parser.add_argument(
        '--dir',
        type=str,
        default='profile_stats',
        help='Profile directory (default: profile_stats)'
    )
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    if args.command == 'analyze':
        analyze_profile(Path(args.profile_file), args.top)
    elif args.command == 'compare':
        compare_profiles(Path(args.baseline), Path(args.comparison))
    elif args.command == 'list':
        list_profiles(Path(args.dir))


if __name__ == '__main__':
    main()
