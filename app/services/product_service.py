import re
from app.models import Product
from app.extensions import db
from rapidfuzz import process, fuzz


ACCESSORY_KEYWORDS = {
    "case", "cases", "cover", "covers", "charger", "chargers", "charging",
    "cable", "cables", "cord", "cords", "protector", "protectors",
    "strap", "straps", "band", "bands", "skin", "skins", "pouch", "pouches",
    "sleeve", "sleeves", "stand", "stands", "mount", "mounts", "dock", "docks",
    "adapter", "adapters", "replacement", "tip", "tips", "eartip", "eartips",
    "holder", "holders",
}

VARIANT_KEYWORDS = {
    "nc", "anc", "pro", "max", "ultra", "plus", "mini", "lite", "se", "fe",
    "prime", "air", "play", "sport", "active", "cellular", "wifi", "lte", "5g",
    "edition", "duo", "zoom", "edge",
}

CATEGORY_SYNONYMS = {
    "phone": {"smartphones", "smartphone", "phones", "mobile", "mobiles", "cellphone"},
    "phones": {"smartphones", "smartphone", "phone", "mobile", "mobiles"},
    "smartphone": {"smartphones", "smartphone", "phone", "phones", "mobile", "mobiles"},
    "smartphones": {"smartphones", "smartphone", "phone", "phones", "mobile", "mobiles"},
    "mobile": {"smartphones", "smartphone", "phone", "phones", "mobile", "mobiles"},
    "earbuds": {"earbuds", "earbud", "earphones", "earphone", "headphones", "headphone", "audio"},
    "earbud": {"earbuds", "earbud", "earphones", "earphone", "headphones", "headphone", "audio"},
    "earphones": {"earbuds", "earbud", "earphones", "earphone", "headphones", "headphone", "audio"},
    "headphones": {"earbuds", "earbud", "earphones", "earphone", "headphones", "headphone", "audio", "headset"},
    "headset": {"earbuds", "earbud", "earphones", "earphone", "headphones", "headphone", "audio", "headset"},
    "laptop": {"laptops", "laptop", "notebook", "notebooks", "computer", "computers", "pc"},
    "laptops": {"laptops", "laptop", "notebook", "notebooks", "computer", "computers", "pc"},
}

COMMON_FILLERS = {
    "the", "a", "an", "and", "or", "for", "with", "in", "on", "at", "to", "by",
    "of", "buy", "get", "want", "need", "purchase", "order", "price", "cost",
    "please", "can", "i", "me", "new", "original", "device", "item", "product",
    "black", "white", "silver", "gray", "grey", "blue", "red", "gold",
}


def normalize_product_name(text: str | None) -> str:
    """Normalize text for consistent product matching:

    - Lowercase.
    - Trim outer whitespace.
    - Replace non-alphanumeric punctuation and underscores with space.
    - Collapse multiple whitespace characters into a single space.
    - Preserve meaningful product identifiers and model suffixes.
    """
    if not text:
        return ""
    cleaned = text.lower().strip()
    cleaned = re.sub(r"[^\w\s]|_", " ", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


def compact_key(text: str | None) -> str:
    """Extract a compact alphanumeric key for format-tolerant equality (e.g.

    'r-50i' vs 'r50i').
    """
    if not text:
        return ""
    return re.sub(r"[^a-z0-9]", "", text.lower())


def tokenize_name(text: str | None) -> list[str]:
    """Split normalized text into word/identifier tokens."""
    norm = normalize_product_name(text)
    return norm.split() if norm else []


class ProductService:

    @staticmethod
    def get_product(product_id: int):
        return Product.query.filter_by(
            id=product_id,
            is_active=True,
        ).first()

    @staticmethod
    def search_products(query: str | None = None, category: str | None = None):
        products_query = Product.query.filter_by(is_active=True)

        if query:
            search_pattern = f"%{query}%"

            products_query = products_query.filter(
                db.or_(
                    Product.name.ilike(search_pattern),
                    Product.description.ilike(search_pattern),
                )
            )

        if category:
            products_query = products_query.filter(
                Product.category.ilike(category)
            )

        return products_query.order_by(Product.name).all()

    @staticmethod
    def fuzzy_search_products(query: str, threshold: int = 65):
        """Fuzzy-match query against all active product names using rapidfuzz.

        Returns a list of (Product, score) tuples sorted by descending score,
        filtered to those above `threshold` (0-100 scale).
        """
        all_products = Product.query.filter_by(is_active=True).all()

        if not all_products:
            return []

        # Build a map: name -> Product
        name_to_product = {p.name: p for p in all_products}

        results = process.extract(
            query,
            name_to_product.keys(),
            scorer=fuzz.token_sort_ratio,
            limit=5,
        )

        matches = [
            (name_to_product[name], score)
            for name, score, _ in results
            if score >= threshold
        ]

        return matches

    @classmethod
    def match_product(cls, query: str | None, active_only: bool = True) -> dict:
        """Deterministic product matching pipeline with the following priority:

        1. Normalization: Lowercase, trim whitespace, normalize spaces, handle
        punctuation, preserve meaningful identifiers and suffixes.
        2. Exact matching: Compare normalized names and compact keys using equality.
        If exactly one product matches, return that product only.
        Do not include longer product names that merely contain the requested name.
        3. Alias matching: Check product aliases if defined. Exact alias matches are treated
        as strong matches.
        4. Partial matching: Run only when no exact or alias match exists.
        Ranks candidates by relevance, verifies token coverage, and avoids treating
        incompatible substring matches (such as accessories like 'case') as relevant.
        Protects against accessory false positives while properly recognizing brand names
        and category descriptors.
        5. Ambiguity handling: Ask for clarification only when multiple genuinely plausible
        candidates remain. Return a proper not-found response otherwise.
        """
        if not query or not query.strip():
            return {
                "success": False,
                "product": None,
                "product_id": None,
                "candidates": [],
                "match_type": "none",
                "is_ambiguous": False,
                "error": "Product name could not be identified.",
            }

        raw_query = query.strip()
        norm_query = normalize_product_name(raw_query)
        comp_query = compact_key(raw_query)
        query_tokens = set(tokenize_name(raw_query))

        products = (
            cls.list_active_products() if active_only
            else Product.query.order_by(Product.name).all()
        )

        if not products:
            return {
                "success": False,
                "product": None,
                "product_id": None,
                "candidates": [],
                "match_type": "none",
                "is_ambiguous": False,
                "error": f"Product '{raw_query}' was not found.",
            }

        # ------------------------------------------------------------------
        # Stage 2: Exact matching
        # ------------------------------------------------------------------
        # Exact by normalized name
        exact_matches = [
            p for p in products
            if normalize_product_name(p.name) == norm_query
        ]

        # Format-tolerant exact match via compact key (e.g. "anker r-50i" vs "anker r50i")
        if not exact_matches and comp_query:
            exact_matches = [
                p for p in products
                if compact_key(p.name) == comp_query
            ]

        if len(exact_matches) == 1:
            prod = exact_matches[0]
            return {
                "success": True,
                "product": prod,
                "product_id": prod.id,
                "candidates": [prod],
                "match_type": "exact",
                "is_ambiguous": False,
                "error": None,
            }
        elif len(exact_matches) > 1:
            options = ", ".join(f"{p.name} (ID: {p.id})" for p in exact_matches[:3])
            return {
                "success": False,
                "product": None,
                "product_id": None,
                "candidates": exact_matches,
                "match_type": "exact",
                "is_ambiguous": True,
                "error": f"Multiple products matched '{raw_query}': {options}. Please specify which one you mean.",
            }

        # ------------------------------------------------------------------
        # Stage 3: Alias matching
        # ------------------------------------------------------------------
        alias_matches = []
        for p in products:
            aliases = getattr(p, "aliases", None)
            if not aliases:
                continue
            if isinstance(aliases, str):
                alias_list = [a.strip() for a in aliases.split(",") if a.strip()]
            elif isinstance(aliases, (list, tuple, set)):
                alias_list = [str(a).strip() for a in aliases if str(a).strip()]
            else:
                alias_list = []

            for alias in alias_list:
                norm_alias = normalize_product_name(alias)
                comp_alias = compact_key(alias)
                if norm_alias == norm_query or (comp_query and comp_alias == comp_query):
                    alias_matches.append(p)
                    break

        if len(alias_matches) == 1:
            prod = alias_matches[0]
            return {
                "success": True,
                "product": prod,
                "product_id": prod.id,
                "candidates": [prod],
                "match_type": "alias",
                "is_ambiguous": False,
                "error": None,
            }
        elif len(alias_matches) > 1:
            options = ", ".join(f"{p.name}" for p in alias_matches[:3])
            return {
                "success": False,
                "product": None,
                "product_id": None,
                "candidates": alias_matches,
                "match_type": "alias",
                "is_ambiguous": True,
                "error": f"Multiple products matched '{raw_query}': {options}. Please clarify which one you mean.",
            }

        # ------------------------------------------------------------------
        # Stage 4: Partial matching & relevance ranking
        # ------------------------------------------------------------------
        query_accessories = {qt for qt in query_tokens if qt in ACCESSORY_KEYWORDS}
        query_variants = {qt for qt in query_tokens if qt in VARIANT_KEYWORDS}

        scored_candidates = []
        for p in products:
            p_norm = normalize_product_name(p.name)
            p_name_tokens = set(tokenize_name(p.name))
            p_cat_tokens = set(tokenize_name(getattr(p, "category", "") or ""))
            p_desc_tokens = set(tokenize_name((getattr(p, "description", "") or "")[:300]))

            # 1. Accessory Guard: If the query specifically requests an accessory
            # (e.g. "case"), but the candidate is not an accessory, disqualify it.
            if query_accessories:
                prod_has_acc = any(
                    acc in p_name_tokens or acc in p_cat_tokens
                    for acc in query_accessories
                )
                if not prod_has_acc:
                    continue

            # 2. Variant Guard: If the query explicitly specifies a model variant
            # (e.g. "pro", "ultra", "nc"), but the candidate lacks that variant,
            # disqualify this candidate so it cannot falsely match a different model.
            if query_variants:
                missing_variants = [
                    v for v in query_variants
                    if not any(fuzz.ratio(v, pt) >= 80 for pt in p_name_tokens)
                ]
                if missing_variants:
                    continue

            # 3. Candidate Variant Detection: Notice if the candidate has a variant
            # modifier in its name (e.g. "nc" in "anker r50i NC") that the query lacked.
            candidate_variants = {pt for pt in p_name_tokens if pt in VARIANT_KEYWORDS}
            unrequested_variants = candidate_variants - query_variants

            # 4. Token Coverage Check: Every non-filler query token should match
            # either the product name, category/synonym, or description (e.g. brand).
            unmatched_tokens = []
            for qt in query_tokens:
                if qt in COMMON_FILLERS or qt in query_accessories:
                    continue

                # Match against product name
                best_name_score = max((fuzz.ratio(qt, pt) for pt in p_name_tokens), default=0)
                if best_name_score >= 75:
                    continue

                # Match against category / synonyms
                best_cat_score = max((fuzz.ratio(qt, pt) for pt in p_cat_tokens), default=0)
                if best_cat_score >= 75:
                    continue
                cat_syns = CATEGORY_SYNONYMS.get(qt, set())
                if any(syn in p_cat_tokens for syn in cat_syns):
                    continue

                # Match against description (e.g. brand name like "Apple" in "Apple iPhone 15")
                best_desc_score = max((fuzz.ratio(qt, pt) for pt in p_desc_tokens), default=0)
                if best_desc_score >= 80:
                    continue

                unmatched_tokens.append(qt)

            # If any specific non-filler query token has zero match anywhere in product context,
            # disqualify the product.
            if unmatched_tokens:
                continue

            # 5. Calculate Relevance Score
            ts_score = fuzz.token_sort_ratio(norm_query, p_norm)
            tset_score = fuzz.token_set_ratio(norm_query, p_norm)

            p_base_tokens = p_name_tokens - candidate_variants
            base_tokens_in_query = sum(
                1 for pt in p_base_tokens
                if any(fuzz.ratio(pt, qt) >= 80 for qt in query_tokens)
            )
            base_coverage = base_tokens_in_query / max(len(p_base_tokens), 1)

            name_tokens_in_query = sum(
                1 for pt in p_name_tokens
                if any(fuzz.ratio(pt, qt) >= 80 for qt in query_tokens)
            )
            name_coverage = name_tokens_in_query / max(len(p_name_tokens), 1)

            is_subset = query_tokens.issubset(p_name_tokens)
            if is_subset and len(query_tokens) < len(p_name_tokens):
                # Broad query (e.g. "anker" matching "anker r50i" and "anker r50i NC")
                len_ratio = len(norm_query) / max(len(p_norm), 1)
                base_score = 75.0 + 15.0 * len_ratio + (5.0 if p_norm.startswith(norm_query) else 0.0)
            else:
                base_score = 0.5 * ts_score + 0.5 * tset_score
                # Coverage bonus if all product name tokens appear in query
                if name_coverage >= 1.0:
                    base_score = max(base_score, 85.0)

            # Penalty if candidate has unrequested variant suffixes (e.g. "nc" when query asked for base model)
            if unrequested_variants and base_coverage >= 0.8:
                base_score -= 15.0 * len(unrequested_variants)

            # Prefix bonus if candidate starts with normalized query
            if not is_subset and p_norm.startswith(norm_query):
                base_score += 5.0

            if base_score >= 60.0:
                scored_candidates.append((p, base_score))

        if not scored_candidates:
            return {
                "success": False,
                "product": None,
                "product_id": None,
                "candidates": [],
                "match_type": "none",
                "is_ambiguous": False,
                "error": f"Product '{raw_query}' was not found.",
            }

        scored_candidates.sort(key=lambda item: item[1], reverse=True)
        best_prod, best_score = scored_candidates[0]
        second_score = scored_candidates[1][1] if len(scored_candidates) > 1 else 0

        # ------------------------------------------------------------------
        # Stage 5: Ambiguity handling
        # ------------------------------------------------------------------
        # Single candidate or best candidate is clearly dominant
        if len(scored_candidates) == 1 or (best_score >= 80 and (best_score - second_score) >= 12):
            return {
                "success": True,
                "product": best_prod,
                "product_id": best_prod.id,
                "candidates": [best_prod],
                "match_type": "partial",
                "is_ambiguous": False,
                "error": None,
            }

        # Multiple genuinely plausible candidates remain:
        top_candidates = [p for p, sc in scored_candidates if sc >= (best_score - 10)][:4]
        options = ", ".join(f"{p.name}" for p in top_candidates)
        return {
            "success": False,
            "product": None,
            "product_id": None,
            "candidates": top_candidates,
            "match_type": "partial",
            "is_ambiguous": True,
            "error": f"Did you mean one of these? {options}",
        }

    @staticmethod
    def check_availability(product_id: int, quantity: int):
        product = ProductService.get_product(product_id)

        if not product:
            return {
                "success": False,
                "error": "Product not found.",
            }

        if quantity <= 0:
            return {
                "success": False,
                "error": "Quantity must be greater than zero.",
            }

        return {
            "success": True,
            "product_id": product.id,
            "product_name": product.name,
            "requested_quantity": quantity,
            "available_quantity": product.stock_quantity,
            "in_stock": product.stock_quantity >= quantity,
        }

    @staticmethod
    def list_active_products():
        return Product.query.filter_by(
            is_active=True
        ).order_by(Product.name).all()

    @staticmethod
    def get_best_sellers(category: str | None = None, limit: int = 5):
        from app.models import OrderItem
        from sqlalchemy import func

        units_sold = func.coalesce(func.sum(OrderItem.quantity), 0).label("units_sold")

        query = (
            db.session.query(Product, units_sold)
            .outerjoin(OrderItem, OrderItem.product_id == Product.id)
            .filter(Product.is_active == True)
        )

        if category:
            query = query.filter(Product.category.ilike(f"%{category}%"))

        results = (
            query
            .group_by(Product.id)
            .order_by(db.desc("units_sold"), Product.name)
            .limit(limit)
            .all()
        )

        return results
