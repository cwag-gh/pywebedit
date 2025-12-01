import base64
import os
import json

EXAMPLES = {
    "Getting started": [
        ("hello",       "1) Hello world"),
        ("input0",      "2) Basic input"),
        ("basic_html",  "3) Initial HTML"),
        ("error",       "4) Showing python errors"),
        ("styled_html", "5) Styled HTML"),
        ("bind",        "6) Run python based on events"),
        ("modules",     "7) Organizing code into modules"),
        ("console",     "8) Simple control flow with async"),
    ],
    "Interacting with HTML": [
        ("calculator", "Calculator with styled buttons"),
        ("sort_table", "Table with sortable columns"),
        ("sphere", "Decode messages from Sphere"),
    ],
    "Drawing and animating": [
        ("clock", "Analog clock"),
        ("barcode", "Generate barcodes"),
        ("pythagoras", "Animated geometry proof"),
        ("pixelperfect", "Perfect pixel-aligned drawing"),
        ("springs", "Spring animation with vectors"),
    ],
    "Playing sounds": [
        ("sound", "Local and remote sounds"),
    ],
    "Games with canvas": [
        ("breakout", "Brick breaking"),
        ("lightcycles", "Lightcycles"),
    ],
    "Using javascript libraries": [
        ("pixi", "Fast 2D graphics (pixi.js)"),
        ("three", "3D spinning cube (three.js)"),
    ],
    "Games with pixi.js": [
        ("pixi", "Basic example"),
        ("pixi2", "Starfield with wrapped pixi.js"),
        ("pixi_sound", "Starfield with sound (pixi-sound.js)"),
        ("pixi-sprite", "True pixel-perfect sprites"),
        ("basepygame", "Pygame-like template for pixi+sound games"),
    ],
}

def bundle_examples_to_javascript(output_file: str):
    """Bundle the examples into a single javascript file.

    For each example listed in EXAMPLES, create an entry
    in a javascript data structure that stores the title,
    the help entry, and the example (loaded from html in the examples directory)
    encoded as base64."""

    examples_dir = "./examples"
    result = []
    num_examples = 0

    for category, examples_list in EXAMPLES.items():
        examples_in_category = []
        print(f'  Category: {category}')
        for example_id, help_text in examples_list:
            file_path = os.path.join(examples_dir, f"{example_id}.html")
            try:
                # Read the HTML content
                with open(file_path, "r", encoding="utf-8") as f:
                    html_content = f.read()

                # Encode to base64
                base64_content = base64.b64encode(html_content.encode("utf-8")).decode("utf-8")

                # Add to result
                examples_in_category.append({
                    "id": example_id,
                    "help": help_text,
                    "content": base64_content
                })
                print(f'    Encoded {example_id}')
                num_examples += 1
            except FileNotFoundError:
                print(f"Warning: Example file {file_path} in category {category} not found")
        result.append({
            "category": category,
            "examples": examples_in_category
        })

    # Convert to JavaScript object format
    js_data = "window.EXAMPLES_DATA = " + json.dumps(result, ensure_ascii=False) + ";"

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(js_data)

    print(f"Wrote {len(result)} categories, {num_examples} examples bundled into {output_file}")


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print("Usage: python examples.py <output_file>")
        sys.exit(1)
    bundle_examples_to_javascript(sys.argv[1])
