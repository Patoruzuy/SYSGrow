"""Blog API endpoints.

Provides public access to blog posts and categories.
No authentication required for better SEO.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from flask import Blueprint, Response, jsonify, request

from app.utils.http import safe_route

logger = logging.getLogger(__name__)

blog_api = Blueprint("blog_api", __name__)

# Cache for blog data
_blog_data_cache: dict[str, Any] | None = None


def _load_blog_data() -> dict[str, Any]:
    """Load blog posts data from JSON file with caching."""
    global _blog_data_cache

    if _blog_data_cache is not None:
        return _blog_data_cache

    try:
        data_path = Path(__file__).resolve().parent.parent.parent.parent / "static" / "data" / "blog_posts.json"
        with open(data_path, encoding="utf-8") as f:
            _blog_data_cache = json.load(f)
        return _blog_data_cache
    except FileNotFoundError:
        logger.error("Blog posts data file not found")
        return {"posts": [], "categories": []}
    except json.JSONDecodeError as e:
        logger.error("Invalid JSON in blog posts file: %s", e)
        return {"posts": [], "categories": []}


def _api_success(data: Any = None, status: int = 200):
    """Return standardized success response."""
    return jsonify({"ok": True, "data": data, "error": None}), status


def _api_error(message: str, status: int = 400):
    """Return standardized error response."""
    return jsonify({"ok": False, "data": None, "error": {"message": message}}), status


@blog_api.route("/posts", methods=["GET"])
@safe_route("Failed to retrieve blog posts")
def get_posts() -> Response:
    """Get blog posts with optional filtering and pagination.

    Query Parameters:
        category: Filter by category ID
        search: Search term for title, summary, and tags
        featured: Filter featured posts only (true/false)
        limit: Maximum number of results (default: 10)
        offset: Offset for pagination (default: 0)

    Returns:
        JSON list of posts with metadata (no full content)
    """
    data = _load_blog_data()

    category_filter = request.args.get("category")
    search_term = request.args.get("search", "").lower().strip()
    featured_only = request.args.get("featured", "").lower() == "true"
    limit = min(int(request.args.get("limit", 10)), 50)
    offset = int(request.args.get("offset", 0))

    posts = data.get("posts", [])
    filtered_posts = []

    for post in posts:
        # Apply category filter
        if category_filter and post.get("category") != category_filter:
            continue

        # Apply featured filter
        if featured_only and not post.get("featured", False):
            continue

        # Apply search filter
        if search_term:
            searchable = (
                post.get("title", "").lower()
                + " "
                + post.get("summary", "").lower()
                + " "
                + " ".join(post.get("tags", []))
            )
            if search_term not in searchable:
                continue

        # Return post without full content for listing
        filtered_posts.append(
            {
                "id": post.get("id"),
                "slug": post.get("slug"),
                "title": post.get("title"),
                "summary": post.get("summary"),
                "category": post.get("category"),
                "emoji": post.get("emoji"),
                "author": post.get("author"),
                "published_at": post.get("published_at"),
                "reading_time": post.get("reading_time"),
                "featured": post.get("featured", False),
                "tags": post.get("tags", []),
            }
        )

    # Sort by published_at descending (newest first)
    filtered_posts.sort(key=lambda x: x.get("published_at", ""), reverse=True)

    # Apply pagination
    total = len(filtered_posts)
    paginated = filtered_posts[offset : offset + limit]

    return _api_success(
        {"posts": paginated, "total": total, "limit": limit, "offset": offset, "has_more": offset + limit < total}
    )


@blog_api.route("/post/<slug>", methods=["GET"])
@safe_route("Failed to retrieve blog post")
def get_post(slug: str) -> Response:
    """Get a single blog post by slug with full content.

    Args:
        slug: Post slug (URL-friendly identifier)

    Returns:
        JSON post with all fields including full content
    """
    data = _load_blog_data()

    for post in data.get("posts", []):
        if post.get("slug") == slug:
            return _api_success(post)

    return _api_error("Post not found", 404)


@blog_api.route("/categories", methods=["GET"])
@safe_route("Failed to retrieve blog categories")
def get_categories() -> Response:
    """Get all blog categories with post counts.

    Returns:
        JSON list of categories with id, name, description, icon, post_count
    """
    data = _load_blog_data()

    # Count posts per category
    category_counts: dict[str, int] = {}
    for post in data.get("posts", []):
        cat = post.get("category", "uncategorized")
        category_counts[cat] = category_counts.get(cat, 0) + 1

    categories = []
    for cat in data.get("categories", []):
        cat_id = cat.get("id")
        categories.append(
            {
                "id": cat_id,
                "name": cat.get("name"),
                "description": cat.get("description"),
                "icon": cat.get("icon"),
                "post_count": category_counts.get(cat_id, 0),
            }
        )

    return _api_success(categories)


@blog_api.route("/featured", methods=["GET"])
@safe_route("Failed to retrieve featured posts")
def get_featured() -> Response:
    """Get featured blog posts.

    Query Parameters:
        limit: Maximum number of results (default: 3)

    Returns:
        JSON list of featured posts
    """
    data = _load_blog_data()
    limit = min(int(request.args.get("limit", 3)), 10)

    featured = []
    for post in data.get("posts", []):
        if post.get("featured", False):
            featured.append(
                {
                    "id": post.get("id"),
                    "slug": post.get("slug"),
                    "title": post.get("title"),
                    "summary": post.get("summary"),
                    "category": post.get("category"),
                    "emoji": post.get("emoji"),
                    "author": post.get("author"),
                    "published_at": post.get("published_at"),
                    "reading_time": post.get("reading_time"),
                    "tags": post.get("tags", []),
                }
            )

    # Sort by published_at descending
    featured.sort(key=lambda x: x.get("published_at", ""), reverse=True)

    return _api_success(featured[:limit])


@blog_api.route("/tags", methods=["GET"])
@safe_route("Failed to retrieve blog tags")
def get_tags() -> Response:
    """Get all unique tags with post counts.

    Returns:
        JSON list of tags with name and count, sorted by count
    """
    data = _load_blog_data()

    tag_counts: dict[str, int] = {}
    for post in data.get("posts", []):
        for tag in post.get("tags", []):
            tag_counts[tag] = tag_counts.get(tag, 0) + 1

    tags = [{"name": name, "count": count} for name, count in tag_counts.items()]
    tags.sort(key=lambda x: x["count"], reverse=True)

    return _api_success(tags)


@blog_api.route("/search", methods=["GET"])
@safe_route("Failed to search blog posts")
def search_posts() -> Response:
    """Search blog posts.

    Query Parameters:
        q: Search query (required)
        limit: Maximum results (default: 10)

    Returns:
        JSON list of matching posts with relevance ranking
    """
    query = request.args.get("q", "").lower().strip()
    limit = min(int(request.args.get("limit", 10)), 50)

    if not query:
        return _api_error("Search query is required")

    data = _load_blog_data()
    results = []

    for post in data.get("posts", []):
        score = 0
        title = post.get("title", "").lower()
        summary = post.get("summary", "").lower()
        tags = [t.lower() for t in post.get("tags", [])]
        content = post.get("content", "").lower()

        # Score based on match location
        if query in title:
            score += 10
        if query in summary:
            score += 5
        if any(query in t for t in tags):
            score += 8
        if query in content:
            score += 1

        # Exact tag match bonus
        if query in tags:
            score += 15

        if score > 0:
            results.append(
                {
                    "id": post.get("id"),
                    "slug": post.get("slug"),
                    "title": post.get("title"),
                    "summary": post.get("summary"),
                    "category": post.get("category"),
                    "emoji": post.get("emoji"),
                    "published_at": post.get("published_at"),
                    "reading_time": post.get("reading_time"),
                    "score": score,
                }
            )

    # Sort by score descending
    results.sort(key=lambda x: x["score"], reverse=True)

    return _api_success({"results": results[:limit], "total": len(results), "query": query})
