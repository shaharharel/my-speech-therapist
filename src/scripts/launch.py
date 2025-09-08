#!/usr/bin/env python3
"""
Launcher script for the Speech Therapist application.
Provides easy access to different configurations and common use cases.
"""

import argparse
import sys
import os
from pathlib import Path

def main():
    parser = argparse.ArgumentParser(
        description="Speech Therapist Application Launcher",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python launch.py                    # Run with default configuration
  python launch.py --debug            # Run in debug mode
  python launch.py --production       # Run in production mode
  python launch.py --case "ילד בן 6"   # Override patient case
  python launch.py --test-config      # Test all configurations
        """
    )
    
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Run in debug mode (faster, cheaper, more verbose)"
    )
    
    parser.add_argument(
        "--production",
        action="store_true",
        help="Run in production mode (best quality, optimized settings)"
    )
    
    parser.add_argument(
        "--case",
        type=str,
        help="Override the patient case description"
    )
    
    parser.add_argument(
        "--model",
        type=str,
        choices=["gpt-4o", "gpt-3.5-turbo"],
        help="Override the LLM model"
    )
    
    parser.add_argument(
        "--no-save",
        action="store_true",
        help="Disable saving reports to files"
    )
    
    parser.add_argument(
        "--test-config",
        action="store_true",
        help="Test all configurations instead of running the application"
    )
    
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )
    
    args = parser.parse_args()
    
    # Build the command
    cmd_parts = ["python", "run.py"]
    
    # Determine configuration
    if args.debug:
        cmd_parts.extend(["--config-name=config_debug"])
    elif args.production:
        cmd_parts.extend(["--config-name=config_production"])
    
    # Add overrides
    overrides = []
    
    if args.case:
        overrides.append(f'patient_case="{args.case}"')
    
    if args.model:
        overrides.append(f"llm.model={args.model}")
    
    if args.no_save:
        overrides.append("output.save_reports=false")
    
    if args.verbose:
        overrides.append("logging.level=DEBUG")
    
    if overrides:
        cmd_parts.extend(overrides)
    
    # Execute command
    if args.test_config:
        print("Testing configurations...")
        os.system("python test_config.py")
    else:
        print(f"Running: {' '.join(cmd_parts)}")
        os.system(" ".join(cmd_parts))

if __name__ == "__main__":
    main()
