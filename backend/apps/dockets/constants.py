"""Column definitions for the four docket types.

Ambient and chilled dockets are category registers: each line splits a supplier
docket across department columns. Returns and transfers are item lists instead.
Keeping the definitions here means the API, the PDF renderer and the frontend
all agree on one source of truth (the frontend reads them from
`/api/dockets/meta/`).
"""

AMBIENT = "ambient"
CHILLED = "chilled"
RETURNS = "returns"
TRANSFER = "transfer"

CATEGORY_TYPES = (AMBIENT, CHILLED)
ITEM_TYPES = (RETURNS, TRANSFER)

AMBIENT_CATEGORIES = (
    ("groc", "Groceries"),
    ("cigs", "Cigarettes"),
    ("wine", "Wine"),
    ("beers", "Beers"),
    ("spirits", "Spirits"),
    ("nonfood", "Non Food"),
    ("news", "News"),
    ("promo", "Promo"),
    ("expense", "Expense"),
)

CHILLED_CATEGORIES = (
    ("beef", "Beef"),
    ("lamb", "Lamb"),
    ("pork", "Pork"),
    ("poultry", "Poultry"),
    ("produce", "Produce"),
    ("frozen", "Frozen"),
    ("provisions", "Provisions"),
    ("deli", "Deli"),
    ("bakery", "Bakery"),
)

CATEGORIES_BY_TYPE = {
    AMBIENT: AMBIENT_CATEGORIES,
    CHILLED: CHILLED_CATEGORIES,
}


def category_keys(docket_type):
    return [key for key, _label in CATEGORIES_BY_TYPE.get(docket_type, ())]


# Which signature slots each docket type expects, in display order.
SIGNATURE_ROLES_BY_TYPE = {
    AMBIENT: ("manager",),
    CHILLED: ("manager",),
    RETURNS: ("staff", "branch_manager"),
    TRANSFER: ("outgoing_staff", "outgoing_manager", "incoming_manager"),
}
