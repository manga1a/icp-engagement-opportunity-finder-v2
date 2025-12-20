"""Profiling utilities for performance analysis."""
import cProfile
import pstats
import io
import logging
from pathlib import Path
from datetime import datetime
from contextlib import contextmanager
from typing import Optional

logger = logging.getLogger(__name__)


class ProfilerContext:
    """Context manager for profiling code sections."""
    
    def __init__(self, name: str, enabled: bool = True):
        """
        Initialize profiler context.
        
        Args:
            name: Name of the profiling section
            enabled: Whether profiling is enabled
        """
        self.name = name
        self.enabled = enabled
        self.profiler = None
        
    def __enter__(self):
        """Start profiling."""
        if self.enabled:
            self.profiler = cProfile.Profile()
            self.profiler.enable()
            logger.debug(f"Started profiling: {self.name}")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Stop profiling."""
        if self.enabled and self.profiler:
            self.profiler.disable()
            logger.debug(f"Stopped profiling: {self.name}")
        return False


def save_profile_stats(
    profiler: cProfile.Profile,
    output_dir: Path,
    prefix: str = "profile"
) -> tuple[Path, Path]:
    """
    Save profiler statistics to files.
    
    Args:
        profiler: The cProfile.Profile object
        output_dir: Directory to save profile files
        prefix: Prefix for output filenames
    
    Returns:
        Tuple of (binary_stats_path, text_report_path)
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate timestamp for unique filenames
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # Save binary stats file (.prof)
    prof_file = output_dir / f"{prefix}_{timestamp}.prof"
    profiler.dump_stats(str(prof_file))
    
    # Generate and save text report
    txt_file = output_dir / f"{prefix}_{timestamp}.txt"
    
    with open(txt_file, 'w') as f:
        # Create stats object
        stats = pstats.Stats(profiler, stream=f)
        
        # Write header
        f.write("=" * 80 + "\n")
        f.write(f"Profile Report: {prefix}\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("=" * 80 + "\n\n")
        
        # Sort by cumulative time and print top functions
        f.write("\n" + "=" * 80 + "\n")
        f.write("TOP 30 FUNCTIONS BY CUMULATIVE TIME\n")
        f.write("=" * 80 + "\n")
        stats.sort_stats('cumulative')
        stats.print_stats(30)
        
        # Sort by total time
        f.write("\n" + "=" * 80 + "\n")
        f.write("TOP 30 FUNCTIONS BY TOTAL TIME\n")
        f.write("=" * 80 + "\n")
        stats.sort_stats('tottime')
        stats.print_stats(30)
        
        # Print callers for top functions
        f.write("\n" + "=" * 80 + "\n")
        f.write("CALLERS OF TOP 10 FUNCTIONS\n")
        f.write("=" * 80 + "\n")
        stats.sort_stats('cumulative')
        stats.print_callers(10)
    
    logger.info(f"Profile stats saved to {prof_file}")
    logger.info(f"Profile report saved to {txt_file}")
    
    return prof_file, txt_file


def print_profile_summary(profiler: cProfile.Profile, top_n: int = 20):
    """
    Print a summary of profiling results to console.
    
    Args:
        profiler: The cProfile.Profile object
        top_n: Number of top functions to display
    """
    # Create string buffer for stats
    s = io.StringIO()
    stats = pstats.Stats(profiler, stream=s)
    
    print("\n" + "=" * 80)
    print("PROFILING SUMMARY - TOP FUNCTIONS BY CUMULATIVE TIME")
    print("=" * 80)
    
    stats.sort_stats('cumulative')
    stats.print_stats(top_n)
    
    # Print the stats
    print(s.getvalue())
    print("=" * 80 + "\n")


def get_profile_stats_summary(profiler: cProfile.Profile) -> dict:
    """
    Get a dictionary summary of profile statistics.
    
    Args:
        profiler: The cProfile.Profile object
    
    Returns:
        Dictionary with summary statistics
    """
    stats = pstats.Stats(profiler)
    
    # Get total stats
    total_calls = stats.total_calls
    prim_calls = stats.prim_calls
    total_time = stats.total_tt
    
    # Get top functions by cumulative time
    stats.sort_stats('cumulative')
    
    # Extract top functions
    top_functions = []
    for func, (cc, nc, tt, ct, callers) in list(stats.stats.items())[:10]:
        top_functions.append({
            'function': func,
            'calls': nc,
            'total_time': tt,
            'cumulative_time': ct,
            'per_call': ct / nc if nc > 0 else 0
        })
    
    return {
        'total_calls': total_calls,
        'primitive_calls': prim_calls,
        'total_time': total_time,
        'top_functions': top_functions
    }


@contextmanager
def profile_section(name: str, enabled: bool = True):
    """
    Context manager for profiling a code section.
    
    Usage:
        with profile_section("data_processing", enabled=args.profile):
            # code to profile
            process_data()
    
    Args:
        name: Name of the section being profiled
        enabled: Whether profiling is enabled
    """
    profiler = None
    if enabled:
        profiler = cProfile.Profile()
        profiler.enable()
        logger.debug(f"Started profiling section: {name}")
    
    try:
        yield profiler
    finally:
        if enabled and profiler:
            profiler.disable()
            logger.debug(f"Stopped profiling section: {name}")
