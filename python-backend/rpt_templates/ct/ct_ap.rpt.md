---
study_name: "CT Abdomen and Pelvis"
aliases:
  - "ct ap"
  - "ct abdomen"
  - "ct abdomen pelvis"
  - "ct abdomen and pelvis"
technique: "CT of the abdomen and pelvis was performed with intravenous contrast in the portal venous phase."
interpolate_normal: false
impression: true
important_first: false
fields:
  - name: "liver"
    normal: "The liver is normal in size and attenuation. No focal lesion."
  - name: "gallbladder"
    normal: "The gallbladder is normal. No gallstones."
  - name: "cbd"
    normal: "The common bile duct is normal in calibre."
  - name: "spleen"
    normal: "The spleen is normal in size."
  - name: "adrenals"
    normal: "The adrenal glands are normal."
  - name: "pancreas"
    normal: "The pancreas is normal in morphology and enhancement."
  - name: "kidneys"
    normal: "The kidneys are normal in size and enhancement. No hydronephrosis or renal calculus."
  - name: "bowel"
    normal: "The visualised bowel is unremarkable. No dilatation or wall thickening."
  - name: "mesentery"
    normal: "The mesentery is clear."
  - name: "lymph_nodes"
    normal: "No pathologically enlarged lymph nodes."
  - name: "bladder"
    normal: "The urinary bladder is normal."
  - name: "uterus_ovaries"
    sex: "female"
    normal: "The uterus and ovaries are normal in size and morphology."
  - name: "prostate"
    sex: "male"
    normal: "The prostate is normal in size."
  - name: "vessels"
    optional: true
    normal: "The abdominal aorta is normal in calibre. The IVC and portal vein are patent."
  - name: "lung_bases"
    normal: "The visualised lung bases are clear."
  - name: "free_fluid"
    normal: "No free fluid."
  - name: "bones"
    normal: "No suspicious osseous lesion."
  - name: "soft_tissues"
    normal: "The abdominal wall and soft tissues are unremarkable."
groups:
  - name: "gallbladder_cbd"
    members:
      - "gallbladder"
      - "cbd"
    joint_normal: "The gallbladder and common bile duct are normal. No gallstones."
    partials: []
  - name: "spleen_adrenals_pancreas"
    members:
      - "spleen"
      - "adrenals"
      - "pancreas"
    joint_normal: "The spleen, adrenal glands and pancreas are unremarkable."
    partials:
      - members: ["spleen", "adrenals"]
        text: "The spleen and adrenal glands are unremarkable."
      - members: ["spleen", "pancreas"]
        text: "The spleen and pancreas are unremarkable."
      - members: ["adrenals", "pancreas"]
        text: "The adrenal glands and pancreas are unremarkable."
---

## CLINICAL HISTORY

{{technique:clinical_indication}}

## TECHNIQUE

{{technique:phase}}

## COMPARISON

None available.

## FINDINGS

{{liver}}

{{gallbladder}}

{{cbd}}

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

{{lung_bases}}

{{free_fluid}}

{{bones}}

{{soft_tissues}}

## Guidance

Normal aortic calibre: infrarenal aorta up to 2.0 cm (men), 1.8 cm (women). Aneurysm threshold: 3.0 cm.

Normal CBD calibre: up to 6 mm (up to 10 mm post-cholecystectomy).

Bosniak classification for renal cysts. LI-RADS for liver lesions on contrast-enhanced CT.

## COMMENT
