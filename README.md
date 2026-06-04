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

### Scheduled Email Reports

When a *Shortfall Report Group* is configured, the plugin sends an HTML email with the report attached to all active users in that group. The frequency is controlled by the *Shortfall Report Days* setting.
