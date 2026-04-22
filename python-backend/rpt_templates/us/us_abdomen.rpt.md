---
study_name: "US Abdomen"
aliases:
  - "us abdomen"
  - "us abdo"
  - "ultrasound abdomen"
  - "ultrasound abdo"
technique: "Ultrasound of the abdomen was performed."
interpolate_normal: true
impression: true
important_first: false
variant: "freeform"
composable_from:
  - "us/us_hbs.rpt.md"
  - "us/us_kidneys.rpt.md"
exclude_fields: 
  us/us_hbs.rpt.md:
    - "others"
  us/us_kidneys.rpt.md:
    - "others"
fields: 
  - name: "others"
    optional: true
    normal: ""
groups: []
---

{{liver}}

{{gallbladder_cbd}}

{{spleen}}
{{pancreas}}

{{kidneys}}

{{others}}

## Guidance

## COMMENT
