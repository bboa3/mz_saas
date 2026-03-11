import frappe
from frappe.model.document import Document


class MZSaaSPlan(Document):
	def validate(self):
		self._ensure_subscription_plan()

	def _ensure_subscription_plan(self):
		"""Auto-create an ERPNext Subscription Plan linked to this MZ SaaS Plan."""
		if self.linked_subscription_plan and frappe.db.exists("Subscription Plan", self.linked_subscription_plan):
			# Keep in sync: update price on the linked plan
			frappe.db.set_value(
				"Subscription Plan",
				self.linked_subscription_plan,
				{
					"cost": self.price,
					"currency": self.currency,
					"billing_interval": _billing_interval(self.billing_cycle),
					"billing_interval_count": _billing_interval_count(self.billing_cycle),
				},
			)
			return

		if not frappe.db.exists("DocType", "Subscription Plan"):
			frappe.log_error(
				title="MZ SaaS: Subscription Plan DocType Not Found",
				message="ERPNext Accounts module may not be installed.",
			)
			return

		plan = frappe.get_doc({
			"doctype": "Subscription Plan",
			"plan_name": self.plan_name,
			"item": _get_or_create_service_item(self.plan_name, self.currency),
			"price_determination": "Fixed Rate",
			"cost": self.price,
			"currency": self.currency,
			"billing_interval": _billing_interval(self.billing_cycle),
			"billing_interval_count": _billing_interval_count(self.billing_cycle),
		})
		plan.insert(ignore_permissions=True)
		self.linked_subscription_plan = plan.name


def _billing_interval(cycle: str) -> str:
	return {"Monthly": "Month", "Quarterly": "Month", "Annual": "Year"}.get(cycle, "Month")


def _billing_interval_count(cycle: str) -> int:
	return {"Monthly": 1, "Quarterly": 3, "Annual": 1}.get(cycle, 1)


def _get_or_create_service_item(plan_name: str, currency: str) -> str:
	"""Return an Item code suitable for use in Subscription Plan billing."""
	item_code = f"SVC-{frappe.scrub(plan_name).upper()}"
	if frappe.db.exists("Item", item_code):
		return item_code

	# Find or create a 'Services' item group
	item_group = "Services" if frappe.db.exists("Item Group", "Services") else "All Item Groups"

	item = frappe.get_doc({
		"doctype": "Item",
		"item_code": item_code,
		"item_name": plan_name,
		"item_group": item_group,
		"stock_uom": "Nos",
		"is_stock_item": 0,
		"is_sales_item": 1,
		"description": f"Serviço SaaS: {plan_name}",
	})
	item.insert(ignore_permissions=True)
	return item_code
