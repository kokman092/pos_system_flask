"""
Pagination utilities for AURA Restaurant POS.
Handles standard dictionary responses for SQLAlchemy pagination.
"""

def paginate_query(query, page: int, per_page: int = 20) -> dict:
    """
    Paginates a SQLAlchemy query and returns a dictionary payload.
    """
    paginated = query.paginate(page=page, per_page=per_page, error_out=False)
    return {
        "items": paginated.items,
        "total": paginated.total,
        "pages": paginated.pages,
        "current_page": paginated.page,
        "has_next": paginated.has_next,
        "has_prev": paginated.has_prev
    }

def get_page_from_request(request, default: int = 1) -> int:
    """
    Safely reads ?page= from Flask request args.
    Returns the default value if missing or invalid.
    """
    try:
        page = request.args.get('page', default, type=int)
        if page < 1:
            return default
        return page
    except Exception:
        return default
