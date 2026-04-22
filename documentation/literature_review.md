# Background: Literature Review

## Introduction

The radiology report is the primary means of communication between the radiologist and the referring clinician. Despite its centrality to patient care, the reporting process remains largely manual, time-consuming, and inconsistent in structure. As imaging volumes grow and radiologist workload intensifies, there is increasing interest in artificial intelligence (AI) tools that can assist with report generation without compromising clinical accuracy or patient safety. This review examines the evidence base for an LLM-assisted radiology report formatting system — one that takes a radiologist's draft findings, classifies the study type, extracts and maps findings to a structured template, renders a formatted report, and generates an impression — operating entirely on local infrastructure.

The review is organised into six thematic sections: (1) the radiology reporting burden and burnout crisis; (2) evidence for structured reporting over free-text; (3) the evolution of NLP applied to radiology reports; (4) LLMs for radiology report generation and structuring; (5) hallucination risks and safety considerations; and (6) local and on-premise deployment of AI in healthcare.

---

## 1. The Radiology Reporting Burden

Radiologist workload has increased dramatically over the past two decades, driven by rising imaging utilisation and increasingly complex examinations. A study of imaging workload trends found that the number of monthly image slices per radiologist increased by 399% between 2009 and 2022, from 48,781 to 243,518, even as the number of monthly studies per radiologist remained relatively constant (Troupis, Knight, & Lau, 2024). This discrepancy reflects the growing complexity of cross-sectional imaging, where each study now contains substantially more data for interpretation.

The consequences for radiologist wellbeing are severe. A systematic review by Fawzy et al. (2023), which screened 6,379 studies and included 23 eligible publications from seven countries, found that overall burnout prevalence among radiologists ranged from 33% to 88%, with high burnout prevalence ranging from 5% to 62%. Emotional exhaustion prevalence estimates ranged from 11% to 100%, and depersonalisation from 4% to 97% [1]. In a 2022 survey, 54% of radiologists reported feelings of burnout, and the rate of burnout among US physicians broadly had risen to the highest levels recorded since 2011, with 63% reporting at least one burnout measure [2].

Increasing clinical demands have been identified as a leading source of job-related stress, constraining radiologists' ability to perform non-interpretive duties critical for both private and academic practice [2]. AI-powered report formatting tools have the potential to reduce the cognitive and administrative burden of structuring reports, allowing radiologists to focus on the interpretive work that constitutes their primary clinical value.

> [1] Fawzy, N. A., et al. (2023). Incidence and factors associated with burnout in radiologists: A systematic review. *European Journal of Radiology Open*, 11, 100530. https://doi.org/10.1016/j.ejro.2023.100530 | PMID: 37920681
>
> [2] Troupis, C. J., Knight, R. A. H., & Lau, K. K. P. (2024). What is the appropriate measure of radiology workload: Study or image numbers? *Journal of Medical Imaging and Radiation Oncology*, 68(5), 530–539. https://doi.org/10.1111/1754-9485.13713 | PMID: 38837555

---

## 2. Structured Versus Free-Text Reporting

The benefits of structured reporting in radiology have been investigated extensively. Nobel et al. (2022) conducted a systematic review searching PubMed, Embase, and the Cochrane Library, categorising structured reporting into two levels: level 1 (structured layout using templates and checklists) and level 2 (structured content using drop-down menus and clickable decision trees). The review found that structured reporting improves report completeness, consistency, and referring clinician satisfaction compared to free-text reporting, though the overall level of evidence was judged to be low and adoption barriers — including perceived rigidity and increased reporting time — remain significant [3].

The European Society of Radiology (ESR) published an updated position paper on structured reporting in 2023, authored by Pinto dos Santos et al. The ESR paper acknowledged that despite many physicians' preference for structured reports and initiatives by national radiological societies, structured reporting has still not been widely adopted in clinical routine. The update highlighted that advances in AI and large language models may provide innovative approaches to integrate structured reporting more seamlessly into clinical workflows [4]. This observation directly motivates the use of LLMs to automate the template-population process — removing the manual formatting overhead that has historically hindered structured reporting adoption.

The RSNA Radiology Reporting Template Library, built on the RadLex controlled vocabulary (containing over 34,000 terms covering diseases, anatomy, and imaging observations), has provided over 250 peer-reviewed reporting templates searchable by keyword, specialty, and language. The IHE MRRT (Management of Radiology Report Templates) profile, developed in 2013, defines a standardised format for template interchange using an HTML5 extension [5]. These standardisation efforts provide the foundational infrastructure upon which LLM-assisted template population can be built.

> [3] Nobel, J. M., van Geel, K., & Robben, S. G. F. (2022). Structured reporting in radiology: A systematic review to explore its potential. *European Radiology*, 32(4), 2837–2854. https://doi.org/10.1007/s00330-021-08327-5 | PMID: 34652520
>
> [4] European Society of Radiology (ESR). (2023). ESR paper on structured reporting in radiology — update 2023. *Insights into Imaging*, 14, 199. https://doi.org/10.1186/s13244-023-01560-0 | PMID: 37995019
>
> [5] Defined, D. P., et al. (2013). From guidelines to practice: How reporting templates promote the use of radiology practice guidelines. *Journal of the American College of Radiology*, 10(4), 268–273. See also: IHE MRRT profile (2013) and RSNA RadLex (>34,000 terms). RSNA Report Template Library: https://radreport.org

---

## 3. Natural Language Processing Applied to Radiology Reports

Prior to the emergence of large language models, natural language processing (NLP) in radiology predominantly relied on rule-based systems and task-specific deep learning models. Casey et al. (2021) conducted a comprehensive systematic review of 164 publications applying NLP to radiology reports, observing that publication volume in 2019 was nearly triple that of 2015. The dominant applications were report classification and information extraction, with deep learning methods becoming increasingly prevalent after 2018. Critically, the review identified report structure heterogeneity as a major challenge — the very problem that template-based structured reporting seeks to address [6].

The CheXpert labeller (Irvin et al., 2019) represented a landmark in rule-based radiology NLP, automatically extracting 14 observation labels from 224,316 chest radiograph reports using negation and uncertainty detection. This was subsequently surpassed by CheXbert (Smit et al., 2020), a BERT-based model that achieved near-expert accuracy for automated labelling of radiology reports, demonstrating that transformer architectures could effectively extract structured information from free-text radiology reports [7]. These pre-LLM approaches validated the feasibility of automated information extraction from radiology text, but were limited to predefined classification tasks rather than flexible template population.

A review by López-Úbeda, Martín-Noguerol, Juluru, and Luna (2022) documented the transition in radiology NLP from rule-based approaches to deep learning, noting that BERT consistently outperformed CNN, LSTM, and Dense architectures in stability across varying training sizes and disease prevalence [8]. This trajectory — from rules to task-specific transformers to general-purpose LLMs — contextualises the current generation of report formatting tools.

> [6] Casey, A., Davidson, E., Poon, M., Dong, H., Duma, D., Grivas, A., ... & Alex, B. (2021). A systematic review of natural language processing applied to radiology reports. *BMC Medical Informatics and Decision Making*, 21, 179. https://doi.org/10.1186/s12911-021-01533-7 | PMID: 34082729
>
> [7] Smit, A., Jain, S., Rajpurkar, P., Pareek, A., Ng, A. Y., & Lungren, M. P. (2020). CheXbert: Combining automatic labelers and expert annotations for accurate radiology report labeling using BERT. *Proceedings of the 2020 Conference on Empirical Methods in Natural Language Processing (EMNLP)*, 1500–1519.
>
> [8] López-Úbeda, P., Martín-Noguerol, T., Juluru, K., & Luna, A. (2022). Natural language processing in radiology: Update on clinical applications. *Journal of the American College of Radiology*, 19(11), 1271–1285. https://doi.org/10.1016/j.jacr.2022.06.016 | PMID: 36029890

---

## 4. Large Language Models for Radiology Report Generation and Structuring

The application of LLMs to radiology report structuring has been the subject of rapid and prolific investigation. Busch, Hoffmann, Pinto dos Santos et al. (2025) published a narrative review in *European Radiology* examining ten studies on LLMs for structured reporting, including work on GPT-3.5 (n=5) and GPT-4 (n=8). All studies reported promising results, and six of ten demonstrated feasibility for multilingual applications [9].

The seminal feasibility study in this area is by Adams, Truhn, Busch et al. (2023), published in *Radiology*. The authors demonstrated that GPT-4 could effectively transform free-text radiology reports into structured formats across multiple languages, with radiologists rating the structured outputs as clinically acceptable in over 90% of cases. This study established that LLM-driven post hoc structuring of radiology reports is feasible and clinically useful [10]. This finding is directly relevant to the present system, which performs an analogous transformation: taking a radiologist's draft findings and mapping them into a predefined template structure.

Subsequent work has extended these findings to specialised reporting systems. Studies have evaluated GPT-4 for extracting LI-RADS features from multilingual free-text liver MRI reports [PMID: 38651924], while another demonstrated GPT-4o's ability to convert coronary CT angiography reports into structured CAD-RADS data [PMID: 40929727]. These studies confirm that LLMs can handle the domain-specific terminology and classification systems prevalent in subspecialty radiology.

In terms of productivity impact, Huang et al. (2025) conducted a prospective cohort study of 11,980 model-assisted radiograph interpretations deployed in live clinical care at Northwestern University. The study, published in *JAMA Network Open*, found that generative AI use was associated with a 15.5% documentation efficiency improvement, with no change in radiologist-evaluated clinical accuracy or textual quality of reports [11]. This provides direct evidence that AI-assisted report generation can improve throughput without compromising quality.

Hartsock et al. (2025) specifically evaluated local LLMs for improving radiology report conciseness and structure. Using a dataset of 814 reports from seven board-certified body radiologists, the authors tested five prompting strategies within the LangChain framework. The Mixtral LLM demonstrated superior adherence to formatting requirements compared to Llama variants, and the optimal strategy — condensing reports first, then applying structured formatting — reduced redundant word counts by more than 53% [12].

> [9] Busch, F., Hoffmann, L., Pinto dos Santos, D., Makowski, M. R., Saba, L., Prucker, P., ... & Bressem, K. K. (2025). Large language models for structured reporting in radiology: Past, present, and future. *European Radiology*, 35, 2589–2602. https://doi.org/10.1007/s00330-024-11107-6 | PMID: 39438330
>
> [10] Adams, L. C., Truhn, D., Busch, F., Kader, A., Niehues, S. M., Makowski, M. R., & Bressem, K. K. (2023). Leveraging GPT-4 for post hoc transformation of free-text radiology reports into structured reporting: A multilingual feasibility study. *Radiology*, 307(4), e230725. https://doi.org/10.1148/radiol.230725 | PMID: 37014240
>
> [11] Huang, J., Wittbrodt, M. T., Teague, C. N., Karl, E., Galal, G., Thompson, M., et al. (2025). Efficiency and quality of generative AI-assisted radiograph reporting. *JAMA Network Open*. PMID: 40471579
>
> [12] Hartsock, I., Araujo, A., Folio, L., & Rasool, G. (2025). Improving radiology report conciseness and structure via local large language models. *Journal of Imaging Informatics in Medicine*, 39, 1005–1016. https://doi.org/10.1007/s10278-025-01510-w | PMID: 40259201

---

## 5. Hallucination, Safety, and Constrained Generation

A critical concern in applying LLMs to clinical documentation is the risk of hallucination — the generation of plausible but factually incorrect content. In radiology, hallucinated findings could lead to unnecessary procedures, missed diagnoses, or medicolegal liability. This concern is particularly acute for report generation systems, where a fabricated finding (e.g., a non-existent lesion) could directly alter patient management.

Asgari et al. (2025) proposed a comprehensive framework for assessing clinical safety and hallucination rates of LLMs in medical text summarisation, published in *npj Digital Medicine*. The framework comprises an error taxonomy, an experimental structure for iterative comparisons, and a clinical safety evaluation methodology. Across 12,999 clinician-annotated sentences derived from 18 experimental configurations, the authors observed a 1.47% hallucination rate and a 3.45% omission rate. Critically, through prompt refinement and workflow optimisation, major errors were reduced below previously reported human note-taking error rates [13].

A review by Salehi, Singh, Horst, Hathaway, and Erickson (2025) on agentic AI and LLMs in radiology documented that hallucination rates in medical imaging contexts range from 8% to 15% across current systems, with hallucinations manifesting as phantom lesions, mischaracterised pathologies, or fabricated anatomical descriptions. The review identified retrieval-augmented generation (RAG) as a promising mitigation strategy, with one study reporting that RAG eliminated hallucinations entirely (0% vs 8%) in controlled conditions [14].

These findings underscore the importance of constrained generation approaches. The present system addresses hallucination risk through several architectural safeguards: (a) the LLM is constrained to extract only information present in the radiologist's draft input; (b) findings not mentioned in the draft are marked `__NOT_DOCUMENTED__` rather than inferred or fabricated; (c) the output is mapped to a predefined template with known anatomical fields, limiting the space for unconstrained generation; and (d) every input-output pair is logged for audit trail and medicolegal traceability.

> [13] Asgari, E., Montaña-Brown, N., Dubois, M., Khalil, S., Balloch, J., Au Yeung, J., & Pimenta, D. (2025). A framework to assess clinical safety and hallucination rates of LLMs for medical text summarisation. *npj Digital Medicine*, 8(1), 274. https://doi.org/10.1038/s41746-025-01670-7 | PMID: 40360677
>
> [14] Salehi, S., Singh, Y., Horst, K. K., Hathaway, Q. A., & Erickson, B. J. (2025). Agentic AI and large language models in radiology: Opportunities and hallucination challenges. *Bioengineering*, 12(12), 1303. https://doi.org/10.3390/bioengineering12121303

---

## 6. Local and On-Premise Deployment

A distinguishing feature of the present system is its local deployment architecture, with no patient data transmitted to external cloud services. This addresses a fundamental tension in healthcare AI: the trade-off between model capability and data privacy.

Savage et al. (2025) published a review and tutorial in *Radiology* on open-source LLMs for practical research and clinical deployment, noting that open-source models offer several practical advantages over proprietary counterparts for radiology applications. The tutorial provides implementation guidance including prompt engineering, retrieval-augmented generation, and fine-tuning techniques, with code examples for commonly used tools [15].

Kotter et al. (2024) directly evaluated on-premise, open-source LLMs for automatically structuring free-text radiology reports. Using a locally hosted Llama-2-70B-chat model, the authors processed 202 English reports from the MIMIC-CXR dataset and 197 German reports from a university hospital. The LLM achieved a Matthews correlation coefficient (MCC) of 0.75 for English and 0.66 for German, with F1 scores of 0.70 and 0.68 respectively. Performance differences between the LLM and human readers fell within the region of practical equivalence for both languages [16]. This study demonstrates that on-premise deployment of open-source models can achieve approximately human-level accuracy for report structuring without requiring any data to leave the institution.

The privacy motivation for local deployment is well-documented. Using proprietary cloud-based models requires transmitting patient data externally, raising concerns under regulatory frameworks including HIPAA and GDPR. Cai (2023) specifically examined the feasibility and prospects of privacy-preserving LLMs in radiology, noting that publicly available open-source models can circumvent stricter regulatory requirements if their licence permits local deployment [17]. Open-source models can be loaded via standard frameworks (e.g., Hugging Face Transformers) in full precision or quantised formats (4-bit, 8-bit, GGUF), enabling deployment on consumer or edge hardware.

> [15] Savage, C. H., Kanhere, A., Parekh, V., Langlotz, C. P., Joshi, A., Huang, H., & Doo, F. X. (2025). Open-source large language models in radiology: A review and tutorial for practical research and clinical deployment. *Radiology*, 314(1), e241073. https://doi.org/10.1148/radiol.241073 | PMID: 39873598
>
> [16] Kotter, E., et al. (2024). Automatic structuring of radiology reports with on-premise open-source large language models. *European Radiology*. https://doi.org/10.1007/s00330-024-11074-y | PMID: 39390261
>
> [17] Cai, W. (2023). Feasibility and prospect of privacy-preserving large language models in radiology. *Radiology*, 309(1), e232335. https://doi.org/10.1148/radiol.232335 | PMID: 37815443

---

## Summary and Research Gap

The literature establishes that: (a) radiologist workload and burnout are at crisis levels, driven by exponentially increasing imaging complexity; (b) structured reporting demonstrably improves report quality and clinical utility, but adoption remains low due to the manual overhead of template use; (c) LLMs can effectively transform free-text radiology reports into structured formats with clinically acceptable accuracy; (d) hallucination is a manageable risk when appropriate constraints and audit mechanisms are in place; and (e) local deployment of open-source LLMs is technically feasible and addresses critical data privacy requirements.

The present system occupies a specific niche at the intersection of these findings. Rather than generating reports *de novo* from images — which carries substantial hallucination risk and regulatory burden — it operates as a **formatting assistant**: taking the radiologist's own clinical observations and structuring them into a standardised template. The radiologist remains the sole source of clinical findings, and the LLM's role is limited to classification, extraction, mapping, and impression synthesis. This human-in-the-loop architecture preserves clinical authority while automating the mechanical aspects of report construction.

Furthermore, the system's fully local deployment model eliminates the privacy concerns associated with cloud-based LLM services, making it suitable for environments where data sovereignty is paramount. The combination of template-constrained generation, explicit `__NOT_DOCUMENTED__` marking for absent findings, and comprehensive input-output logging provides a layered safety framework not typically present in general-purpose LLM applications.

To our knowledge, no existing system integrates all of these elements — LLM-assisted study classification, template-based findings extraction, constrained report rendering, impression generation, local deployment, and full audit logging — into a single end-to-end pipeline specifically designed for radiology report formatting from draft findings.

---

## References

1. Fawzy, N. A., et al. (2023). Incidence and factors associated with burnout in radiologists: A systematic review. *European Journal of Radiology Open*, 11, 100530. https://doi.org/10.1016/j.ejro.2023.100530

2. Troupis, C. J., Knight, R. A. H., & Lau, K. K. P. (2024). What is the appropriate measure of radiology workload: Study or image numbers? *Journal of Medical Imaging and Radiation Oncology*, 68(5), 530–539. https://doi.org/10.1111/1754-9485.13713

3. Nobel, J. M., van Geel, K., & Robben, S. G. F. (2022). Structured reporting in radiology: A systematic review to explore its potential. *European Radiology*, 32(4), 2837–2854. https://doi.org/10.1007/s00330-021-08327-5

4. European Society of Radiology (ESR). (2023). ESR paper on structured reporting in radiology — update 2023. *Insights into Imaging*, 14, 199. https://doi.org/10.1186/s13244-023-01560-0

5. RSNA Radiology Reporting Template Library (https://radreport.org); RadLex controlled vocabulary; IHE Management of Radiology Report Templates (MRRT) profile (2013).

6. Casey, A., Davidson, E., Poon, M., et al. (2021). A systematic review of natural language processing applied to radiology reports. *BMC Medical Informatics and Decision Making*, 21, 179. https://doi.org/10.1186/s12911-021-01533-7

7. Smit, A., Jain, S., Rajpurkar, P., et al. (2020). CheXbert: Combining automatic labelers and expert annotations for accurate radiology report labeling using BERT. *EMNLP 2020*, 1500–1519.

8. López-Úbeda, P., Martín-Noguerol, T., Juluru, K., & Luna, A. (2022). Natural language processing in radiology: Update on clinical applications. *Journal of the American College of Radiology*, 19(11), 1271–1285. https://doi.org/10.1016/j.jacr.2022.06.016

9. Busch, F., Hoffmann, L., Pinto dos Santos, D., et al. (2025). Large language models for structured reporting in radiology: Past, present, and future. *European Radiology*, 35, 2589–2602. https://doi.org/10.1007/s00330-024-11107-6

10. Adams, L. C., Truhn, D., Busch, F., et al. (2023). Leveraging GPT-4 for post hoc transformation of free-text radiology reports into structured reporting: A multilingual feasibility study. *Radiology*, 307(4), e230725. https://doi.org/10.1148/radiol.230725

11. Huang, J., Wittbrodt, M. T., Teague, C. N., et al. (2025). Efficiency and quality of generative AI-assisted radiograph reporting. *JAMA Network Open*. PMID: 40471579

12. Hartsock, I., Araujo, A., Folio, L., & Rasool, G. (2025). Improving radiology report conciseness and structure via local large language models. *Journal of Imaging Informatics in Medicine*, 39, 1005–1016. https://doi.org/10.1007/s10278-025-01510-w

13. Asgari, E., Montaña-Brown, N., Dubois, M., et al. (2025). A framework to assess clinical safety and hallucination rates of LLMs for medical text summarisation. *npj Digital Medicine*, 8(1), 274. https://doi.org/10.1038/s41746-025-01670-7

14. Salehi, S., Singh, Y., Horst, K. K., Hathaway, Q. A., & Erickson, B. J. (2025). Agentic AI and large language models in radiology: Opportunities and hallucination challenges. *Bioengineering*, 12(12), 1303. https://doi.org/10.3390/bioengineering12121303

15. Savage, C. H., Kanhere, A., Parekh, V., et al. (2025). Open-source large language models in radiology: A review and tutorial for practical research and clinical deployment. *Radiology*, 314(1), e241073. https://doi.org/10.1148/radiol.241073

16. Kotter, E., et al. (2024). Automatic structuring of radiology reports with on-premise open-source large language models. *European Radiology*. https://doi.org/10.1007/s00330-024-11074-y

17. Cai, W. (2023). Feasibility and prospect of privacy-preserving large language models in radiology. *Radiology*, 309(1), e232335. https://doi.org/10.1148/radiol.232335
