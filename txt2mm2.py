#!/usr/bin/env python
#
# A simple text to freemind conversion program
#
# See README for copyright and licensing information.
#
import io
import sys, time, encodings, re
from xml.dom import minidom

import uuid


def bailout(msg, line=None):
    global filename
    if filename == '-':
        filename = '<stdin>'
    if line is not None:
        sys.stderr.write('%s:%d: %s\n' % (filename, line, msg))
    else:
        sys.stderr.write('%s: %s\n' % (filename, msg))
    sys.exit(1)


# Try to load a suitable celementtree incarnation. This is supposed to work for
# both Python 2.4 (both python and C version) and Python 2.5
try:
    import xml.etree.ElementTree as et  # python 2.5
except ImportError:
    try:
        import cElementTree as et  # python 2.4 celementtree
    except ImportError:
        import elementtree.ElementTree as et  # python 2.4 elementtree

try:
    et
except NameError:
    bailout('No suitable ElementTree package found. Install python-elementtree (default in python 2.5).')

creation_time = str(int(time.time() * 1000))


def indent(elem, level=0):
    # Indentation helper from http://effbot.org/zone/element-lib.htm
    i = "\n" + level * "  "
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = i + "  "
        for elem in elem:
            indent(elem, level + 1)
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
    else:
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = i


def set_node_properties(node, text, level):
    # convert literal \n into newlines
    if r'\n' in text:
        text = text.replace(r'\n', '\n')

    # parse line for markdown url links
    if r'[' in text and r'](' in text and r']' in text:  # find [text](link) formatted markdown
        match = re.search("\[(\w.*)\]\((\w.*)\)$", text)
        if match:
            text = match.group(1)
            link = match.group(2)
            node.set('LINK', link)
    elif r'<' in text and r'>' in text:  # find <link> formatted markdown
        match = re.search("\<(\w.*)\>$", text)
        if match:
            text = match.group(1)
            link = match.group(1)
            node.set('LINK', link)

    node.set('CREATED', '0')
    node.set('ID', uuid.uuid4().hex[-32:])
    node.set('MODIFIED', '0')
    if level != 0:
        node.set("POSITION", "right")
    node.set('TEXT', text)


def convert_lines_into_mm(lines, out_fp):
    # read all lines and get the indent
    lines_with_level = []
    toplevel_seen = False

    level = 0
    oldlevel = 0
    line_no = 0
    for line in lines:
        line_no += 1
        oldlevel = level

        # Skip empty lines
        if not line.strip(): continue

        # Skip comments
        if line.startswith('#'): continue
        if line.startswith('//'): continue

        if toplevel_seen and not line.startswith('\t'):
            bailout('All lines except for the first should start with a tab.', line_no)

        level = 0
        while line.startswith('\t'):
            level += 1
            line = line[1:]

        if level - oldlevel > 1:
            bailout('Cannot indent more than one level at a time.', line_no)

        if level == 0:
            toplevel_seen = True

        line = line.rstrip()
        lines_with_level.append((level, line))

    # now we have a list of (level, line) tuples.
    # just loop over it and do magic xml thingies :)

    curlevel = -1
    topnode = et.Element('map')
    topnode.set('version', '0.9.0')
    curpath = [topnode]
    lastnode = None
    for level, line in lines_with_level:
        if level == curlevel:
            # Add element as sibling to the current path. This means tail of
            # the path is replace by a new node.
            n = et.SubElement(curpath[-2], 'node')
            set_node_properties(n, line, level)
            curpath[-1] = n
        elif level > curlevel:
            # Add child element to current node.
            n = et.SubElement(curpath[-1], 'node')
            curpath.append(n)
            set_node_properties(n, line, level)
        else:
            # One ore more levels up the tree. Pop items from the current path
            # and add a new node.
            for i in range(curlevel - level + 1):
                curpath.pop(-1)
            n = et.SubElement(curpath[-1], 'node')
            curpath.append(n)
            set_node_properties(n, line, level)

        curlevel = level

    # indent(topnode)
    tree = et.ElementTree(topnode)
    # rough_string = et.tostring(topnode, encoding='utf-8', method='xml', declaration=False)
    stream = io.BytesIO()
    et.ElementTree(topnode).write(stream, encoding='utf-8',
                                  xml_declaration=False, short_empty_elements=True)
    rough_string = stream.getvalue()
    # 用 minidom 解析该字符串，并得到 'pretty' 打印的版本
    reparsed = minidom.parseString(rough_string)
    # 输出没有缩进和换行的 XML 字符串

    xml_str = reparsed.toprettyxml(indent="\t", encoding=None)

    if out_fp == sys.stdout:
        sys.stdout.write(xml_str)
    else:
        with open(out_fp, 'w', encoding='utf-8') as ff:
            ff.write(xml_str)
            ff.write('\n')




if __name__ == '__main__':
    global filename
    global outfile
    try:
        filename = sys.argv[1]
        if filename == '-':
            # stdin
            lines = [line for line in sys.stdin.readlines()]
        else:
            # user-specified filename
            with open(filename, 'r', encoding='utf-8') as f:
                lines = [line for line in f.readlines()]
    except IndexError:
        # stdin
        lines = [line for line in sys.stdin.readlines()]

    if len(sys.argv) > 2:
        outfile = sys.argv[2]
    else:
        outfile = sys.stdout

    convert_lines_into_mm(lines, outfile)
