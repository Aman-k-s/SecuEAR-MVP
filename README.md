# SecuEAR

### Cardless payments for people who can't carry a card.

**Razorpay AI Buildathon 2026 — Open Track**

---

## The Problem

Every payment method assumes you have something on you — a card, a phone, cash. But in canteens, factory floors, gyms, and campus dining, people are routinely *without* those things by design:

- Canteen/campus users leave phones in lockers, or don't carry one at all (kids on campus)
- Factory floor workers face formal phone bans for safety — this isn't an edge case, it's standard policy at plants like Tata Steel
- Gym-goers leave both phone and wallet behind by choice

The current workaround — a physical loyalty/ID card — gets lost, forgotten, or handed to someone else. That's a real, recurring operational cost for the institution running the space, not just a shopper inconvenience.

## The Solution

**Enroll once. Recharge from anywhere. Pay with nothing in your hands.**

1. **Enroll** — a 3D ear-shape scan is captured once, at registration, alongside a loyalty/ID sign-up that already happens.
2. **Recharge** — the user (or a parent/employer) tops up a prepaid wallet balance through the app.
3. **Pay** — at a fixed kiosk, a new ear scan is matched against the enrolled profile and the wallet is debited. No card, no phone, no PIN, nothing that can be lost or borrowed.

## The Real Differentiator

Ear biometrics for payments is **not a new idea** — Descartes Biometrics has held patents in this space since 2013, and commercial face/fingerprint canteen systems already serve the "cardless payment" niche across Indian institutions. We're not claiming to be first. We're claiming something narrower and, we think, more defensible:

> **If this database is ever breached, the leaked data has no reuse value beyond this system.**

| | Fingerprint | Face | **Ear (SecuEAR)** |
|---|---|---|---|
| Spoof resistance | Low — can be lifted | Varies — active research arms race | Depth-based matching |
| Breach impact | Reusable across other systems | Enables deepfakes, wider misuse | **Contained to this wallet only** |
| Contact required | Yes | No | No |

A leaked fingerprint or face template has value to an attacker far beyond the system it was stolen from. A leaked ear-shape embedding largely doesn't. That containment property — not "nobody's thought of this before" — is the actual pitch.

*No biometric here is treated as a sole authorizer of a payment — see Confidence-Gated Decisions below.*

## Honest Competitive Landscape

We did the homework so a judge doesn't have to catch us out on it:

- **Descartes Biometrics (HELIX/ERGO)** — patented ear-shape auth since 2013, lists mobile banking as a use case, but has no shipped bank integration and no funding raised to date.
- **Amazon One** — palm-vein payment at general retail, discontinued in 2026. It failed on *adoption*, not technology: shoppers already had fast tap-to-pay and felt no need to switch. This is exactly why SecuEAR targets cardless-by-design populations rather than general retail convenience.
- **Indian face/fingerprint canteen vendors** — mature, commercially deployed cardless canteen/attendance systems already exist at scale in India. We're not filling an empty niche here; we're proposing a specific privacy property none of them lead with.
- **Aadhaar eKYC / DigiYatra** — the incumbent for India's KYC and airport-boarding biometrics. Explicitly out of scope for this MVP (see Roadmap) — not something a payments-wallet hackathon project should compete with directly.

## How It Works

```
.ply scan → depth map → ear crop → embedding → similarity score → tiered decision → wallet debit → audit log
```

| Stage | What happens |
|---|---|
| **Capture** | 3D ear scan via iPhone TrueDepth, exported as a `.ply` point cloud |
| **Preprocess** | Statistical outlier removal + PCA-plane alignment + grid projection → normalized 2D depth map |
| **Ear isolation** | OpenCV Haar cascade crop, with a fallback to the full preprocessed frame if detection is unreliable |
| **Embedding** | A frozen, pretrained CNN (ResNet18) extracts a feature vector — no training required, so it isn't a fragile artifact of our small dataset |
| **Cross-side correction** | A person's left and right ears are mirror-similar but not identical — verifying against the opposite side triggers an automatic horizontal mirror before comparison (research shows ~35% accuracy loss on naive cross-side matching without this) |
| **Decision** | Cosine similarity is checked against tiered thresholds: **auto-approve** (high confidence) → **PIN required** (medium) → **deny** (low) |
| **Audit** | Every decision — at every tier — is logged with its score, threshold, and reasoning. Nothing is a black-box yes/no |

## Core AI Features

- **Embedding-based verification** — new users enroll without retraining any model, unlike a closed-set classifier
- **Confidence-gated, explainable decisions** — directly answers "why should anyone trust a biometric alone with money": it doesn't have to, above a threshold it doesn't clear
- **Cross-side anatomical correction** — a detail most ear-biometric demos skip; we account for it explicitly and log when it's applied
- **Full audit trail** — every enroll/verify/pay event is inspectable, live, in the demo

## Where This Goes

| Tier | Scope | Status |
|---|---|---|
| **Now** | Closed-loop wallets for canteens, factories, gyms, campuses | What this MVP demonstrates |
| **Next** | Retail & supermarkets (DMart, Reliance Fresh, malls) — loyalty-linked wallet alongside cards | Expansion vision |
| **Future** | KYC onboarding, airport/border-style checkpoints | Long-term, explicitly out of MVP scope — Aadhaar eKYC/DigiYatra are real incumbents here, worth acknowledging rather than overclaiming against |

## Known Limitations (stated proactively)

- **Small, controlled dataset** — 3 people, static scans, for demo purposes. This shows the mechanism working correctly, not validated accuracy at scale.
- **No liveness/anti-spoofing in this MVP** — designed, but not built, due to lack of multi-frame capture data. Flagged as future work.
- **Ear-detection reliability on depth maps is unverified** — the Haar cascade step was trained on natural photos, not synthetic depth-map projections; a fallback path exists for when it fails.
- **Payment integration is mocked** — structured to mirror the real Razorpay SDK's shape for an easy future swap, but no live API calls are made in this MVP.

## Tech Stack

| Layer | Choice |
|---|---|
| Capture | iPhone TrueDepth → `.ply` point cloud |
| Preprocessing | Python, Open3D, NumPy |
| Ear isolation | OpenCV (Haar cascade) |
| Embedding | PyTorch + torchvision (pretrained ResNet18, frozen) |
| Backend | FastAPI |
| Database | SQLite |
| Payments | Mocked Razorpay-SDK-shaped service |
| Frontend | Plain HTML / CSS / JS |

## Getting Started

```bash
# Backend
cd backend
pip install -r requirements.txt --break-system-packages
uvicorn app.main:app --reload

# Frontend
cd frontend
# open enroll.html / pay.html / recharge.html / audit.html in a browser
```

Place your `.ply` scan files in `sample_data/` before running enrollment.

## Repository Structure

```
SecuEAR-Razorpay/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── database.py
│   │   ├── models/
│   │   ├── routers/
│   │   └── services/
│   └── requirements.txt
├── frontend/
│   ├── enroll.html
│   ├── pay.html
│   ├── recharge.html
│   └── audit.html
├── sample_data/
└── README.md
```

## Demo

📹 *5-minute demo video: [[https://youtu.be/tqCiC3maw0Y](https://youtu.be/tqCiC3maw0Y)]*


**Aman Kumar Srivastav**
Punjab Engineering College, Chandigarh

📄 **Resume:** [[https://drive.google.com/file/d/1Zbd0Jpy8LkM49TwJUWd3PM605CFdfk_N/view?usp=drive_link](https://drive.google.com/file/d/1Zbd0Jpy8LkM49TwJUWd3PM605CFdfk_N/view?usp=drive_link)]
🔗 **GitHub:** [github.com/Aman-k-s/SecuEAR-Razorpay](https://github.com/Aman-k-s/SecuEAR-Razorpay.git)

---

*Built for Razorpay AI Buildathon 2026 — Open Track.*