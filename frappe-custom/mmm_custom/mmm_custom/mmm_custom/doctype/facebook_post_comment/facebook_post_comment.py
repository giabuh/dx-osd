# Copyright (c) 2026, MMM and contributors
# For license information, please see license.txt

try:
    from frappe.model.document import Document
except ImportError:
    class Document:
        pass


class FacebookPostComment(Document):
    pass
