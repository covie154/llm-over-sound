---
study_name: "Test CT Abdomen"
aliases:
  - "test ct abdomen"
  - "test ct ap"
technique: "CT of the abdomen was performed with intravenous contrast in the portal venous phase."
interpolate_normal: false
impression: true
important_first: false
variant: "freeform"
fields:
  - name: "liver"
    normal: "The liver is normal in size and attenuation. No focal lesion."
  - name: "spleen"
    normal: "The spleen is normal in size."
  - name: "pancreas"
    normal: "The pancreas is normal in morphology and enhancement."
  - name: "uterus"
    sex: "female"
    normal: "The uterus is normal in size and morphology."
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

Liver span: {{measurement:liver_span_cm}} cm.

{{uterus}}

## Guidance

When reporting liver lesions, comment on enhancement pattern relative to background liver parenchyma in each phase. Use Bosniak classification for renal cysts if applicable.

## COMMENT
