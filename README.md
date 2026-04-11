# 🪢 KNOT | Integrated Campus Ecosystem

**KNOT** is a futuristic, decentralized campus management system designed to streamline resource allocation, real-time infrastructure tracking, and peer-to-peer asset management. Built for operability and speed, it bridges the gap between administrative authority and student needs.

🔗 **Live Interface:** [knot.niksoriginals.in](https://knot.niksoriginals.in)  

---

## 🚀 Core Modules

### 🔬 Infrastructure Node (Resource Hub)
* **Live Tracking:** Real-time occupancy status of Labs, Seminar Halls, and Studios.
* **Smart Auto-Release:** Proprietary protocol that automatically releases nodes back to 'Available' status the moment a reservation window expires.
* **Permission Layer:** Integrated HOD/Dean approval workflow for restricted resources.

### 📦 Marketplace Ledger
* **Asset Barter:** Secure Sell/Trade system within the campus network.
* **Lost & Found:** Peer-to-peer reporting system for misplaced hardware or belongings.
* **Operative Identity:** Every listing is tied to a verified college identity for maximum accountability.

### 🛡 Administrative Authority
* **Telemetry Dashboard:** Real-time analytics on node utilization frequency.
* **Clearance Escalation:** Role-based access control (RBAC) to manage security clearances (Admin, HOD, Dean, Student).
* **Protocol Override:** Direct administrative control to purge data or decommission nodes.

---

## 🛠 Tech Stack

| Layer | Technology |
| :--- | :--- |
| **Frontend** | Tailwind CSS, JavaScript (ES6+), FontAwesome |
| **Backend** | Python (Flask), Gunicorn |
| **Database** | SQLite3 (WAL Mode) |
| **Security** | Resend API (OTP Identity Handshake), Session-based Auth |
| **Deployment** | Custom Domain Integration (niksoriginals.in) |

---

## ⚡ Quick Start (Local Setup)

1.  **Clone the Repository:**
    ```bash
    git clone [https://github.com/niksoriginals/knot-ecosystem.git](https://github.com/niksoriginals/knot-ecosystem.git)
    cd knot-ecosystem
    ```

2.  **Environment Sync:**
    Create a `.env` file and add your credentials:
    ```env
    FLASK_SECRET=your_secure_key
    RESEND_API_KEY=re_your_api_key
    ```

3.  **Deploy Engine:**
    ```bash
    python main.py
    ```

---

## 🧠 System Architecture

KNOT operates on a **Shared-Session Architecture**. By utilizing cross-subdomain cookie management (`.niksoriginals.in`), we ensure a seamless handshake between the Student Hub and Admin Node without requiring multiple logins.

---

## 👨‍💻 Developed By

**Team - Init to Winit** Verification ID: `niksoriginals`  
Email: [nikhilyadavrny_cse25@its.edu.in](mailto:nikhilyadavrny_cse25@its.edu.in)

---

> *Built for the futuristic campus. Governed by the KNOT Protocol.*
