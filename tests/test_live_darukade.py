import pytest

pytestmark = [pytest.mark.live, pytest.mark.anyio]


async def test_live_search_filters(client):
    r = (await client.call_tool("dr_search", {"query": "ملاتونین", "in_stock": True, "limit": 5})).structured_content
    assert r["total"] > 20 and len(r["products"]) == 5
    assert all(p["in_stock"] and p["url"].startswith("https://darukade.com/") for p in r["products"]), r


async def test_live_brand_then_search(client):
    b = (await client.call_tool("dr_brands", {"query": "ellaro"})).structured_content["brands"][0]
    assert b["id"] == 315
    r = (await client.call_tool("dr_search", {"brand": [b["id"]], "limit": 5})).structured_content
    assert r["total"] > 20 and all(p["brand"] == "Ellaro" for p in r["products"])


async def test_live_category_cheapest_is_sorted(client):
    c = (await client.call_tool("dr_categories", {"query": "ضد آفتاب انواع پوست"})).structured_content["categories"][0]
    r = (await client.call_tool("dr_cheapest", {"category": [c["id"]], "limit": 6})).structured_content
    prices = [p["price"] for p in r["products"]]
    assert len(prices) == 6 and prices == sorted(prices) and prices[0] > 0, r


async def test_live_product_detail_and_reviews(client):
    r = (await client.call_tool("dr_product", {"product": "1276"})).structured_content
    assert r["name"] == "هیرویت" and r["ingredients"] and r["dosage"]
    rv = (await client.call_tool("dr_reviews", {"product": "1276"})).structured_content
    assert rv["questions"] and rv["questions_total"] > 10


async def test_live_related(client):
    r = (await client.call_tool("dr_related", {"product": "2084", "limit": 3})).structured_content
    assert any(len(v) for k, v in r.items() if k != "id"), r


async def test_live_text_search_sorted_over_all_matches(client):
    r = (await client.call_tool("dr_search", {"query": "ملاتونین", "sort": "cheapest", "limit": 24})).structured_content
    prices = [p["price"] for p in r["products"]]
    assert len(prices) == 24 and prices == sorted(prices) and r["total"] > 200, r


async def test_live_form_filter(client):
    f = (await client.call_tool("dr_forms", {"query": "اسپری"})).structured_content["forms"][0]
    r = (await client.call_tool("dr_search", {"category": [1379], "form": [28], "limit": 3})).structured_content
    assert f["id"] and 0 < r["total"] < 253 and r["products"], r


async def test_live_compare_and_product_extras(client):
    r = (await client.call_tool("dr_compare", {"products": ["1276", "2084"]})).structured_content
    assert len(r["products"]) == 2 and r["products"][0]["ingredients"] and r["cheapest"]
    p = (await client.call_tool("dr_product", {"product": "1276"})).structured_content
    assert p["ingredients_per"] and p["faq"] and p["articles"]


async def test_live_home_brand_profile(client):
    h = (await client.call_tool("dr_home", {})).structured_content
    assert len(h["sections"]) >= 3 and h["sections"][0]["groups"][0]["products"][0]["price"]
    b = (await client.call_tool("dr_brands", {"id": 315})).structured_content
    assert b["name"] == "الارو" and b["products"] > 20 and b["categories"]


async def test_live_articles_then_article(client):
    a = (await client.call_tool("dr_articles", {"query": "ملاتونین", "limit": 3})).structured_content
    assert a["total"] > 5 and a["articles"]
    d = (
        await client.call_tool("dr_article", {"article": a["articles"][0]["url"], "max_chars": 800})
    ).structured_content
    assert d["title"] == a["articles"][0]["title"] and len(d["text"]) > 300 and d["authors"], d
