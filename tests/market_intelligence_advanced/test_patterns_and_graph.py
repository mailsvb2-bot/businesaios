from execution.market_intelligence_knowledge_graph import KnowledgeGraphLayer
from execution.market_intelligence_pattern_extractor import ContentOfferPatternExtractor


def test_pattern_extractor_finds_cta_and_prices():
    rows = [
        {'headline': 'Start Free CRM Today', 'copy': 'Start free and save 20%', 'offer': 'Only $19'},
        {'headline': 'Learn More About CRM', 'copy': 'Book now', 'offer': '€29'},
    ]
    patterns = ContentOfferPatternExtractor().extract(rows)
    assert 'start free' in patterns.ctas
    assert any(price in {'19', '29'} for price in patterns.pricing_anchors)


def test_knowledge_graph_builds_edges():
    rows = [{'product_id': 'p1', 'competitor_id': 'c1', 'ad_id': 'a1', 'offer_id': 'o1', 'review_id': 'r1', 'feature_id': 'f1'}]
    edges = KnowledgeGraphLayer().build_edges(rows)
    assert len(edges) >= 4
