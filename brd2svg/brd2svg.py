# Metadata
version = '0.0.1b.1'

#!/usr/bin/env python3
import sys
import os
import copy
from lxml import etree

SUBPARTS_DIR = os.path.join(os.path.dirname(__file__), "..", "subparts", "breadboard")

def usage():
    print(f"Usage: python {os.path.basename(__file__)} filename.brd")
    sys.exit(1)

def parse_brd_file(path):
    parser = etree.XMLParser(remove_blank_text=True)
    with open(path, "rb") as f:
        tree = etree.parse(f, parser)
    return tree.getroot()

def extract_board_outline(root):
    plain = root.find(".//plain")
    if plain is None:
        print("No <plain> element found for board outline.")
        return None

    points = []
    for wire in plain.findall("wire"):
        x1 = float(wire.get("x1"))
        y1 = float(wire.get("y1"))
        x2 = float(wire.get("x2"))
        y2 = float(wire.get("y2"))
        points.append((x1, y1))
        points.append((x2, y2))

    if not points:
        print("No wires found in <plain> for board outline.")
        return None

    seen = set()
    unique_points = []
    for p in points:
        if p not in seen:
            unique_points.append(p)
            seen.add(p)

    return unique_points

def bounding_box(points):
    xs, ys = zip(*points)
    return min(xs), min(ys), max(xs), max(ys)

def extract_components(root, board_max_y):
    comps = []
    for elem in root.findall(".//elements/element"):
        name = elem.get("name")
        package = elem.get("package")
        if not (name and package):
            continue
        x = float(elem.get("x", "0"))
        y = float(elem.get("y", "0"))
        rot = elem.get("rot", "R0")
        # Flip Y to SVG coordinate system
        y = board_max_y - y
        comps.append((name, package, x, y, rot))
    return comps

def match_svg(package_name):
    svg_path = os.path.join(SUBPARTS_DIR, f"{package_name}.svg")
    if os.path.isfile(svg_path):
        return svg_path
    return None

def parse_svg(svg_path):
    parser = etree.XMLParser(remove_blank_text=True)
    try:
        tree = etree.parse(svg_path, parser)
        return tree.getroot()
    except Exception as e:
        print(f"Error parsing SVG {svg_path}: {e}")
        return None

def create_svg_root(minX, minY, maxX, maxY):
    SVG_NS = "http://www.w3.org/2000/svg"
    NSMAP = {None: SVG_NS}
    width = maxX - minX
    height = maxY - minY
    width_in = width / 1000.0  # mils to inches
    height_in = height / 1000.0

    svg = etree.Element("svg", nsmap=NSMAP)
    # SVG should always start at 0,0 for Fritzing
    svg.attrib['width'] = f"{width_in}in"
    svg.attrib['height'] = f"{height_in}in"
    svg.attrib['viewBox'] = f"0 0 {width} {height}"
    svg.attrib['version'] = "1.1"
    return svg

def build_transform(x, y, rot_str):
    # Start with translation
    transform = f"translate({x},{y})"
    # Rotation and mirroring
    if rot_str.startswith("M"):
        # Mirrored
        angle = 0
        if rot_str.startswith("MR"):
            angle = int(rot_str[2:])
        else:
            angle = int(rot_str[1:])
        transform += f" scale(-1,1) rotate({angle})"
    elif rot_str.startswith("R"):
        angle = int(rot_str[1:])
        transform += f" rotate({angle})"
    return transform

def combine_svgs(components, board_outline=None):
    bminX, bminY, bmaxX, bmaxY = (0, 0, 2000, 2000)
    if board_outline:
        bminX, bminY, bmaxX, bmaxY = bounding_box(board_outline)

    svg_root = create_svg_root(bminX, bminY, bmaxX, bmaxY)

    # ---- Fritzing-compatible: Everything inside <g id="breadboard"> ----
    breadboard_g = etree.Element("g", id="breadboard")
    svg_root.append(breadboard_g)

    # Create a top-level group with transform to translate board min coords to 0,0
    g_root = etree.Element("g")  # No offset needed
    breadboard_g.append(g_root)
    # -------------------------------------------------------------------

    # Add board outline wires (flipped Y)
    if board_outline is not None:
        # Use bounding box max Y to flip Y coords
        _, _, _, maxY = bounding_box(board_outline)
        plain = root.find(".//plain")
        if plain is not None:
            for wire in plain.findall("wire"):
                x1 = float(wire.get("x1"))
                y1 = maxY - float(wire.get("y1"))
                x2 = float(wire.get("x2"))
                y2 = maxY - float(wire.get("y2"))
                line = etree.Element("line", x1=str(x1), y1=str(y1), x2=str(x2), y2=str(y2))
                line.attrib['style'] = "stroke:#000000;stroke-width:10"
                g_root.append(line)

    # Add components with transforms
    for name, package, x, y, rot in components:
        svg_path = match_svg(package)
        if not svg_path:
            print(f"Warning: No SVG for package '{package}' (component {name})")
            continue

        sub_svg_root = parse_svg(svg_path)
        if sub_svg_root is None:
            print(f"Warning: Failed to parse SVG for {package}")
            continue

        # Remove width/height/viewBox to embed properly
        sub_svg_root.attrib.pop('width', None)
        sub_svg_root.attrib.pop('height', None)
        sub_svg_root.attrib.pop('viewBox', None)

        part_svg = copy.deepcopy(sub_svg_root)

        g_comp = etree.Element("g", id=name)
        g_comp.attrib["transform"] = build_transform(x, y, rot)

        for c in list(part_svg):
            g_comp.append(c)
        g_root.append(g_comp)

    return svg_root

def main():
    if len(sys.argv) != 2:
        usage()

    brd_path = sys.argv[1]
    if not brd_path.lower().endswith(".brd") or not os.path.isfile(brd_path):
        print(f"Error: '{brd_path}' is not a valid .brd file.")
        usage()

    global root
    root = parse_brd_file(brd_path)

    board_outline = extract_board_outline(root)
    _, _, _, bmaxY = bounding_box(board_outline) if board_outline else (0, 0, 2000, 2000)

    components = extract_components(root, bmaxY)

    if not components:
        print("No components found in .brd file.")
        sys.exit(0)

    print(f"Found {len(components)} components.")

    final_svg = combine_svgs(components, board_outline=board_outline)

    base_name = os.path.splitext(os.path.basename(brd_path))[0]
    output_path = os.path.join(os.path.dirname(brd_path), f"{base_name}-output.svg")

    tree = etree.ElementTree(final_svg)
    tree.write(output_path, pretty_print=True, xml_declaration=True, encoding="UTF-8")
    print(f"Output saved to: {output_path}")

if __name__ == "__main__":
    main()
