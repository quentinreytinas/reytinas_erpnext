frappe.ui.form.on("EnableBanking Settings", {
	refresh(frm) {
		if (!frm.doc.enabled) {
			return;
		}

		frm.add_custom_button(__("Connecter un compte bancaire"), async () => {
			try {
				await openAuthorizationDialog(frm);
			} catch (error) {
				console.error("EnableBanking dialog error", error);
				frappe.msgprint({
					title: __("Erreur EnableBanking"),
					indicator: "red",
					message: error.message || __("Impossible d'ouvrir l'assistant de connexion bancaire."),
				});
			}
		});
	},
});

async function openAuthorizationDialog(frm) {
	const dialog = new frappe.ui.Dialog({
		title: __("Connecter un compte bancaire"),
		fields: [
			{
				fieldname: "bank_account",
				fieldtype: "Link",
				label: __("Compte bancaire ERPNext"),
				options: "Bank Account",
				reqd: 1,
				get_query: () => ({
					filters: {
						is_company_account: 1,
					},
				}),
			},
			{
				fieldname: "country",
				fieldtype: "Data",
				label: __("Pays"),
				default: "FR",
				reqd: 1,
			},
			{
				fieldname: "psu_type",
				fieldtype: "Select",
				label: __("Type de PSU"),
				options: ["business", "personal"],
				default: "business",
				reqd: 1,
			},
			{
				fieldname: "aspsp_name",
				fieldtype: "Select",
				label: __("Banque"),
				options: "",
				reqd: 1,
				description: __("Charge les banques disponibles pour le pays et le type sélectionnés."),
			},
		],
		secondary_action_label: __("Charger les banques"),
		secondary_action: async () => {
			await loadBanks(dialog);
		},
		primary_action_label: __("Lancer l'autorisation"),
		primary_action: async (values) => {
			if (!values.aspsp_name) {
				frappe.msgprint(__("Choisis une banque avant de continuer."));
				return;
			}

			const bank = dialog.enablebankingBanks.find((item) => item.name === values.aspsp_name);
			if (!bank) {
				frappe.msgprint(__("Banque introuvable dans la liste chargée."));
				return;
			}

			const response = await frappe.call({
				method: "reytinas_erpnext.enablebanking.api.start_authorization",
				args: {
					bank_account: values.bank_account,
					aspsp_name: bank.name,
					aspsp_country: bank.country || values.country,
					aspsp_id: bank.uid || bank.id || bank.aspsp_id || null,
					psu_type: values.psu_type,
				},
				freeze: true,
				freeze_message: __("Creation du lien EnableBanking..."),
			});

			const result = response.message || {};
			if (!result.authorization_url) {
				frappe.throw(__("EnableBanking n'a pas renvoyé d'URL d'autorisation."));
			}

			dialog.hide();
			window.open(result.authorization_url, "_blank", "noopener");
			frappe.show_alert({
				message: __("Autorisation ouverte dans un nouvel onglet."),
				indicator: "green",
			});
		},
	});

	dialog.enablebankingBanks = [];

	dialog.show();
	await loadBanks(dialog);
}

async function loadBanks(dialog) {
	const country = dialog.get_value("country") || "FR";
	const psuType = dialog.get_value("psu_type") || "business";

	const response = await frappe.call({
		method: "reytinas_erpnext.enablebanking.api.get_aspsps",
		args: {
			country,
			psu_type: psuType,
		},
		freeze: true,
		freeze_message: __("Chargement des banques EnableBanking..."),
	});

	const banks = (response.message || []).slice().sort((left, right) => {
		return (left.name || "").localeCompare(right.name || "");
	});
	const bankNames = banks.map((item) => item.name).filter(Boolean);

	dialog.enablebankingBanks = banks;
	dialog.set_df_property("aspsp_name", "options", bankNames.join("\n"));
	dialog.refresh();

	if (bankNames.length === 1) {
		dialog.set_value("aspsp_name", bankNames[0]);
	}

	frappe.show_alert({
		message: __("{0} banques chargees", [bankNames.length]),
		indicator: "blue",
	});
}
