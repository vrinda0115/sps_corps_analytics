# Project Specification: Ophthalmology Clinical Tutor (Ophtho-Tutor)

## 1. Project Vision
* **Title:** The Ophthalmology Clinical Tutor (Ophtho-Tutor)
* **Tone:** The Encouraging Expert
* **Primary Objective:** To provide medical students with a high-fidelity diagnostic simulator for common eye conditions, offering "Diagnostic Post-Mortems" and targeted study resources (mnemonics/videos) upon failure.

---

## 2. Team Roles & Responsibilities
| Member | Primary Focus | Key Deliverables |
| :--- | :--- | :--- |
| **Raj Singh** | UI & Integration | Streamlit Dashboard, `st.session_state` management, Sidebar controls. |
| **Vrinda Thakur** | Agent Logic | The "Judge LLM" prompt, Synonym mapping, System persona locking. |
| **Srishti Srinivasan** | Data & Knowledge | The "Study Vault" JSON, 24 Pathognomonic Fact Sheets (.txt files). |

---

## 3. Technical Requirements (Functional)
1.  **The "Ophtho-Five" Coverage:** The system shall cover Glaucoma, Cataracts, Retinal Detachment, Conjunctivitis, and Macular Degeneration.
2.  **Dual-Persona Logic:** The AI shall act as a "Patient" (medically illiterate) during the interview and an "Encouraging Expert" during the review.
3.  **The Judge LLM:** The system shall use an LLM-based verification to check if the student's diagnosis is a semantic match to the ground truth.
4.  **The Two-Strike Rule:**
    * *Strike 1:* Provide a "Socratic Hint" (guiding question).
    * *Strike 2:* Trigger the Diagnostic Post-Mortem and the Study Card.
5.  **Study Vault (JSON):** The system shall retrieve YouTube links (from Moran CORE/CataractCoach) and mnemonics specific to the identified disease.
6.  **Pathognomonic Retrieval:** The system shall search the Vector Store for disease-specific clues to provide a "Missed Clues" summary.

---

## 4. Technical Stack
* **Interface:** Streamlit (deployed via Google Colab/Local Tunnel).
* **LLM Engine:** Llama-3.1-8B (via Groq/Ollama for speed).
* **Vector Database:** FAISS (In-memory storage for 24 case files).
* **Data Structure:** JSON for study resources; `.txt` for RAG case context.

---

## 5. Non-Functional Requirements
* **Latency:** The Judge LLM and Post-Mortem generation shall respond in **< 4 seconds**.
* **Privacy/Statelessness:** No user medical inputs shall be stored permanently; all session states reset on browser refresh.
* **Accuracy:** The Judge LLM must achieve **> 90% accuracy** in synonym matching (e.g., matching "Pink Eye" to "Conjunctivitis").

---

## 6. Evaluation Plan (10-Scenario Stress Test)
**Lead:** TBD

| # | Scenario | Expected Behavior |
| :--- | :--- | :--- |
| 1 | **Classic Presentation** | AI patient accurately describes "halos" for Glaucoma. |
| 2 | **Synonym Match** | Judge LLM accepts "AMD" as "Macular Degeneration." |
| 3 | **Strike 1 Logic** | AI gives a hint about "anatomy" without naming the disease. |
| 4 | **Strike 2 Logic** | AI reveals the Study Card after the second wrong guess. |
| 5 | **Critical Failure** | AI uses "Clinical Gravity" tone for Retinal Detachment misses. |
| 6 | **The Distractor** | AI differentiates between viral (watery) and bacterial (sticky) eye. |
| 7 | **Vague Complaint** | Patient responds to "Tell me more" with a secondary symptom. |
| 8 | **Empty Guess** | System prevents "Reveal" if no guess has been submitted. |
| 9 | **Video Integration** | YouTube link correctly renders in the Overlay Card. |
| 10 | **Session Reset** | "New Case" button successfully clears the FAISS buffer and history. |
