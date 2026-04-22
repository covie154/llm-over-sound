---
study_name: "Group Measurements"
aliases: ["group measurements"]
technique: "Boilerplate."
fields:
  - name: "spleen"
    normal: "The spleen is normal."
  - name: "pancreas"
    normal: "The pancreas is normal."
  - name: "adrenals"
    normal: "The adrenals are normal."
groups:
  - name: "sap"
    members: ["spleen", "pancreas", "adrenals"]
    joint_normal: "The spleen measures {{measurement:spleen_length_cm}} cm. The pancreas and adrenals are unremarkable."
    partials:
      - members: ["pancreas", "adrenals"]
        text: "The pancreas is unremarkable. The adrenals measure {{measurement:adrenal_size_cm}} cm."
---
## FINDINGS

{{spleen}}

{{pancreas}}

{{adrenals}}

## COMMENT
