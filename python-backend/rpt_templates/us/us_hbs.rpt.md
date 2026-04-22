---
study_name: "US Hepatobiliary"
aliases:
  - "us hbs"
  - "us hepatobiliary"
  - "ultrasound hbs"
  - "ultrasound hepatobiliary"
technique: "Ultrasound of the hepatobiliary system was performed."
interpolate_normal: true
impression: true
important_first: false
variant: "freeform"
fields:
  - name: "liver"
    normal: "The liver surface is smooth. The liver parenchyma shows normal echogenicity. No suspicious focal hepatic lesion is detected."
  - name: "gallbladder_cbd"
    normal: "The gallbladder wall is normal. The sonographic Murphy's sign is negative.\nNo gallstone is noted.\nThe common duct measures {{measurement:cbd_diameter_cm}} cm."
  - name: "spleen"
    normal: "The spleen is normal in size and echotexture, measuring {{measurement:spleen_length_cm}} cm."
  - name: "pancreas"
    normal: "The imaged pancreas is unremarkable."
  - name: "others"
    optional: true
    normal: ""
groups: []
---

{{liver}}

{{gallbladder_cbd}}

{{spleen}}
{{pancreas}}

{{others}}

## Guidance
- Measurements may not be provided. If you feel they are important, include a placeholder ("[*]") as a place the user can input them (e.g. there is a hypoechoic lesion... measuring [*] cm.).
- Please ensure your units for measurements are correct. Multiply or divide as appropriate.

Regarding the Liver:
- The "Liver" section should include a description of the liver surface, echotexture/echogenicity, and any focal/suspicious lesions. If there is no lesion, please explicitly state this.
  - If any of these three components are not included in the draft, you can assume they are normal and include the relevant normal description in the report. 
  - For example, if the draft only describes the liver echotexture is coarse, but does not mention the liver surface or focal lesions, you can assume that the liver surface is smooth, and there are no focal lesions.
- If the liver shows increased echogenicity, this may suggest hepatic steatosis. But this finding should not be in the impression.
- Anechoic lesions can be considered as cysts. 
- Hypoechoic or hyperechoic lesions are at least indeterminate, if not outright suspicious if there are risk factors. Measurements are needed. Use placeholders if measurements are not provided.
  - If a measurement is provided: lesions greater than 1 cm should undergo further investigation by cross sectional imaging (CT/MRI). Lesions under 1 cm can be followed up sonographically. Add this to the impression as well.
- A nodular hepatic surface and coarsened echotexture are suggestive of cirrhosis.
- Increased hepatic echogenicity is nonspecific and should not be included in the impression.

Regarding the gallbladder and biliary tree:
- The common duct diameter is usually given in mm. This needs to be converted to cm by dividing by 10.
- Common duct diameter should be less than 6 mm. If it is between 6-10 mm, this is indeterminate. You do not need to conclude anything, just insert a placeholder after stating the diameter.
- If the patient is post-cholecystectomy, up to 10 mm is accepted. 
- If the common duct diameter is more than 10 mm, suggest MRCP and correlation with liver function tests.
- Focal mural thickening (especially in the fundus) and/or comet tail artefacts is suggestive of adenomyomatosis
- If the draft states "immobile echogenic foci" (or words to that effect), just leave it as "immobile echogenic foci" in the body of the report. In the impression, conclude that they may represent \
a polyp/adherent soft calculus (if single focus), or polyps/adherent soft calculi (if multiple).

Regarding the spleen:
- Normal splenic diameter is up to 13 cm.

Regarding the pancreas:
- Common options for pancreas:
  - "The imaged pancreas is unremarkable."
  - "The imaged pancreas is unremarkable; the tail is obscured."
  - "The pancreas is obscured."

## COMMENT
