# Currency evidence review

Source: Zidio_Project_Data_1.1 (1).pdf, Project FORESIGHT engagement brief v1.0, 21 pages. SHA-256: `41800d9ad6d878ede0ac5071d74b6f182f93062710346520b1d869811f660c9e`.

- Page 5, section 3.1: “Quantify the business impact in rupees”.
- Page 11, section 8.1: “the rupee value at stake is attached”.
- Pages 12–13, D4/D7: rupee value and rupee impact are acceptance requirements.
- Pages 19–20, Appendix A: revenue, unit price, unit cost and list price are described, but no currency code, denomination, exchange rate, or field-level unit statement is provided.
- None of the four supplied CSVs contains a currency field. Their numeric values cannot establish denomination.

Conclusion: the brief establishes rupee reporting intent, but does not explicitly confirm that the supplied numeric price/cost values are INR. INR may be intended; it remains an inference rather than source-backed confirmation. Per the user's no-fabricated-currency constraint, outputs retain source currency units with `currency: null`. There is no conversion and no ₹ label. Source-owner confirmation is the only unresolved currency requirement; the user has said they do not know.

The financial calculations can still be reconciled in source units and the operational quantities do not depend on currency. If denomination is later confirmed, rerun with `--currency INR` and regenerate notebooks with the same explicit setting. Do not treat a request for rupee reporting as proof of an unstated exchange rate or denomination.
