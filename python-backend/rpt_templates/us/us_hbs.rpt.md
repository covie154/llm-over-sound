---
study_name: "US Hepatobiliary"
aliases:
  - "us hbs"
  - "us hepatobiliary"
  - "ultrasound hbs"
  - "ultrasound hepatobiliary"
technique: "Ultrasound of the hepatobiliary system was performed."
interpolate_normal: false
impression: true
important_first: false
fields:
  - name: "liver"
    normal: "The liver is normal in echotexture, measuring {{measurement:liver_span_cm}} cm in craniocaudal span. No focal lesion."
  - name: "gallbladder_cbd"
    normal: "The gallbladder is normal with no gallstones or wall thickening. The common bile duct measures {{measurement:cbd_diameter_mm}} mm, within normal limits."
  - name: "spleen"
    normal: "The spleen is normal in echotexture, measuring {{measurement:spleen_length_cm}} cm."
  - name: "pancreas"
    normal: "The pancreas is normal in echotexture where visualised."
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

{{gallbladder_cbd}}

CBD diameter: {{measurement:cbd_diameter_mm}} mm.

{{spleen}}

Spleen length: {{measurement:spleen_length_cm}} cm.

{{pancreas}}

{{others}}

## Guidance

Normal liver span: up to 15.5 cm (craniocaudal).

Normal CBD calibre: up to 6 mm (up to 10 mm post-cholecystectomy).

Normal spleen length: up to 12 cm.

## COMMENT
