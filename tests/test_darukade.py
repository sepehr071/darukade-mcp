from urllib.parse import parse_qs

import httpx
import pytest
from conftest import fixture, html, page

pytestmark = pytest.mark.anyio

TOOLS = {
    "dr_search",
    "dr_cheapest",
    "dr_product",
    "dr_reviews",
    "dr_related",
    "dr_categories",
    "dr_brands",
    "dr_forms",
    "dr_compare",
    "dr_home",
    "dr_articles",
    "dr_article",
}
LIST = "/api/search/search"


def listing(name):
    """Route handler serving a saved list page as the JSON the site's filter UI gets (categoryMataData itself)."""
    return lambda request: httpx.Response(200, json=fixture(name)["categoryMataData"])


def query(request):
    """The filter params the tool sent inside the `queryParams` value."""
    return {k: v[0] for k, v in parse_qs(request.url.params["queryParams"]).items()}


async def test_all_tools_are_read_only_and_described(client):
    tools = (await client.list_tools()).tools
    assert {t.name for t in tools} == TOOLS
    for t in tools:
        assert t.annotations.read_only_hint is True, t.name
        assert t.title and t.description.splitlines()[0].endswith("."), t.name
        assert "title" not in str(t.input_schema.get("properties", {}).values()), t.name


async def test_api_calls_send_the_headers_of_the_sites_own_fetch(client, api):
    api[LIST] = listing("list_search.json")
    await client.call_tool("dr_search", {})
    h = api.calls[0].headers  # Next.js fetch(): same-origin, Accept */*, no Origin
    assert (h["accept"], h["sec-fetch-site"], h["sec-fetch-mode"], h["sec-fetch-dest"], h["priority"]) == (
        "*/*",
        "same-origin",
        "cors",
        "empty",
        "u=1, i",
    )
    assert h["referer"] == "https://darukade.com/" and "origin" not in h and h["accept-language"].startswith("fa-IR")


async def test_search_builds_the_sites_filter_params(client, api):
    api[LIST] = listing("list_search.json")
    r = (
        await client.call_tool(
            "dr_search",
            {
                "query": "ملاتونین",
                "category": [860, 1379],
                "brand": [315],
                "min_price": 1000,
                "max_price": 500000,
                "in_stock": True,
                "discounted": True,
                "page": 2,
                "limit": 3,
            },
        )
    ).structured_content
    q = query(api.calls[0])
    assert q == {"w": "ملاتونین", "g": "860,1379", "b": "315", "co": "1000,500000", "a": "t", "d": "t", "p": "2"}
    assert r["count"] == 3 and len(r["products"]) == 3 and r["total"] > 3 and r["page"] == 2
    p = r["products"][0]
    assert p["url"].startswith("https://darukade.com/products/") and p["price"] and p["in_stock"] is True


async def test_search_card_reports_discount_and_unknown_price(client, api):
    api[LIST] = lambda request: httpx.Response(
        200,
        json={
            "filters": {"pages": {"totalProductCount": 2, "totalPage": 1}, "list": []},
            "products": [
                {
                    "id": 1,
                    "faName": "الف",
                    "orginalCost": 1000,
                    "discountCost": 900,
                    "discountPercent": 10,
                    "storeState": True,
                },
                {"id": 2, "faName": "ب", "orginalCost": 0, "discountCost": 0, "storeState": False},
            ],
        },
    )
    a, b = (await client.call_tool("dr_search", {})).structured_content["products"]
    assert (a["price"], a["price_before_discount"], a["discount_percent"]) == (900, 1000, 10)
    assert "price" not in b and b["in_stock"] is False


async def test_text_search_sort_is_done_locally_over_scanned_pages(client, api):
    api[LIST] = listing("list_search.json")
    r = (await client.call_tool("dr_search", {"query": "ملاتونین", "sort": "cheapest", "limit": 24})).structured_content
    prices = [p["price"] for p in r["products"]]
    assert prices == sorted(prices) and "note" in r


async def test_cheapest_in_category_uses_site_sort_and_drops_unpriced(client, api):
    api[LIST] = listing("list_cheapest.json")
    r = (await client.call_tool("dr_cheapest", {"category": [1379], "limit": 5})).structured_content
    q = query(api.calls[0])
    assert q["s"] == "5" and q["a"] == "t" and q["g"] == "1379"
    assert r["count"] == 5 and all(p["price"] for p in r["products"])


async def test_cheapest_needs_a_filter(client, api):
    r = await client.call_tool("dr_cheapest", {})
    assert r.is_error


async def test_product_supplement_has_ingredients_dosage_and_properties(client, api):
    api["/products/x/p-1276"] = page("product_supplement.json")
    r = (await client.call_tool("dr_product", {"product": "1276"})).structured_content
    assert r["name"] == "هیرویت" and r["brand"] == "Health Aid" and r["price"] > 0
    assert r["ingredients"][0]["english"].startswith("Vitamin B1") and r["ingredients"][0]["amount"] == "10 mg"
    assert "صبحانه" in r["dosage"] and r["properties"]["کشور سازنده"] == "ایران"
    assert r["category_path"] and r["warnings"] and "<" not in r["description"]


async def test_product_variants_are_listed_with_selected_one(client, api):
    path = "/products/cosmetic-sunscreen-for-all-skin-types-1379/cream-sunscreen-cream-spf50-2084"
    api[path] = page("product_variants.json")
    r = (await client.call_tool("dr_product", {"product": "https://darukade.com" + path})).structured_content
    assert len(r["variants"]) == 3 and [v.get("selected") for v in r["variants"]].count(True) == 1
    assert r["price"] == next(v["price"] for v in r["variants"] if v.get("selected"))


async def test_product_rejects_bad_reference_and_unknown_product(client, api):
    assert (await client.call_tool("dr_product", {"product": "not a product"})).is_error
    api["/products/x/p-5"] = lambda request: html({"error": "x"})
    r = await client.call_tool("dr_product", {"product": "5"})
    assert r.is_error and "No product" in r.content[0].text


async def test_reviews_pages_and_pharmacy_answers_deduplicated(client, api):
    api["/products/x/p-2084"] = page("product_variants.json")
    r = (await client.call_tool("dr_reviews", {"product": "2084"})).structured_content
    assert r["questions_total"] == 11 and r["rating"] == 3.2
    answer = r["questions"][0]["answers"]
    assert answer[0]["pharmacy"] is True and len(answer) == len({a["text"] for a in answer})


async def test_related_groups(client, api):
    api["/api/products/fetchrelated"] = fixture("related.json")
    r = (await client.call_tool("dr_related", {"product": "2084", "limit": 2})).structured_content
    assert api.calls[0].url.params["id"] == "2084"
    assert r["same_brand"][0]["brand"] == "Ellaro" and len(r["same_brand"]) <= 2


async def test_categories_and_brands_from_the_filter_lists(client, api):
    api[LIST] = listing("filters.json")
    top = (await client.call_tool("dr_categories", {})).structured_content
    assert {c["id"] for c in top["categories"]} == {860, 918}
    hits = (await client.call_tool("dr_categories", {"query": "اصلاح"})).structured_content["categories"]
    assert hits[0]["id"] == 918
    kids = (await client.call_tool("dr_categories", {"parent": 918})).structured_content
    assert kids["parent"]["id"] == 918 and kids["categories"]
    assert (await client.call_tool("dr_categories", {"parent": 5})).is_error
    b = (await client.call_tool("dr_brands", {"query": "ellaro"})).structured_content
    assert b["brands"][0]["id"] == 315 and b["brands"][0]["name"] == "الارو"


async def test_http_error_becomes_a_tool_error(client, api):
    api[LIST] = lambda request: httpx.Response(403)
    r = await client.call_tool("dr_search", {"query": "x"})
    assert r.is_error and "403" in r.content[0].text


async def test_search_form_gift_and_name_sort_params(client, api):
    api[LIST] = listing("list_search.json")
    r = (
        await client.call_tool("dr_search", {"query": "x", "form": [28, 54], "gift": True, "sort": "name"})
    ).structured_content
    assert query(api.calls[0]) == {"w": "x", "ty": "28,54", "v": "t", "s": "1", "p": "1"}
    assert "ignores" in r["note"]


async def test_text_search_sort_scans_all_pages_and_pages_the_result(client, api):
    meta = fixture("list_search.json")["categoryMataData"]
    meta["filters"]["pages"]["totalPage"] = 3

    def route(request):
        page = query(request)["p"]
        rows = [{**p, "id": int(page) * 1000 + i} for i, p in enumerate(meta["products"])]
        return httpx.Response(200, json={**meta, "products": rows})

    api[LIST] = route
    r = (await client.call_tool("dr_search", {"query": "x", "sort": "cheapest", "limit": 24})).structured_content
    assert sorted(query(c)["p"] for c in api.calls) == ["1", "2", "3"]
    assert r["pages"] >= 2 and "note" in r
    prices = [p["price"] for p in r["products"]]
    assert prices == sorted(prices)


async def test_forms_lists_product_types(client, api):
    api[LIST] = listing("filters.json")
    r = (await client.call_tool("dr_forms", {"query": "capsule"})).structured_content
    assert {f["id"] for f in r["forms"]} == {279, 195}
    assert (await client.call_tool("dr_forms", {})).structured_content["count"] == 4


async def test_product_extras_faq_articles_and_serving_unit(client, api):
    api["/products/x/p-1276"] = page("product_supplement.json")
    r = (await client.call_tool("dr_product", {"product": "1276"})).structured_content
    assert r["ingredients_per"] and r["faq"][0]["question"] and r["articles"][0]["url"].startswith("https://")
    assert r["expert_review"] is None
    full = (await client.call_tool("dr_product", {"product": "1276", "full": True})).structured_content
    assert len(full["expert_review"]) > 500


async def test_compare_finds_cheapest_and_common_ingredients(client, api):
    api["/products/x/p-1276"] = page("product_supplement.json")
    api["/products/x/p-2084"] = page("product_variants.json")
    r = (await client.call_tool("dr_compare", {"products": ["1276", "2084"]})).structured_content
    assert [p["id"] for p in r["products"]] == [1276, 2084]
    assert r["cheapest"] == min(r["products"], key=lambda p: p["price"])["id"]
    assert (await client.call_tool("dr_compare", {"products": ["1276"]})).is_error


async def test_brand_profile(client, api):
    api["/brands/x-315"] = page("brand_page.json")
    r = (await client.call_tool("dr_brands", {"id": 315})).structured_content
    assert r["name"] == "الارو" and r["products"] == 77 and r["about"] and r["categories"]
    assert (await client.call_tool("dr_brands", {})).is_error


async def test_home_offers_have_product_ids_and_prices(client, api):
    api["/"] = page("home.json")
    r = (await client.call_tool("dr_home", {"per_group": 2})).structured_content
    first = r["sections"][0]["groups"][0]["products"]
    assert len(first) == 2 and first[0]["id"] > 0 and first[0]["price"] and first[0]["url"].startswith("https://")
    assert r["featured"]


async def test_articles_search_builds_params_and_trims(client, api):
    api["/api/mag/search"] = fixture("articles_list.json")["magCatData"]
    r = (
        await client.call_tool("dr_articles", {"query": "کبد", "category": 5, "sort": "popular", "limit": 3})
    ).structured_content
    p = api.calls[0].url.params
    assert p["targetID"] == "5/0/0" and parse_qs(p["queryParams"]) == {"p": ["1"], "s": ["2"], "w": ["کبد"]}
    assert r["total"] > 100 and r["count"] == 3 and r["articles"][0]["url"].startswith("https://darukade.com/mag/")


async def test_article_reads_text_and_resolves_by_id_or_url(client, api):
    api["/mag/articles/x/x-51"] = page("article.json")
    r = (await client.call_tool("dr_article", {"article": "51", "max_chars": 500})).structured_content
    assert r["title"] and len(r["text"]) == 500 and r["truncated"] is True and "<" not in r["text"]
    assert r["authors"][0]["name"] and r["products"][0]["price"]
    url = "https://darukade.com/mag/articles/illness-5/auxiliary-methods-for-lowering-cholesterol-51"
    assert (await client.call_tool("dr_article", {"article": url})).structured_content["id"] == 51
    assert (await client.call_tool("dr_article", {"article": "no id here"})).is_error
    api["/mag/articles/x/x-9"] = lambda request: html({"articleData": {}})
    assert "No article" in (await client.call_tool("dr_article", {"article": "9"})).content[0].text
