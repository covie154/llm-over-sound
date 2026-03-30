---
study_name: "Minimal Groups"
aliases:
  - "minimal groups"
technique: "Test technique."
interpolate_normal: false
impression: true
important_first: false
variant: "freeform"
fields:
  - name: "liver"
    normal: "The liver is normal."
  - name: "spleen"
    normal: "The spleen is normal."
  - name: "pancreas"
    normal: "The pancreas is normal."
  - name: "kidneys"
    normal: "The kidneys are normal."
groups:
  - name: "spleen_pancreas"
    members:
      - "spleen"
      - "pancreas"
    joint_normal: "The spleen and pancreas are unremarkable."
    partials: []
---

## CLINICAL HISTORY

{{technique:clinical_indication}}

## TECHNIQUE

{{technique:phase}}

## COMPARISON

None available.

## FINDINGS

{{liver}}

{{spleen}}

{{pancreas}}

{{kidneys}}

## Guidance

Test guidance content to be stripped.

## COMMENT
