"""Edition schema. Used to validate every edition file and as the model's output contract."""

LAYERS = [
    ("Compute & Infrastructure", "chips, datacenters, inference systems, and the machinery beneath AI."),
    ("Data", "training material, synthetic data, labeling, retrieval, and tokenization."),
    ("Models & Research", "new architectures, training methods, evaluations, and scientific findings."),
    ("Platforms & Tools", "products and technical systems people use to build or work with AI."),
    ("Applications & Policy", "AI in the world: use cases, safety, business, law, and governance."),
]
LAYER_NAMES = [n for n, _ in LAYERS]

_link = {
    "type": "object",
    "required": ["label", "url"],
    "additionalProperties": False,
    "properties": {
        "label": {"type": "string", "minLength": 1},
        "url": {"type": "string", "pattern": "^https?://"},
    },
}
_links = {"type": "array", "items": _link}
_layer = {"type": ["string", "null"], "enum": LAYER_NAMES + [None]}
# Inline text fields may carry <a>, <em>, <strong>, <sup>, <sub>, <code>; everything else is stripped at render.
_text = {"type": "string"}

EDITION_SCHEMA = {
    "type": "object",
    "required": ["date", "dek", "brief", "top_stories", "blogs", "videos", "papers", "threads"],
    "additionalProperties": False,
    "properties": {
        "date": {"type": "string", "pattern": r"^\d{4}-\d{2}-\d{2}$"},
        "dek": {"type": "string", "minLength": 20},
        "brief": {"type": "array", "minItems": 1, "maxItems": 4, "items": _text},
        "top_stories": {
            "type": "array",
            "minItems": 3,
            "maxItems": 5,
            "items": {
                "type": "object",
                "required": ["lead", "threads", "layer", "title", "summary", "why", "links"],
                "additionalProperties": False,
                "properties": {
                    "lead": {"type": "boolean"},
                    "threads": {"type": "array", "items": {"type": "string"}},
                    "layer": _layer,
                    "title": {"type": "string", "minLength": 1},
                    "summary": _text,
                    "why": _text,
                    "links": {**_links, "minItems": 1},
                },
            },
        },
        "blogs": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["body", "links"],
                "additionalProperties": False,
                "properties": {"body": _text, "links": _links},
            },
        },
        "videos": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["channel", "title", "when", "url", "summary", "links"],
                "additionalProperties": False,
                "properties": {
                    "channel": {"type": "string"},
                    "title": {"type": "string"},
                    "when": {"type": "string"},
                    "url": {"type": ["string", "null"]},
                    "summary": _text,
                    "links": _links,
                },
            },
        },
        "papers": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["title", "layer", "body", "links"],
                "additionalProperties": False,
                "properties": {"title": {"type": "string"}, "layer": _layer, "body": _text, "links": _links},
            },
        },
        "threads": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["name", "update"],
                "additionalProperties": False,
                "properties": {"name": {"type": "string"}, "update": _text},
            },
        },
    },
}


def _relaxed(schema):
    """Archived editions predate the link requirement on every story; render them as-is."""
    import copy

    s = copy.deepcopy(schema)
    s["properties"]["top_stories"]["items"]["properties"]["links"].pop("minItems", None)
    return s


ARCHIVE_SCHEMA = _relaxed(EDITION_SCHEMA)
