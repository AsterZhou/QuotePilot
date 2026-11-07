# Genesis business analytics

Natural-language questions call the configured Genesis model to produce a typed
query plan. The server validates the dataset, dimensions, metrics, filters,
dates, sorting and result limit, then generates parameter-bound SELECT SQL.
It never executes model-authored SQL. Counts and chart/table data come from the
same database result, with the model response ID shown alongside the interpretation.

Supported datasets: historical RFQs, imported email requirements, supplier price
resources, and internal inventory/cost records. Questions can combine dates,
customers, parts, urgency, categories, grouping, counts and selected aggregates.
Quantity sums are separated by unit, and original-currency price averages by
currency. These sample prices are not live offers or approved quotes.

Flight/ticket search and other external or real-time information are outside the
data scope. Unsupported questions, invalid plans and provider errors clear the
previous chart/table and display a persistent explanation. Quick statistics
remain available without a model call. Relative dates use the visible reference
date; the default is the historical sample date 2026-09-01.

The provider must be explicitly configured as Genesis. API credentials remain in
backend environment variables. Existing administrator login remains required.
