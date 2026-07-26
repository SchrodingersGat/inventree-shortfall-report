# Component Shortfall Plugin — Agent Summary

## Purpose

This InvenTree plugin identifies which components have insufficient stock to fulfil outstanding demand. It is intended to support procurement and production planning by surfacing deficits before orders are at risk.

## Core calculation

**Shortfall = Required − Stock on Hand − On Order − In Production**

Requirements are gathered from open Sales Orders and active Build Orders. For each top-level assembly, the plugin walks the BOM recursively (up to 50 levels deep) to propagate shortfall down to raw sub-components. Only consumable=False BOM items are included; shortfall stops propagating into a sub-assembly branch when no additional deficit remains.

## Outputs

- **XLSX report** — one row per component, with columns for stock, on-order, in-production, required, and shortfall quantities. Optionally includes supplier names. Exported via InvenTree's `DataOutput` mechanism.
- **HTML email** — sent to all active members of a configured user group on a configurable schedule (default: weekly).
- **Part parameters** — when a `ParameterTemplate` is selected, shortfall quantities are written directly onto affected parts so they can be filtered and queried from the InvenTree part list.

## Entry points

| What | Where |
|---|---|
| Plugin class, settings, scheduled task | `component_shortfall/core.py` |
| Shortfall calculation and XLSX export | `component_shortfall/shortfall.py` |
| REST API view (on-demand generation) | `component_shortfall/views.py` |
| API serializer | `component_shortfall/serializers.py` |
| Dashboard widget (React) | `frontend/` |

## Key settings

| Setting | Default | Effect |
|---|---|---|
| `HIDE_NO_SHORTFALL` | True | Omit zero-shortfall rows from the report |
| `EXCLUDE_PENDING_BUILD_ORDERS` | False | Skip build orders with *pending* status |
| `EXCLUDE_PENDING_SALES_ORDERS` | False | Skip sales orders with *pending* status |
| `SHORTFALL_HORIZON_MONTHS` | 12 | Ignore orders due further than N months away (0 = no limit) |
| `SHORTFALL_REPORT_DAYS` | 7 | Email schedule cadence (0 = disabled) |
| `SHORTFALL_REPORT_GROUP` | — | User group that receives email reports |
| `SHORTFALL_PARAMETER_TEMPLATE` | — | Part parameter to write shortfall values into |
| `INCLUDE_SUPPLIER_DATA` | False | Add a supplier column to the XLSX output |
