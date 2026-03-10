"""Help Center API endpoints.

Provides public access to help articles and categories.
No authentication required for better SEO and user support.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from flask import Blueprint, Response, jsonify, request

from app.utils.http import safe_route

logger = logging.getLogger(__name__)

help_api = Blueprint("help_api", __name__)

# Cache for help data
_help_data_cache: dict[str, Any] | None = None


def _load_help_data() -> dict[str, Any]:
    """Load help articles data from JSON file with caching."""
    global _help_data_cache

    if _help_data_cache is not None:
        return _help_data_cache

    try:
        data_path = Path(__file__).resolve().parent.parent.parent.parent / "static" / "data" / "help_articles.json"
        with open(data_path, encoding="utf-8") as f:
            _help_data_cache = json.load(f)
        return _help_data_cache
    except FileNotFoundError:
        logger.error("Help articles data file not found")
        return {"categories": []}
    except json.JSONDecodeError as e:
        logger.error("Invalid JSON in help articles file: %s", e)
        return {"categories": []}


def _api_success(data: Any = None, status: int = 200):
    """Return standardized success response."""
    return jsonify({"ok": True, "data": data, "error": None}), status


def _api_error(message: str, status: int = 400):
    """Return standardized error response."""
    return jsonify({"ok": False, "data": None, "error": {"message": message}}), status


@help_api.route("/categories", methods=["GET"])
@safe_route("Failed to retrieve help categories")
def get_categories() -> Response:
    """Get all help categories with their article counts.

    Returns:
        JSON list of categories with id, title, icon, description, and article_count
    """
    data = _load_help_data()

    categories = []
    for cat in data.get("categories", []):
        categories.append(
            {
                "id": cat.get("id"),
                "title": cat.get("title"),
                "icon": cat.get("icon"),
                "description": cat.get("description"),
                "article_count": len(cat.get("articles", [])),
            }
        )

    return _api_success(categories)


@help_api.route("/articles", methods=["GET"])
@safe_route("Failed to retrieve help articles")
def get_articles() -> Response:
    """Get help articles with optional filtering and search.

    Query Parameters:
        category: Filter by category ID
        search: Search term for title, summary, and keywords
        limit: Maximum number of results (default: 50)
        offset: Offset for pagination (default: 0)

    Returns:
        JSON list of articles with id, category, title, summary
    """
    data = _load_help_data()

    category_filter = request.args.get("category")
    search_term = request.args.get("search", "").lower().strip()
    limit = min(int(request.args.get("limit", 50)), 100)
    offset = int(request.args.get("offset", 0))

    all_articles = []
    for cat in data.get("categories", []):
        for article in cat.get("articles", []):
            article_data = {
                "id": article.get("id"),
                "category": cat.get("id"),
                "category_title": cat.get("title"),
                "category_icon": cat.get("icon"),
                "title": article.get("title"),
                "summary": article.get("summary"),
                "keywords": article.get("keywords", []),
            }

            # Apply category filter
            if category_filter and cat.get("id") != category_filter:
                continue

            # Apply search filter
            if search_term:
                searchable = (
                    article.get("title", "").lower()
                    + " "
                    + article.get("summary", "").lower()
                    + " "
                    + " ".join(article.get("keywords", []))
                )
                if search_term not in searchable:
                    continue

            all_articles.append(article_data)

    # Apply pagination
    total = len(all_articles)
    paginated = all_articles[offset : offset + limit]

    return _api_success(
        {"articles": paginated, "total": total, "limit": limit, "offset": offset, "has_more": offset + limit < total}
    )


@help_api.route("/article/<category>/<article_id>", methods=["GET"])
@safe_route("Failed to retrieve help article")
def get_article(category: str, article_id: str) -> Response:
    """Get a single help article with full content.

    Args:
        category: Category ID
        article_id: Article ID

    Returns:
        JSON article with id, category, title, summary, keywords, content
    """
    data = _load_help_data()

    for cat in data.get("categories", []):
        if cat.get("id") == category:
            for article in cat.get("articles", []):
                if article.get("id") == article_id:
                    return _api_success(
                        {
                            "id": article.get("id"),
                            "category": cat.get("id"),
                            "category_title": cat.get("title"),
                            "category_icon": cat.get("icon"),
                            "title": article.get("title"),
                            "summary": article.get("summary"),
                            "keywords": article.get("keywords", []),
                            "content": article.get("content", ""),
                        }
                    )

    return _api_error("Article not found", 404)


@help_api.route("/search", methods=["GET"])
@safe_route("Failed to search help articles")
def search_articles() -> Response:
    """Search help articles across all categories.

    Query Parameters:
        q: Search query (required)
        limit: Maximum results (default: 20)

    Returns:
        JSON list of matching articles with relevance ranking
    """
    query = request.args.get("q", "").lower().strip()
    limit = min(int(request.args.get("limit", 20)), 50)

    if not query:
        return _api_error("Search query is required")

    data = _load_help_data()
    results = []

    for cat in data.get("categories", []):
        for article in cat.get("articles", []):
            score = 0
            title = article.get("title", "").lower()
            summary = article.get("summary", "").lower()
            keywords = [k.lower() for k in article.get("keywords", [])]
            content = article.get("content", "").lower()

            # Score based on match location
            if query in title:
                score += 10
            if query in summary:
                score += 5
            if any(query in k for k in keywords):
                score += 8
            if query in content:
                score += 1

            # Exact keyword match bonus
            if query in keywords:
                score += 15

            if score > 0:
                results.append(
                    {
                        "id": article.get("id"),
                        "category": cat.get("id"),
                        "category_title": cat.get("title"),
                        "title": article.get("title"),
                        "summary": article.get("summary"),
                        "score": score,
                    }
                )

    # Sort by score descending
    results.sort(key=lambda x: x["score"], reverse=True)

    return _api_success({"results": results[:limit], "total": len(results), "query": query})
