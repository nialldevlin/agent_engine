#!/usr/bin/env python3
"""Test mini-editor with real Claude API calls.

This script demonstrates how to use the mini-editor with actual LLM integration.
Requires ANTHROPIC_API_KEY environment variable to be set.

Usage:
    export ANTHROPIC_API_KEY="your-api-key-here"
    python3 test_with_llm.py
"""

import sys
import os
from pathlib import Path

# Add repo root to path for imports
_script_dir = Path(__file__).parent
_repo_root = _script_dir.parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from anthropic import Anthropic

# Initialize Anthropic client with your API key
api_key = os.environ.get("ANTHROPIC_API_KEY")
if not api_key:
    print("ERROR: ANTHROPIC_API_KEY environment variable not set")
    print("\nTo use this script:")
    print("  export ANTHROPIC_API_KEY='your-api-key-here'")
    print("  python3 test_with_llm.py")
    sys.exit(1)

client = Anthropic()

def create_document(title: str, instructions: str) -> str:
    """Use Claude to create document content."""
    message = client.messages.create(
        model="claude-3-5-sonnet-20241022",
        max_tokens=1024,
        messages=[
            {
                "role": "user",
                "content": f"""Create a document titled "{title}" with the following instructions:

{instructions}

Format the response as clean markdown ready to save to a .md file."""
            }
        ]
    )
    return message.content[0].text


def main():
    """Main test function."""
    print("\n" + "="*60)
    print("Mini-Editor with Real Claude LLM")
    print("="*60)
    print(f"\n✓ Using Anthropic API key: {api_key[:20]}...")

    # Test 1: Simple document creation
    print("\n" + "-"*60)
    print("Test 1: Creating Python Best Practices Guide")
    print("-"*60)

    title = "Python Best Practices Guide"
    instructions = """Write a concise guide with the following sections:
1. Naming Conventions - best practices for variable and function names
2. Error Handling - proper exception handling patterns
3. Performance Optimization - common optimization techniques

Include code examples for each section."""

    print(f"\nTitle: {title}")
    print(f"Instructions: {instructions}")
    print("\nCalling Claude API...")

    try:
        content = create_document(title, instructions)
        print("\n✓ Claude Response:")
        print("-" * 60)
        print(content)
        print("-" * 60)

        # Save to file
        output_file = Path(_script_dir) / "python_best_practices.md"
        output_file.write_text(content)
        print(f"\n✓ Saved to: {output_file}")

    except Exception as e:
        print(f"\n✗ Error: {e}")
        sys.exit(1)

    # Test 2: Another document
    print("\n" + "-"*60)
    print("Test 2: Creating Docker Quick Reference")
    print("-"*60)

    title = "Docker Quick Reference"
    instructions = """Create a quick reference card for Docker commands covering:
- Container management (run, stop, remove, logs)
- Image management (build, tag, push, pull)
- Common patterns and best practices

Keep it concise with practical examples."""

    print(f"\nTitle: {title}")
    print("Calling Claude API...")

    try:
        content = create_document(title, instructions)
        print("\n✓ Claude Response:")
        print("-" * 60)
        print(content)
        print("-" * 60)

        # Save to file
        output_file = Path(_script_dir) / "docker_quick_ref.md"
        output_file.write_text(content)
        print(f"\n✓ Saved to: {output_file}")

    except Exception as e:
        print(f"\n✗ Error: {e}")
        sys.exit(1)

    print("\n" + "="*60)
    print("✓ All tests completed successfully!")
    print("="*60)
    print(f"\nGenerated files:")
    print(f"  - python_best_practices.md")
    print(f"  - docker_quick_ref.md")


if __name__ == "__main__":
    main()
