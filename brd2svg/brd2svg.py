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

def combine_svgs(components, positions, board_outline=None):
    SVG_NS = "http://www.w3.org/2000/svg"
    NSMAP = {None: SVG_NS}

    # Calculate canvas size if board_outline given, else default 2000 x 2000
    if board_outline:
        xs, ys = zip(*board_outline)
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        width = max_x - min_x + 200  # Add margin 200 mils
        height = max_y - min_y + 200
        viewbox_x = min_x - 100
        viewbox_y = min_y - 100
    else:
        width = 2000
        height = 2000
        viewbox_x = 0
        viewbox_y = 0

    root_svg = etree.Element("svg", nsmap=NSMAP)
    root_svg.attrib['width'] = str(width)
    root_svg.attrib['height'] = str(height)
    root_svg.attrib['viewBox'] = f"{viewbox_x} {viewbox_y} {width} {height}"
    root_svg.attrib['version'] = "1.1"

    # Draw board outline polygon if available
    if board_outline:
        points_str = " ".join(f"{x},{y}" for x, y in board_outline)
        polygon = etree.Element("polygon", points=points_str)
        polygon.attrib['style'] = "fill:#e0e0e0;stroke:#000000;stroke-width:5"
        root_svg.append(polygon)

    # Add components as before...
    for i, (name, package) in enumerate(components):
        svg_path = match_svg(package)
        if not svg_path:
            print(f"Warning: No SVG for package '{package}' (component {name})")
            continue

        sub_svg_root = parse_svg(svg_path)
        if sub_svg_root is None:
            print(f"Warning: Failed to parse SVG for {package}")
            continue

        sub_svg_root.attrib.pop('width', None)
        sub_svg_root.attrib.pop('height', None)
        sub_svg_root.attrib.pop('viewBox', None)

        part_svg = copy.deepcopy(sub_svg_root)

        x_off, y_off = positions[i]
        offset_svg_coords(part_svg, x_off, y_off)

        g = etree.Element("g", id=name)
        children = list(part_svg)
        for c in children:
            g.append(c)
        root_svg.append(g)

    return root_svg

def extract_board_outline(root):
    # Try to find the <plain> element inside <drawing> or <board>
    plain = root.find(".//plain")
    if plain is None:
        print("No <plain> element found for board outline.")
        return None
    
    points = []

    # Usually the outline is defined by <wire> elements connected in a loop
    for wire in plain.findall("wire"):
        x1 = float(wire.get("x1"))
        y1 = float(wire.get("y1"))
        x2 = float(wire.get("x2"))
        y2 = float(wire.get("y2"))
        # Add start and end points (converted to mils)
        points.append( (x1, y1) )
        points.append( (x2, y2) )
    
    if not points:
        print("No wires found in <plain> for board outline.")
        return None

    # Remove duplicates and order points to form a polygon path
    # For now, just remove duplicates and keep order, better algorithms can be added later
    seen = set()
    unique_points = []
    for p in points:
        if p not in seen:
            unique_points.append(p)
            seen.add(p)

    # Convert Eagle units (assuming mm) to mils (0.001 inch)
    # Eagle default units may be mm; adjust here if you know units (for now assume mm)
    # 1 mm = 39.3701 mils (0.001 inch)
    MM_TO_MILS = 39.3701
    polygon_points = []
    for x, y in unique_points:
        px = x * MM_TO_MILS
        py = y * MM_TO_MILS
        polygon_points.append( (px, py) )

    return polygon_points

def main():
    if len(sys.argv) != 2:
        usage()

    brd_path = sys.argv[1]
    if not brd_path.lower().endswith(".brd") or not os.path.isfile(brd_path):
        print(f"Error: '{brd_path}' is not a valid .brd file.")
        usage()

    root = parse_brd_file(brd_path)
    components = extract_components(root)
    board_outline = extract_board_outline(root)

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

    final_svg = combine_svgs(components, positions, board_outline=board_outline)

    base_name = os.path.splitext(os.path.basename(brd_path))[0]
    output_path = os.path.join(os.path.dirname(brd_path), f"{base_name}-output.svg")

    tree = etree.ElementTree(final_svg)
    tree.write(output_path, pretty_print=True, xml_declaration=True, encoding="UTF-8")
    print(f"Output saved to: {output_path}")

if __name__ == "__main__":
    main()
