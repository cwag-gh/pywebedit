#!/usr/bin/env python3
import argparse
import sys
import re
from pathlib import Path

def replace_between_tags(file_path: str,
                         start_tag: str,
                         end_tag: str,
                         new_content: str,
                         in_place: bool = False,
                         output_file: str | None = None) -> str:
    """
    Replace content between specified tags in a file.

    Args:
        file_path: Path to the input file
        start_tag: Opening tag to match
        end_tag: Closing tag to match
        new_content: Content to insert between tags
        in_place: If True, modifies the file directly; if False, prints to stdout
        output_file: If provided, writes the modified content to this file instead of stdout

    Returns:
        Modified content as string

    Raises:
        FileNotFoundError: If input file doesn't exist
        ValueError: If tags aren't found or are malformed
    """
    try:
        with open(file_path, 'r') as f:
            content = f.read()
    except FileNotFoundError:
        raise FileNotFoundError(f"Input file not found: {file_path}")

    # Escape special regex characters in tags
    start_tag_escaped = re.escape(start_tag)
    end_tag_escaped = re.escape(end_tag)

    # Pattern to match content between tags, including the tags
    pattern = f"({start_tag_escaped})(.*?)({end_tag_escaped})"

    # Search for the pattern
    match = re.search(pattern, content, re.DOTALL)
    if not match:
        raise ValueError(f"Tags not found: {start_tag} ... {end_tag}")

    # Replace the content between tags
    new_text = content[:match.start(2)] + new_content + content[match.end(2):]

    if in_place:
        assert output_file is None, 'Cannot use in-place and output file together'
        with open(file_path, 'w') as f:
            f.write(new_text)
    elif output_file is not None:
        with open(output_file, 'w') as f:
            f.write(new_text)
    else:
        print(new_text)

    return new_text

def main():
    parser = argparse.ArgumentParser(
        description='Replace content between specified tags in a file.'
    )
    parser.add_argument('file', help='Input file path')
    parser.add_argument('start_tag', help='Opening tag')
    parser.add_argument('end_tag', help='Closing tag')
    parser.add_argument('content_file', help='File containing the new content to insert')
    parser.add_argument('-i', '--in-place', action='store_true',
                        help='Modify file in place instead of printing to stdout')
    parser.add_argument('-o', '--output', help='Output file path', nargs=1)

    args = parser.parse_args()

    # Make sure -i and -o are not used together
    if args.in_place and args.output:
        parser.error('Cannot use -i and -o together')

    try:
        # Read the new content from file
        try:
            with open(args.content_file, 'r') as f:
                new_content = f.read()
        except FileNotFoundError:
            raise FileNotFoundError(f"Content file not found: {args.content_file}")

        replace_between_tags(
            args.file,
            args.start_tag,
            args.end_tag,
            new_content,
            args.in_place,
            args.output[0] if args.output else None
        )
    except (FileNotFoundError, ValueError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
