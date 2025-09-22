
import frappe
from frappe.model.document import Document

class EHSRiskRegister(Document):
    def validate(self):
        def to_int(x):
            try: return int(x or 0)
            except Exception: return 0
        self.risk_rating_pre = to_int(self.consequence) * to_int(self.likelihood)
        self.risk_rating_post = to_int(self.residual_consequence) * to_int(self.residual_likelihood)
