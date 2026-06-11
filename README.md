[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![PyPI](https://img.shields.io/pypi/v/inventree-component-shortfall)](https://pypi.org/project/inventree-component-shortfall/)
![PEP](https://github.com/SchrodingersGat/inventree-shortfall-report/actions/workflows/ci.yaml/badge.svg)

# Component Shortfall

An [InvenTree](https://inventree.org) plugin for generating component shortfall reports.

## Description

The *Component Shortfall* plugin calculates which components are insufficient to fulfil outstanding demand. It aggregates requirements from open sales orders and active build orders, then traverses each assembly's BOM recursively to determine sub-component requirements.

For each component it computes:

**Shortfall = Required − Stock on Hand − On Order − In Production**

Results are exported as an `.xlsx` file and can also be emailed automatically on a configurable schedule.

## Installation

### Via User Interface

Install from the InvenTree plugin interface using the package name `inventree-component-shortfall`.

### Via Pip

```bash
pip install -U inventree-component-shortfall
```

*Note: After installation the plugin must be activated via the InvenTree plugin interface.*

## Configuration

| Setting | Description |
| --- | --- |
| Hide No Shortfall | Omit components with zero shortfall from the report (default: enabled) |
| Shortfall Report Days | How often (in days) the scheduled report runs; set to `0` to disable (default: 7) |
| Shortfall Report Group | User group that receives periodic email reports |
| Shortfall Horizon (Months) | Only consider orders due within this many months; orders with no due date are always included; set to `0` for no limit (default: 12) |
| Shortfall Parameter Template | A parameter template used to record the shortfall quantity directly against each part; leave blank to disable (default: disabled) |

## Usage

### Dashboard Widget

A *Shortfall Report* dashboard item is available in the InvenTree UI. Click **Generate** to run the report on demand. The report can optionally be filtered by part category.

The generated `.xlsx` file contains the following columns for each component:

| Column | Description |
| --- | --- |
| Part ID / Name / IPN | Part identification |
| Category | Part category path |
| Current Stock | Stock on hand |
| On Order | Quantity on open purchase orders |
| In Production | Quantity allocated to active build orders |
| Required Quantity | Total quantity needed across all outstanding orders |
| Shortfall | Deficit after accounting for stock, on-order, and in-production quantities |

### Shortfall Parameter Recording

When a *Shortfall Parameter Template* is configured, the plugin writes the shortfall quantity as a part parameter on each affected component after every report run:

- **Parts with shortfall > 0** — the parameter value is created or updated with the shortfall quantity.
- **Parts with shortfall = 0** — any existing parameter value for that template is deleted, keeping the data set clean.

This makes shortfall data queryable and filterable directly from the InvenTree part list, and allows the values to be used in other automations or reports. The parameter template must already exist in InvenTree before selecting it in this setting.

### Scheduled Email Reports

When a *Shortfall Report Group* is configured, the plugin sends an HTML email with the report attached to all active users in that group. The frequency is controlled by the *Shortfall Report Days* setting.
