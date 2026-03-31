---
study_name: "CT Thorax, Abdomen and Pelvis"
aliases:
  - "ct tap"
  - "ct thorax abdomen pelvis"
  - "ct thorax abdomen and pelvis"
  - "ct chest abdomen pelvis"
technique: "CT of the chest, abdomen and pelvis was performed with intravenous contrast."
interpolate_normal: false
impression: true
important_first: false
variant: "freeform"
composable_from:
  - "ct/ct_thorax.rpt.md"
  - "ct/ct_ap.rpt.md"
exclude_fields:
  ct/ct_thorax.rpt.md:
    - "bones"
    - "limited_abdomen"
  ct/ct_ap.rpt.md:
    - "bones"
    - "lung_bases"
fields:
  - name: "bones"
    normal: "No suspicious osseous lesion. No acute fracture."
groups: []
---

## CLINICAL HISTORY

{{technique:clinical_indication}}

## TECHNIQUE

{{technique:phase}}

## COMPARISON

None available.

## FINDINGS

### Thorax

{{lungs}}

{{pleura}}

{{airways}}

{{thyroid}}

{{mediastinum}}

{{heart_great_vessels}}

### Abdomen and Pelvis

{{liver}}

{{gallbladder}} {{cbd}}

{{spleen}}
{{adrenals}}
{{pancreas}}

{{kidneys}}


{{bowel}}
{{mesentery}}

{{lymph_nodes}}


{{bladder}}
{{uterus_ovaries}}
{{prostate}}


{{vessels}}
{{free_fluid}}
{{soft_tissues}}

### Other

{{bones}}

## Guidance

Lymph node short axis threshold: 10 mm for pathological mediastinal or hilar lymphadenopathy.

Fleischner Society guidelines for incidental pulmonary nodule management.

Normal thoracic aortic calibre: up to 4.0 cm at mid-ascending aorta.

Normal aortic calibre: infrarenal aorta up to 2.0 cm (men), 1.8 cm (women). Aneurysm threshold: 3.0 cm.

Normal CBD calibre: up to 6 mm (up to 10 mm post-cholecystectomy).

Bosniak classification for renal cysts. LI-RADS for liver lesions on contrast-enhanced CT.

## COMMENT
