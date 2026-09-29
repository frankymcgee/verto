from frappe.model.document import Document


class UserWhiteboardState(Document):
    def validate(self):
        previous = self.get_doc_before_save()
        self.revision = (previous.revision or 0) + 1 if previous else 1
