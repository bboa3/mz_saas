import frappe


def after_install():
	"""Run setup tasks after app installation"""
	_sync_custom_fields()
	frappe.db.commit()


def after_migrate():
	"""Run setup tasks after migration"""
	_sync_custom_fields()
	frappe.db.commit()


def _sync_custom_fields():
	"""Programmatically ensure MZ SaaS custom fields on Contract and Sales Invoice exist."""
	if not frappe.db.exists("DocType", "Contract"):
		return
	if not frappe.db.exists("DocType", "Sales Invoice"):
		return

	try:
		from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

		create_custom_fields(
			{
				"Contract": [
					{
						"fieldname": "mz_saas_tab",
						"label": "MozEconomia Cloud",
						"fieldtype": "Tab Break",
						"insert_after": "fulfilment_terms",
						"module": "MZ SaaS",
					},
					{
						"fieldname": "mz_service_lines",
						"label": "Linhas de Serviço",
						"fieldtype": "Table",
						"options": "MZ Contract Service Line",
						"insert_after": "mz_saas_tab",
						"module": "MZ SaaS",
					},
					{
						"fieldname": "mz_service_status",
						"label": "Estado do Serviço",
						"fieldtype": "Select",
						"options": "Draft\nActive\nSuspended\nDeactivated",
						"default": "Draft",
						"insert_after": "mz_service_lines",
						"module": "MZ SaaS",
					},
					{
						"fieldname": "mz_customer_email",
						"label": "Email do Cliente",
						"fieldtype": "Data",
						"options": "Email",
						"insert_after": "mz_service_status",
						"module": "MZ SaaS",
					},
					{
						"fieldname": "mz_sales_responsible",
						"label": "Responsável Comercial",
						"fieldtype": "Link",
						"options": "User",
						"insert_after": "mz_customer_email",
						"module": "MZ SaaS",
					},
					{
						"fieldname": "mz_technical_responsible",
						"label": "Responsável Técnico",
						"fieldtype": "Link",
						"options": "User",
						"insert_after": "mz_sales_responsible",
						"module": "MZ SaaS",
					},
					{
						"fieldname": "mz_linked_subscription",
						"label": "Subscrição ERPNext",
						"fieldtype": "Link",
						"options": "Subscription",
						"read_only": 1,
						"insert_after": "mz_technical_responsible",
						"module": "MZ SaaS",
					},
					{
						"fieldname": "mz_internal_notes",
						"label": "Notas Internas",
						"fieldtype": "Text",
						"insert_after": "mz_linked_subscription",
						"module": "MZ SaaS",
					},
				],
				"Sales Invoice": [
					{
						"fieldname": "mz_saas_managed",
						"label": "Gerido por MZ SaaS",
						"fieldtype": "Check",
						"read_only": 1,
						"default": "0",
						"insert_after": "subscription",
						"module": "MZ SaaS",
					},
					{
						"fieldname": "mz_contract",
						"label": "Contrato MZ SaaS",
						"fieldtype": "Link",
						"options": "Contract",
						"read_only": 1,
						"insert_after": "mz_saas_managed",
						"module": "MZ SaaS",
					},
					{
						"fieldname": "mz_sales_responsible_email",
						"label": "Email Responsável Comercial",
						"fieldtype": "Data",
						"options": "Email",
						"read_only": 1,
						"insert_after": "mz_contract",
						"module": "MZ SaaS",
					},
				],
			},
			ignore_validate=True,
			update=True,
		)
	except Exception:
		frappe.log_error(
			title="MZ SaaS: Sync Custom Fields Failed",
			message=frappe.get_traceback(),
		)
