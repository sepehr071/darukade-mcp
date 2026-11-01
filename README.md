<!-- mcp-name: io.github.sepehr071/darukade-mcp -->

# darukade-mcp: Darukade (داروکده) online pharmacy MCP server for AI agents

**darukade-mcp is an unofficial, read-only MCP server for Darukade (darukade.com), an Iranian online pharmacy.**<br>
Its 12 tools search the product catalog with filters (category, brand, form, price, stock, discount), find the cheapest products,
read a product's price per variant, ingredients, dosage and warnings, compare products, list user questions with the pharmacists'
answers, suggest alternatives, show the home page offers, and search and read the Darukade health magazine.<br>
No API key or account is needed. It works in Claude, Cursor, Copilot and any other MCP client.

[![PyPI](https://img.shields.io/pypi/v/darukade-mcp?color=2563eb)](https://pypi.org/project/darukade-mcp/)
[![License: MIT](https://img.shields.io/badge/license-MIT-16a34a)](https://github.com/sepehr071/darukade-mcp/blob/main/LICENSE)

## For AI agents

- **What:** unofficial MCP server for darukade.com: supplements, vitamins, cosmetics and skin care, baby, medical equipment.
- **Install:** `uvx darukade-mcp` or `claude mcp add darukade -- uvx darukade-mcp`. Transport: stdio. Needs [uv](https://docs.astral.sh/uv/getting-started/installation/).
- **Auth:** none. Optional `DARUKADE_MCP_PROXY` (HTTP proxy URL, or a comma-separated list); system proxy settings are ignored.
- **Access:** read-only. It cannot log in, order or upload prescriptions, so no confirmation is needed before any tool.
- **Tools:** 12, prefixed `dr_`. Typical: `dr_categories` / `dr_brands` / `dr_forms` -> `dr_search` / `dr_cheapest` -> `dr_product` / `dr_compare` -> `dr_reviews` / `dr_related`; or `dr_articles` -> `dr_article`.
- **Output:** compact JSON; prices in Toman after discount; Persian text as the shop has it. Not medical advice.

## Quick start

```bash
claude mcp add darukade -- uvx darukade-mcp
```

Claude Desktop / Cursor: add `{"mcpServers": {"darukade": {"command": "uvx", "args": ["darukade-mcp"]}}}` to the MCP config.

## Tools

| Tool | What it does |
|---|---|
| `dr_search` | Search the catalog by words, category, brand, form, price range, in stock, discounted, gift, with sort and paging |
| `dr_cheapest` | List the lowest-priced products of a category, brand or search, cheapest first |
| `dr_product` | One product: price per variant, stock, brand, ingredients with amounts, dosage, warnings, properties, pharmacy FAQ, magazine articles |
| `dr_compare` | 2-5 products side by side: price, stock, ingredient amounts, dosage, cheapest, common ingredients |
| `dr_reviews` | User comments and questions with the pharmacy's answers, plus the rating summary |
| `dr_related` | Alternatives, similar, same-brand and complementary products with prices |
| `dr_categories` | Category ids (about 60 top-level, 475 sub-categories) for the `category` filter |
| `dr_brands` | Find a brand by name and get its id for the `brand` filter, or read a brand's profile (about text, categories) |
| `dr_forms` | Product form ids (capsule, syrup, cream, spray ...) for the `form` filter |
| `dr_home` | The home page's golden offers, newest, best-selling and most-loved products |
| `dr_articles` | Search the health magazine (about 2,900 articles; category 14 is drug information) |
| `dr_article` | Read one magazine article as text with its author, sources and recommended products |

Example: "cheapest sunscreen for all skin types" -> `dr_categories("ضد آفتاب انواع پوست")` -> `dr_cheapest(category=[1379])`.
The site cannot sort text searches, so a text query with a cheapest/discount sort orders up to 288 matches itself.

## Development

```bash
uv sync
uv run ruff check . && uv run ruff format --check .
uv run python -m pytest -q
uv run python -m pytest -m live -q   # calls the real site
```

Unofficial; not affiliated with Darukade. MIT licensed. Author: Sepehr Radmard (سپهر رادمرد), github.com/sepehr071.
