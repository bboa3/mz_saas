import frappe


def flag_overdue_customers():
	"""Daily: create MZ Overdue Review records for overdue MZ SaaS invoices."""
	overdue_invoices = frappe.db.sql(
		"""
		SELECT name, customer, mz_contract, outstanding_amount, due_date
		FROM `tabSales Invoice`
		WHERE mz_saas_managed = 1
			AND outstanding_amount > 0
			AND due_date < CURDATE()
			AND docstatus = 1
		""",
		as_dict=True,
	)

	for inv in overdue_invoices:
		if not inv.mz_contract:
			continue
		if frappe.db.exists(
			"MZ Overdue Review",
			{"contract": inv.mz_contract, "review_status": "Pending Review"},
		):
			continue

		assigned_to = frappe.db.get_value("Contract", inv.mz_contract, "mz_sales_responsible")

		frappe.get_doc({
			"doctype": "MZ Overdue Review",
			"customer": inv.customer,
			"contract": inv.mz_contract,
			"outstanding_amount": inv.outstanding_amount,
			"overdue_since": inv.due_date,
			"review_status": "Pending Review",
			"assigned_to": assigned_to,
		}).insert(ignore_permissions=True)

	frappe.db.commit()
