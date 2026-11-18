import pytest
from app.models import Product
from app.extensions import db
from app.services.product_service import (
    ProductService,
    normalize_product_name,
    compact_key,
    tokenize_name,
)
from app.agent.nodes import resolve_product


@pytest.fixture
def anker_catalog(app):
    """Seed test database with the exact Anker scenario and variants."""
    with app.app_context():
        # Clear existing products to ensure clean testing environment
        Product.query.delete()

        p11 = Product(
            id=11,
            name="anker r50i",
            description="True wireless earbuds with 10mm drivers and 30-hour playtime.",
            price=29.99,
            category="Earbuds",
            stock_quantity=25,
            is_active=True,
        )
        p14 = Product(
            id=14,
            name="anker r50i NC",
            description="Active noise cancelling wireless earbuds with multi-mode ANC.",
            price=49.99,
            category="Earbuds",
            stock_quantity=18,
            is_active=True,
        )
        p20 = Product(
            id=20,
            name="Samsung Galaxy S24 Ultra",
            description="Flagship smartphone with AI and S-Pen.",
            price=1199.99,
            category="Smartphones",
            stock_quantity=10,
            is_active=True,
        )
        p30 = Product(
            id=30,
            name="iPhone 15",
            description="Apple iPhone 15 with A16 Bionic chip and USB-C.",
            price=799.99,
            category="Smartphones",
            stock_quantity=12,
            is_active=True,
        )

        db.session.add_all([p11, p14, p20, p30])
        db.session.commit()

        yield app


def test_normalization_helpers():
    assert normalize_product_name("   Anker   R50i  ") == "anker r50i"
    assert normalize_product_name("anker-r50i") == "anker r50i"
    assert normalize_product_name("Samsung Galaxy S-24 Ultra!") == "samsung galaxy s 24 ultra"
    assert compact_key("Anker R-50i NC") == "ankerr50inc"
    assert compact_key("   anker   r50i   ") == "ankerr50i"
    assert tokenize_name("anker r50i NC") == ["anker", "r50i", "nc"]


def test_anker_r50i_matches_product_11_only(anker_catalog):
    """Root cause test case: 'anker r50i' must return Product 11 ONLY,

    never Product 14 ('anker r50i NC').
    """
    with anker_catalog.app_context():
        result = ProductService.match_product("anker r50i")
        assert result["success"] is True
        assert result["product_id"] == 11
        assert result["product"].name == "anker r50i"
        assert result["match_type"] == "exact"
        assert result["is_ambiguous"] is False
        assert len(result["candidates"]) == 1


def test_anker_r50i_nc_matches_product_14_only(anker_catalog):
    """Test case: 'anker r50i NC' must return Product 14 ONLY."""
    with anker_catalog.app_context():
        result = ProductService.match_product("anker r50i NC")
        assert result["success"] is True
        assert result["product_id"] == 14
        assert result["product"].name == "anker r50i NC"
        assert result["match_type"] == "exact"
        assert result["is_ambiguous"] is False


def test_anker_broad_query_triggers_ambiguity(anker_catalog):
    """Test case: 'anker' matches both earbuds and must trigger ambiguity handling."""
    with anker_catalog.app_context():
        result = ProductService.match_product("anker")
        assert result["success"] is False
        assert result["is_ambiguous"] is True
        candidate_ids = [p.id for p in result["candidates"]]
        assert 11 in candidate_ids
        assert 14 in candidate_ids
        assert "Did you mean one of these?" in result["error"]
        assert "anker r50i" in result["error"]
        assert "anker r50i NC" in result["error"]


def test_anker_r50i_case_does_not_select_earbuds(anker_catalog):
    """Test case: 'anker r50i case' must NOT incorrectly select the base earbuds."""
    with anker_catalog.app_context():
        result = ProductService.match_product("anker r50i case")
        assert result["success"] is False
        assert result["product_id"] is None
        assert "not found" in result["error"].lower()


def test_capitalization_tolerance(anker_catalog):
    """Test case: Different capitalization produces identical matching result."""
    with anker_catalog.app_context():
        r1 = ProductService.match_product("ANKER R50I")
        r2 = ProductService.match_product("aNkEr r50I")
        assert r1["success"] is True
        assert r2["success"] is True
        assert r1["product_id"] == 11
        assert r2["product_id"] == 11


def test_whitespace_tolerance(anker_catalog):
    """Test case: Extra whitespace produces identical matching result."""
    with anker_catalog.app_context():
        result = ProductService.match_product("   anker     r50i   ")
        assert result["success"] is True
        assert result["product_id"] == 11


def test_hyphen_formatting_tolerance(anker_catalog):
    """Test case: Common formatting variations like hyphens match correctly."""
    with anker_catalog.app_context():
        result = ProductService.match_product("anker r-50i")
        assert result["success"] is True
        assert result["product_id"] == 11


def test_unknown_product_returns_proper_not_found(anker_catalog):
    """Test case: Unknown product returns proper not-found response."""
    with anker_catalog.app_context():
        result = ProductService.match_product("quantum teleportation pad x9")
        assert result["success"] is False
        assert result["product"] is None
        assert result["product_id"] is None
        assert "not found" in result["error"].lower()


def test_empty_or_whitespace_query(anker_catalog):
    with anker_catalog.app_context():
        result = ProductService.match_product("   ")
        assert result["success"] is False
        assert "could not be identified" in result["error"].lower()


def test_resolve_product_agent_node_anker_r50i(anker_catalog):
    """Verify the agent's resolve_product node directly handles the Anker bug."""
    with anker_catalog.app_context():
        state = {"product_name": "anker r50i"}
        resolved = resolve_product(state)
        assert resolved.get("product_id") == 11
        assert "error" not in resolved


def test_resolve_product_agent_node_anker_r50i_nc(anker_catalog):
    with anker_catalog.app_context():
        state = {"product_name": "anker r50i NC"}
        resolved = resolve_product(state)
        assert resolved.get("product_id") == 14
        assert "error" not in resolved


def test_resolve_product_agent_node_ambiguity(anker_catalog):
    with anker_catalog.app_context():
        state = {"product_name": "anker"}
        resolved = resolve_product(state)
        assert "error" in resolved
        assert "Did you mean one of these?" in resolved["error"]
        assert "product_id" not in resolved


def test_resolve_product_agent_node_case_accessory(anker_catalog):
    with anker_catalog.app_context():
        state = {"product_name": "anker r50i case"}
        resolved = resolve_product(state)
        assert "error" in resolved
        assert "not found" in resolved["error"].lower()
        assert "product_id" not in resolved


def test_natural_queries_with_brand_and_category(anker_catalog):
    """Verify natural customer inquiries resolve properly to catalog products."""
    with anker_catalog.app_context():
        # Brand in description: "Apple iPhone 15" -> iPhone 15 (ID 30)
        r_apple = ProductService.match_product("Apple iPhone 15")
        assert r_apple["success"] is True
        assert r_apple["product_id"] == 30

        # Category synonym: "anker r50i earbuds" -> ID 11
        r_anker_buds = ProductService.match_product("anker r50i earbuds")
        assert r_anker_buds["success"] is True
        assert r_anker_buds["product_id"] == 11

        # Category synonym: "Samsung S24 Ultra phone" -> ID 20
        r_samsung = ProductService.match_product("Samsung S24 Ultra phone")
        assert r_samsung["success"] is True
        assert r_samsung["product_id"] == 20


def test_alias_exact_matching(anker_catalog):
    """Test alias matching when product has aliases configured."""
    with anker_catalog.app_context():
        p11 = db.session.get(Product, 11)
        p11.aliases = "soundcore r50i, anker true wireless"

        result = ProductService.match_product("soundcore r50i")
        assert result["success"] is True
        assert result["product_id"] == 11
        assert result["match_type"] == "alias"


def test_alias_ambiguity_when_multiple_products_share_alias(anker_catalog):
    """When multiple products match an alias, ambiguity should be flagged."""
    with anker_catalog.app_context():
        p11 = db.session.get(Product, 11)
        p14 = db.session.get(Product, 14)
        p11.aliases = ["r50i series"]
        p14.aliases = ["r50i series"]

        result = ProductService.match_product("r50i series")
        assert result["success"] is False
        assert result["is_ambiguous"] is True
        assert result["match_type"] == "alias"


def test_variant_mismatch_rejection(anker_catalog):
    """When the query specifies a variant not present in the catalog, do not match base product."""
    with anker_catalog.app_context():
        # Catalog has r50i and r50i NC, but NOT r50i Pro
        result = ProductService.match_product("anker r50i Pro")
        assert result["success"] is False
        assert "not found" in result["error"].lower()

