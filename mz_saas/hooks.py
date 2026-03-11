app_name = "mz_saas"
app_title = "MozEconomia SaaS"
app_publisher = "MozEconomia, SA"
app_description = "Gestão de contratos e clientes SaaS para MozEconomia Cloud"
app_email = "contacto@mozeconomia.co.mz"
app_license = "mit"
app_version = "1.0.0"

required_apps = ["erpnext", "erpnext_mz"]

after_install = "mz_saas.install.after_install"
after_migrate = "mz_saas.install.after_migrate"

doc_events = {
	"Contract": {
		"on_submit": "mz_saas.saas.contract_lifecycle.on_contract_submit",
		"on_update_after_submit": "mz_saas.saas.contract_lifecycle.on_contract_status_change",
	},
	"Sales Invoice": {
		"on_submit": "mz_saas.saas.contract_lifecycle.on_invoice_submit",
	},
}

scheduler_events = {
	"daily": [
		"mz_saas.saas.billing_monitor.flag_overdue_customers",
	]
}

fixtures = [
	{"dt": "Custom Field", "filters": [["dt", "in", ["Contract", "Sales Invoice"]]]},
	{"dt": "Notification", "filters": [["name", "like", "MZ SaaS%"]]},
]
