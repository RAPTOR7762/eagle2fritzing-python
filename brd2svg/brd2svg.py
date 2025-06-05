#!/usr/bin/env python3

import sys
import os
from lxml import etree

# Determine the absolute path to the subparts directory
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SUBPARTS_DIR = os.path.join(SCRIPT_DIR, "..", "subparts", "breadboard")

def usage():
    print("Usage:")
    print("  python brd2svg.py file.brd")
    print("\nDescription:")
    print("  Parses an Eagle .brd file and lists breadboard SVG subparts that match component packages.")
    print(f"  Looks for subparts in: {os.path.normpath(SUBPARTS_DIR)}")
    sys.exit(1)

def parse_brd_file(brd_path):
    try:
        tree = etree.parse(brd_path)
        return tree.getroot()
    except (etree.XMLSyntaxError, OSError) as e:
        print(f"Error reading or parsing '{brd_path}': {e}")
        sys.exit(1)

def extract_components(root):
    components = []
    for element in root.xpath(".//element"):
        name = element.get("name")
        package = element.get("package")
        if name and package:
            components.append((name, package))
    return components

def match_svg(package, subparts_dir=SUBPARTS_DIR):
    filename = f"{package}.svg"
    svg_path = os.path.join(subparts_dir, filename)
    return svg_path if os.path.isfile(svg_path) else None

def main():
    if len(sys.argv) != 2:
        usage()

    brd_path = sys.argv[1]

    if not brd_path.lower().endswith(".brd") or not os.path.isfile(brd_path):
        print(f"Error: '{brd_path}' is not a valid .brd file.")
        usage()

    root = parse_brd_file(brd_path)
    components = extract_components(root)

    if not components:
        print("No components found in .brd file.")
        sys.exit(0)

    print("\n**Matched breadboard subparts:**")
    print('=======================================================')
    for name, package in components:
        svg = match_svg(package)
        if svg:
            print(f"✔ {name} ({package}) → {os.path.relpath(svg)}")
        else:
            print(f"✘ {name} ({package}) → No match found")

if __name__ == "__main__":
    main()
