---
study_name: "Minimal Measurements"
aliases:
  - "minimal measurements"
technique: "Test technique."
interpolate_normal: false
impression: true
important_first: false
variant: "freeform"
fields:
  - name: "liver"
    normal: "The liver measures {{measurement:liver_span_cm}} cm. Normal."
  - name: "spleen"
    normal: "The spleen measures {{measurement:spleen_length_cm}} cm."
  - name: "others"
    optional: true
    normal: ""
groups: []
---

## CLINICAL HISTORY

{{technique:clinical_indication}}

## TECHNIQUE

{{technique:phase}}

## COMPARISON

None available.

## FINDINGS

{{liver}}

Liver span: {{measurement:liver_span_cm}} cm.

{{spleen}}

Spleen: {{measurement:spleen_length_cm}} cm.

{{others}}

## Guidance

Test guidance content to be stripped.

## COMMENT
