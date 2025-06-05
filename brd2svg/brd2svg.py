#!/usr/bin/env python3

import sys
import os
import copy
import re
from lxml import etree

# Paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SUBPARTS_DIR = os.path.join(SCRIPT_DIR, "..", "subparts", "breadboard")

USAGE_MSG = f"""Usage:
  python brd2svg.py <file.brd>

Description:
  Converts Eagle .brd components to a combined SVG breadboard layout.
  Looks for subpart SVGs in: {os.path.normpath(SUBPARTS_DIR)}
  Output saved as <inputfile>-output.svg
"""

# Regex for extracting numbers from SVG path data
FLOAT_RE = re.compile(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?")

def usage():
    print(USAGE_MSG)
    sys.exit(1)

def parse_brd_file(brd_path):
    try:
        tree = etree.parse(brd_path)
        return tree.getroot()
    except (etree.XMLSyntaxError, OSError) as e:
        print(f"Error reading or parsing '{brd_path}': {e}")
        sys.exit(1)

def extract_components(root):
    # Extract elements with (name, package)
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

def parse_svg(svg_path):
    try:
        parser = etree.XMLParser(remove_comments=True)
        tree = etree.parse(svg_path, parser)
        return tree.getroot()
    except (etree.XMLSyntaxError, OSError) as e:
        print(f"Error parsing SVG '{svg_path}': {e}")
        return None

def add_offset_to_path_d(d_attr, x_off, y_off):
    # This is a simplified approach: adds x_off to all X coords, y_off to all Y coords
    # SVG path commands alternate letters and numbers
    # We'll split numbers, offset pairs accordingly
    
    tokens = FLOAT_RE.findall(d_attr)
    if not tokens:
        return d_attr
    
    # Convert tokens to float
    nums = list(map(float, tokens))
    
    # Heuristic: path coords come in pairs (x,y)
    # Add offset to each pair (x+ x_off, y + y_off)
    new_coords = []
    i = 0
    while i < len(nums):
        x = nums[i] + x_off
        y = nums[i+1] + y_off if (i+1) < len(nums) else 0
        new_coords.append(f"{x:.3f}")
        new_coords.append(f"{y:.3f}")
        i += 2
    
    # Now reconstruct the d string by replacing the numbers with new ones
    # We'll replace numbers in original string in order
    def replacer(match):
        return new_coords.pop(0)
    
    new_d = FLOAT_RE.sub(replacer, d_attr)
    return new_d

def offset_svg_coords(svg_root, x_off, y_off):
    # Modify coordinates inside SVG elements by adding x_off, y_off
    # Common attributes: x, y, cx, cy, points, d (path)
    
    # For all elements recursively
    for elem in svg_root.iter():
        # x and y
        if 'x' in elem.attrib:
            try:
                elem.attrib['x'] = str(float(elem.attrib['x']) + x_off)
            except:
                pass
        if 'y' in elem.attrib:
            try:
                elem.attrib['y'] = str(float(elem.attrib['y']) + y_off)
            except:
                pass
        # cx and cy (circle, ellipse)
        if 'cx' in elem.attrib:
            try:
                elem.attrib['cx'] = str(float(elem.attrib['cx']) + x_off)
            except:
                pass
        if 'cy' in elem.attrib:
            try:
                elem.attrib['cy'] = str(float(elem.attrib['cy']) + y_off)
            except:
                pass
        # points (polyline, polygon)
        if 'points' in elem.attrib:
            points = elem.attrib['points'].strip()
            # points format: "x1,y1 x2,y2 ..."
            new_points = []
            for pt in points.split():
                if ',' in pt:
                    px, py = pt.split(',')
                    try:
                        pxn = float(px) + x_off
                        pyn = float(py) + y_off
                        new_points.append(f"{pxn},{pyn}")
                    except:
                        new_points.append(pt)
                else:
                    new_points.append(pt)
            elem.attrib['points'] = " ".join(new_points)
        # path d attribute
        if 'd' in elem.attrib:
            try:
                elem.attrib['d'] = add_offset_to_path_d(elem.attrib['d'], x_off, y_off)
            except:
                pass

def combine_svgs(components, positions):
    # Create root svg element
    SVG_NS = "http://www.w3.org/2000/svg"
    NSMAP = {None: SVG_NS}
    
    # Calculate canvas size (auto or fixed)
    width = 2000  # mils (2 inch) arbitrary default for now
    height = 2000

    root_svg = etree.Element("svg", nsmap=NSMAP)
    root_svg.attrib['width'] = str(width)
    root_svg.attrib['height'] = str(height)
    root_svg.attrib['viewBox'] = f"0 0 {width} {height}"
    root_svg.attrib['version'] = "1.1"
    
    for i, (name, package) in enumerate(components):
        svg_path = match_svg(package)
        if not svg_path:
            print(f"Warning: No SVG for package '{package}' (component {name})")
            continue

        sub_svg_root = parse_svg(svg_path)
        if sub_svg_root is None:
            print(f"Warning: Failed to parse SVG for {package}")
            continue
        
        # Remove width/height attributes on subpart SVG root (to avoid conflicting)
        sub_svg_root.attrib.pop('width', None)
        sub_svg_root.attrib.pop('height', None)
        sub_svg_root.attrib.pop('viewBox', None)

        # Make a deep copy of sub_svg_root (to avoid modifying original)
        part_svg = copy.deepcopy(sub_svg_root)

        # Apply offset to all coords in part_svg
        x_off, y_off = positions[i]
        offset_svg_coords(part_svg, x_off, y_off)

        # Wrap part_svg children into a <g id="{name}">
        g = etree.Element("g", id=name)
        # Move all children of part_svg into g
        children = list(part_svg)
        for c in children:
            g.append(c)
        # Append group to root svg
        root_svg.append(g)

    return root_svg

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

    print(f"Found {len(components)} components.")

    # For demo, place components on grid with 500 mil spacing
    positions = []
    grid_spacing = 500  # mils
    cols = 10
    for i in range(len(components)):
        x = (i % cols) * grid_spacing
        y = (i // cols) * grid_spacing
        positions.append((x, y))

    final_svg = combine_svgs(components, positions)

    # Write output file
    base_name = os.path.splitext(os.path.basename(brd_path))[0]
    output_path = os.path.join(os.path.dirname(brd_path), f"{base_name}-output.svg")

    tree = etree.ElementTree(final_svg)
    tree.write(output_path, pretty_print=True, xml_declaration=True, encoding="UTF-8")
    print(f"Output saved to: {output_path}")

if __name__ == "__main__":
    main()
