"""
Tests for the Tovito Trader Platform Mind Map Generator.

Tests cover:
    - Data model completeness and integrity
    - Radial layout computation
    - Mermaid syntax validity
    - HTML self-contained output
    - PNG minimum resolution
    - SVG valid XML
"""

import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from scripts.generate_mindmap import (
    MindMapData,
    MindMapNode,
    MindMapEdge,
    RadialLayout,
    FlowLayout,
    MermaidGenerator,
    MatplotlibGenerator,
    HtmlGenerator,
    DatabaseImpactData,
    BusinessProcessData,
    CATEGORY_COLORS,
    CATEGORY_LABELS,
)


# ============================================================
# FIXTURES
# ============================================================

@pytest.fixture
def data():
    """Build and return a fully populated MindMapData."""
    d = MindMapData()
    d.build()
    return d


@pytest.fixture
def layout(data):
    """Compute and return layout positions."""
    return RadialLayout(data).compute()


@pytest.fixture
def tmp_dir():
    """Create a temporary directory for test outputs."""
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)


# ============================================================
# DATA MODEL TESTS
# ============================================================

class TestDataModel:
    """Tests for MindMapData completeness and integrity."""

    def test_has_root_node(self, data):
        """Root node must exist."""
        assert 'root' in data.nodes
        assert data.nodes['root'].category == 'root'
        assert data.nodes['root'].parent_id is None

    def test_node_count_minimum(self, data):
        """Should have at least 70 nodes for a comprehensive map."""
        assert len(data.nodes) >= 70

    def test_data_flow_edge_count(self, data):
        """Should have at least 20 data flow connections."""
        flow_edges = [e for e in data.edges if e.edge_type == 'dataflow']
        assert len(flow_edges) >= 20

    def test_all_branches_exist(self, data):
        """All 6 major branches must exist under root."""
        branch_ids = {n.id for n in data.get_children('root')}
        expected = {'apps', 'db', 'auto', 'ext', 'wf', 'lib'}
        assert expected == branch_ids

    def test_no_orphan_nodes(self, data):
        """Every non-root node must have a valid parent."""
        for node_id, node in data.nodes.items():
            if node_id == 'root':
                continue
            assert node.parent_id is not None, f"Node '{node_id}' has no parent"
            assert node.parent_id in data.nodes, \
                f"Node '{node_id}' references missing parent '{node.parent_id}'"

    def test_valid_categories(self, data):
        """All nodes must have valid categories."""
        for node in data.nodes.values():
            assert node.category in CATEGORY_COLORS, \
                f"Node '{node.id}' has invalid category '{node.category}'"

    def test_applications_branch(self, data):
        """Applications branch should have 5 apps."""
        apps = data.get_children('apps')
        assert len(apps) == 5

    def test_database_branch_has_tables(self, data):
        """Database branch should have table groups and individual tables."""
        db_groups = data.get_children('db')
        assert len(db_groups) >= 5  # financial, positions, etl, flow, profiles, monitor

        # Check that we have specific table nodes
        table_ids = {n.id for n in data.nodes.values()
                     if n.category == 'database' and data.get_depth(n.id) >= 3}
        expected_tables = {'db_investors', 'db_daily_nav', 'db_transactions',
                           'db_trades', 'db_tax_events', 'db_ffr'}
        assert expected_tables.issubset(table_ids)

    def test_automation_has_nav_pipeline(self, data):
        """Automation branch should have the 7-step NAV pipeline."""
        nav = data.get_children('auto_nav')
        assert len(nav) == 7  # 7 pipeline steps

    def test_external_integrations(self, data):
        """External branch should have TastyTrade, Tradier, Discord, Email, healthchecks."""
        ext_children = {n.id for n in data.get_children('ext')}
        assert 'ext_tt' in ext_children
        assert 'ext_tr' in ext_children
        assert 'ext_discord' in ext_children
        assert 'ext_email' in ext_children
        assert 'ext_hc' in ext_children

    def test_workflows(self, data):
        """Workflows branch should have 6 operational workflows."""
        wf_children = data.get_children('wf')
        assert len(wf_children) == 6

    def test_core_libraries(self, data):
        """Libraries branch should have 7 core library modules."""
        lib_children = data.get_children('lib')
        assert len(lib_children) == 7

    def test_edge_references_valid_nodes(self, data):
        """All edge source/target IDs must reference existing nodes."""
        for edge in data.edges:
            assert edge.source_id in data.nodes, \
                f"Edge source '{edge.source_id}' not found"
            assert edge.target_id in data.nodes, \
                f"Edge target '{edge.target_id}' not found"

    def test_subtree_size(self, data):
        """Root subtree size should equal total leaf count."""
        total_leaves = sum(
            1 for n in data.nodes.values()
            if not data.get_children(n.id)
        )
        root_size = data.get_subtree_size('root')
        assert root_size == total_leaves

    def test_invalid_category_raises(self):
        """Creating a node with invalid category should raise ValueError."""
        with pytest.raises(ValueError, match="Invalid category"):
            MindMapNode('bad', 'Bad Node', 'nonexistent_category')


# ============================================================
# LAYOUT TESTS
# ============================================================

class TestRadialLayout:
    """Tests for the radial layout engine."""

    def test_all_nodes_positioned(self, data, layout):
        """Every node should have a position."""
        assert len(layout) == len(data.nodes)

    def test_root_at_center(self, layout):
        """Root should be at (0, 0)."""
        assert layout['root'] == (0.0, 0.0)

    def test_branches_at_radius_r1(self, data, layout):
        """Branch nodes should be approximately at radius R1."""
        r1 = RadialLayout.R1
        for branch in data.get_children('root'):
            x, y = layout[branch.id]
            dist = (x ** 2 + y ** 2) ** 0.5
            assert abs(dist - r1) < 1.0, \
                f"Branch '{branch.id}' at distance {dist:.1f}, expected ~{r1}"

    def test_no_overlapping_nodes(self, data, layout):
        """No two nodes at the same depth should overlap significantly."""
        min_dist = 40  # minimum distance between same-depth nodes
        by_depth = {}
        for nid in layout:
            depth = data.get_depth(nid)
            by_depth.setdefault(depth, []).append(nid)

        for depth, ids in by_depth.items():
            if depth == 0:
                continue  # root is alone
            for i, id1 in enumerate(ids):
                for id2 in ids[i + 1:]:
                    x1, y1 = layout[id1]
                    x2, y2 = layout[id2]
                    dist = ((x1 - x2) ** 2 + (y1 - y2) ** 2) ** 0.5
                    # Allow some overlap at leaf level (depth 3+)
                    if depth <= 2:
                        assert dist > min_dist, \
                            f"Nodes '{id1}' and '{id2}' too close: {dist:.1f}px"


# ============================================================
# MERMAID GENERATOR TESTS
# ============================================================

class TestMermaidGenerator:
    """Tests for Mermaid diagram output."""

    def test_generates_file(self, data, tmp_dir):
        """Should generate a .md file."""
        path = tmp_dir / 'test.md'
        result = MermaidGenerator(data).generate(path)
        assert result.exists()
        assert result.stat().st_size > 0

    def test_contains_mermaid_block(self, data, tmp_dir):
        """Output should contain mermaid code fences."""
        path = tmp_dir / 'test.md'
        MermaidGenerator(data).generate(path)
        content = path.read_text(encoding='utf-8')
        assert '```mermaid' in content
        assert 'flowchart TB' in content
        assert '```' in content

    def test_contains_subgraphs(self, data, tmp_dir):
        """Output should contain subgraph blocks."""
        path = tmp_dir / 'test.md'
        MermaidGenerator(data).generate(path)
        content = path.read_text(encoding='utf-8')
        assert 'subgraph' in content
        assert 'end' in content

    def test_contains_data_flow_arrows(self, data, tmp_dir):
        """Output should contain dashed arrows for data flows."""
        path = tmp_dir / 'test.md'
        MermaidGenerator(data).generate(path)
        content = path.read_text(encoding='utf-8')
        assert '-.->' in content

    def test_contains_class_definitions(self, data, tmp_dir):
        """Output should contain classDef for each category."""
        path = tmp_dir / 'test.md'
        MermaidGenerator(data).generate(path)
        content = path.read_text(encoding='utf-8')
        for cat in CATEGORY_COLORS:
            assert f'classDef {cat}' in content

    def test_contains_root_node(self, data, tmp_dir):
        """Output should reference the root node."""
        path = tmp_dir / 'test.md'
        MermaidGenerator(data).generate(path)
        content = path.read_text(encoding='utf-8')
        assert 'Tovito Trader' in content


# ============================================================
# MATPLOTLIB GENERATOR TESTS
# ============================================================

class TestMatplotlibGenerator:
    """Tests for PNG and SVG image output."""

    def test_generates_png(self, data, layout, tmp_dir):
        """Should generate a PNG file."""
        png = tmp_dir / 'test.png'
        svg = tmp_dir / 'test.svg'
        MatplotlibGenerator(data, layout).generate(png, svg)
        assert png.exists()
        assert png.stat().st_size > 0

    def test_generates_svg(self, data, layout, tmp_dir):
        """Should generate an SVG file."""
        png = tmp_dir / 'test.png'
        svg = tmp_dir / 'test.svg'
        MatplotlibGenerator(data, layout).generate(png, svg)
        assert svg.exists()
        assert svg.stat().st_size > 0

    def test_png_minimum_resolution(self, data, layout, tmp_dir):
        """PNG should be at least 3000px wide."""
        from PIL import Image
        png = tmp_dir / 'test.png'
        svg = tmp_dir / 'test.svg'
        MatplotlibGenerator(data, layout).generate(png, svg)
        img = Image.open(str(png))
        assert img.width >= 3000, f"PNG width {img.width} is below 3000px minimum"

    def test_svg_valid_xml(self, data, layout, tmp_dir):
        """SVG should be valid XML."""
        png = tmp_dir / 'test.png'
        svg = tmp_dir / 'test.svg'
        MatplotlibGenerator(data, layout).generate(png, svg)
        # Should not raise an exception
        tree = ET.parse(str(svg))
        root = tree.getroot()
        assert root is not None


# ============================================================
# HTML GENERATOR TESTS
# ============================================================

class TestHtmlGenerator:
    """Tests for interactive HTML output."""

    def test_generates_file(self, data, layout, tmp_dir):
        """Should generate an HTML file."""
        path = tmp_dir / 'test.html'
        result = HtmlGenerator(data, layout).generate(path)
        assert result.exists()
        assert result.stat().st_size > 0

    def test_self_contained(self, data, layout, tmp_dir):
        """HTML should be self-contained (only external ref is Tailwind CDN)."""
        path = tmp_dir / 'test.html'
        HtmlGenerator(data, layout).generate(path)
        content = path.read_text(encoding='utf-8')
        # Should contain Tailwind CDN
        assert 'cdn.tailwindcss.com' in content
        # Should not reference any other external scripts or stylesheets
        # Remove the known Tailwind CDN reference before checking
        stripped = content.replace('https://cdn.tailwindcss.com', '')
        assert 'src="http' not in stripped

    def test_contains_nodes_data(self, data, layout, tmp_dir):
        """HTML should contain embedded node data."""
        path = tmp_dir / 'test.html'
        HtmlGenerator(data, layout).generate(path)
        content = path.read_text(encoding='utf-8')
        assert 'const NODES' in content
        assert 'const EDGES' in content
        assert 'Tovito Trader' in content

    def test_contains_interactive_elements(self, data, layout, tmp_dir):
        """HTML should have search, reset, zoom controls."""
        path = tmp_dir / 'test.html'
        HtmlGenerator(data, layout).generate(path)
        content = path.read_text(encoding='utf-8')
        assert 'search-input' in content
        assert 'btn-reset' in content
        assert 'btn-expand' in content
        assert 'btn-collapse' in content

    def test_contains_legend(self, data, layout, tmp_dir):
        """HTML should have a legend section."""
        path = tmp_dir / 'test.html'
        HtmlGenerator(data, layout).generate(path)
        content = path.read_text(encoding='utf-8')
        assert 'legend' in content.lower()
        assert 'LABELS' in content

    def test_contains_svg_canvas(self, data, layout, tmp_dir):
        """HTML should have an SVG element for the mind map."""
        path = tmp_dir / 'test.html'
        HtmlGenerator(data, layout).generate(path)
        content = path.read_text(encoding='utf-8')
        assert '<svg' in content
        assert 'mindmap-svg' in content
        assert 'viewBox' in content


# ============================================================
# INTEGRATION TESTS
# ============================================================

class TestIntegration:
    """End-to-end integration tests."""

    def test_full_pipeline(self, tmp_dir):
        """Full pipeline: build → layout → generate all formats."""
        data = MindMapData()
        data.build()

        layout_engine = RadialLayout(data)
        positions = layout_engine.compute()

        # Mermaid
        md_path = tmp_dir / 'full.md'
        MermaidGenerator(data).generate(md_path)
        assert md_path.exists()

        # PNG + SVG
        png_path = tmp_dir / 'full.png'
        svg_path = tmp_dir / 'full.svg'
        MatplotlibGenerator(data, positions).generate(png_path, svg_path)
        assert png_path.exists()
        assert svg_path.exists()

        # HTML
        html_path = tmp_dir / 'full.html'
        HtmlGenerator(data, positions).generate(html_path)
        assert html_path.exists()

    def test_category_colors_and_labels_match(self):
        """CATEGORY_COLORS and CATEGORY_LABELS should have matching keys."""
        assert set(CATEGORY_COLORS.keys()) == set(CATEGORY_LABELS.keys())


# ============================================================
# DATABASE IMPACT VIEW TESTS
# ============================================================

class TestDatabaseImpact:
    """Tests for the Database Impact focused view."""

    @pytest.fixture
    def db_data(self):
        d = DatabaseImpactData()
        d.build()
        return d

    @pytest.fixture
    def db_layout(self, db_data):
        return FlowLayout(db_data).compute_database_impact()

    def test_has_tables(self, db_data):
        """Should have all 15 database tables as nodes."""
        table_nodes = [n for n in db_data.nodes.values()
                       if n.parent_id == 'db_center']
        assert len(table_nodes) == 15

    def test_has_writers(self, db_data):
        """Should have writer processes."""
        writers = db_data.get_children('writers')
        assert len(writers) >= 8

    def test_has_readers(self, db_data):
        """Should have reader processes."""
        readers = db_data.get_children('readers')
        assert len(readers) >= 6

    def test_write_edges_exist(self, db_data):
        """Should have write flow edges (process → table)."""
        write_edges = [e for e in db_data.edges if e.edge_type == 'dataflow'
                       and e.source_id.startswith('w_')]
        assert len(write_edges) >= 15

    def test_read_edges_exist(self, db_data):
        """Should have read flow edges (table → reader)."""
        read_edges = [e for e in db_data.edges if e.edge_type == 'dataflow'
                      and e.target_id.startswith('r_')]
        assert len(read_edges) >= 15

    def test_all_nodes_positioned(self, db_data, db_layout):
        """Every node should have a position."""
        assert len(db_layout) == len(db_data.nodes)

    def test_three_column_layout(self, db_data, db_layout):
        """Writers should be left, tables center, readers right."""
        writers = db_data.get_children('writers')
        readers = db_data.get_children('readers')
        tables = db_data.get_children('db_center')

        if writers and tables and readers:
            avg_writer_x = sum(db_layout[w.id][0] for w in writers) / len(writers)
            avg_table_x = sum(db_layout[t.id][0] for t in tables) / len(tables)
            avg_reader_x = sum(db_layout[r.id][0] for r in readers) / len(readers)
            assert avg_writer_x < avg_table_x < avg_reader_x

    def test_generates_all_formats(self, db_data, db_layout, tmp_dir):
        """Should generate Mermaid, PNG, SVG, and HTML."""
        MermaidGenerator(db_data).generate(tmp_dir / 'db.md')
        MatplotlibGenerator(db_data, db_layout).generate(
            tmp_dir / 'db.png', tmp_dir / 'db.svg')
        HtmlGenerator(db_data, db_layout).generate(tmp_dir / 'db.html')

        assert (tmp_dir / 'db.md').exists()
        assert (tmp_dir / 'db.png').exists()
        assert (tmp_dir / 'db.svg').exists()
        assert (tmp_dir / 'db.html').exists()

    def test_no_orphan_nodes(self, db_data):
        """Every node should have valid parent references (except roots)."""
        roots = [n for n in db_data.nodes.values() if n.parent_id is None]
        assert len(roots) >= 1
        for node in db_data.nodes.values():
            if node.parent_id is not None:
                assert node.parent_id in db_data.nodes, \
                    f"Node '{node.id}' references missing parent '{node.parent_id}'"


# ============================================================
# BUSINESS PROCESS VIEW TESTS
# ============================================================

class TestBusinessProcess:
    """Tests for the Business Process focused view."""

    @pytest.fixture
    def bp_data(self):
        d = BusinessProcessData()
        d.build()
        return d

    @pytest.fixture
    def bp_layout(self, bp_data):
        return FlowLayout(bp_data).compute_business_process()

    def test_has_seven_processes(self, bp_data):
        """Should have 7 business processes."""
        processes = bp_data.get_children('root')
        assert len(processes) == 7

    def test_process_names(self, bp_data):
        """Should include key business processes."""
        process_ids = {n.id for n in bp_data.get_children('root')}
        assert 'bp_contrib' in process_ids
        assert 'bp_withdraw' in process_ids
        assert 'bp_nav' in process_ids
        assert 'bp_report' in process_ids
        assert 'bp_tax' in process_ids
        assert 'bp_onboard' in process_ids
        assert 'bp_close' in process_ids

    def test_contribution_has_steps(self, bp_data):
        """Contribution process should have numbered steps."""
        # Walk the chain starting from bp_contrib's first child
        contrib_children = bp_data.get_children('bp_contrib')
        assert len(contrib_children) >= 1
        assert '1.' in contrib_children[0].label

    def test_all_nodes_positioned(self, bp_data, bp_layout):
        """Every node should have a position."""
        assert len(bp_layout) == len(bp_data.nodes)

    def test_swim_lane_layout(self, bp_data, bp_layout):
        """Each process should be on a different Y row."""
        processes = bp_data.get_children('root')
        y_positions = set()
        for p in processes:
            _, y = bp_layout[p.id]
            y_positions.add(y)
        # Each process should have a unique Y position
        assert len(y_positions) == len(processes)

    def test_steps_flow_left_to_right(self, bp_data, bp_layout):
        """Within a process, steps should generally move left to right."""
        # Check contribution flow
        contrib_children = bp_data.get_children('bp_contrib')
        if len(contrib_children) >= 2:
            first_child = contrib_children[0]
            # Walk the main chain
            current = first_child
            prev_x = bp_layout[current.id][0]
            while True:
                next_children = bp_data.get_children(current.id)
                if not next_children:
                    break
                current = next_children[0]
                curr_x = bp_layout[current.id][0]
                assert curr_x >= prev_x, \
                    f"Step '{current.id}' goes backwards: {curr_x} < {prev_x}"
                prev_x = curr_x

    def test_generates_all_formats(self, bp_data, bp_layout, tmp_dir):
        """Should generate Mermaid, PNG, SVG, and HTML."""
        MermaidGenerator(bp_data).generate(tmp_dir / 'bp.md')
        MatplotlibGenerator(bp_data, bp_layout).generate(
            tmp_dir / 'bp.png', tmp_dir / 'bp.svg')
        HtmlGenerator(bp_data, bp_layout).generate(tmp_dir / 'bp.html')

        assert (tmp_dir / 'bp.md').exists()
        assert (tmp_dir / 'bp.png').exists()
        assert (tmp_dir / 'bp.svg').exists()
        assert (tmp_dir / 'bp.html').exists()

    def test_node_details_have_metadata(self, bp_data):
        """Process step nodes should have useful metadata in details."""
        # Check that at least some nodes have 'actor' or 'writes' details
        nodes_with_details = [n for n in bp_data.nodes.values()
                              if n.details.get('actor') or n.details.get('writes')]
        assert len(nodes_with_details) >= 10

    def test_no_orphan_nodes(self, bp_data):
        """Every non-root node should have a valid parent."""
        for node in bp_data.nodes.values():
            if node.parent_id is not None:
                assert node.parent_id in bp_data.nodes, \
                    f"Node '{node.id}' references missing parent '{node.parent_id}'"
