# JengaPro & FundiPro - Construction Workforce Management Platform

> **Empowering construction workers and contractors through digital gig tracking and verification**

![JengaPro  Logo](./assets/logo.png)
![FundiPro  Logo](./assets/logo.png)


[![Django](https://img.shields.io/badge/Django-4.2+-green.svg)](https://www.djangoproject.com/)
[![Angular](https://img.shields.io/badge/Angular-17+-red.svg)](https://angular.io/)
[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Status](https://img.shields.io/badge/Status-Production-success.svg)]()

---

## 📋 Table of Contents

- [Overview](#overview)
- [Problem Statement](#problem-statement)
- [Solution](#solution)
- [Key Features](#key-features)
- [Tech Stack](#tech-stack)
- [Architecture](#architecture)
- [User Roles](#user-roles)
- [Core Modules](#core-modules)
- [Screenshots](#screenshots)
- [Installation](#installation)
- [API Documentation](#api-documentation)
- [Database Schema](#database-schema)
- [Business Impact](#business-impact)
- [Future Roadmap](#future-roadmap)
- [Contributing](#contributing)
- [License](#license)

---

## 🎯 Overview

**JengaPro** & **FundiPro** is a comprehensive workforce management platform designed for the construction industry in Kenya. It digitizes gig tracking, worker verification, and performance analytics for both skilled workers (Fundis) and contractors (Supervisors).

The platform addresses critical challenges in informal construction work by providing:
- **Digital work history** for workers
- **Verification systems** for contractors
- **Credit scoring** for worker credibility
- **Real-time analytics** for business decisions
- **Mobile M-Pesa integration** for payments

![Platform Overview](./assets/platform-overview.png)

---

## 🔴 Problem Statement

### Challenges in Kenya's Construction Industry

1. **No Digital Work History**
   - Workers have no verifiable record of their work experience
   - Contractors struggle to assess worker reliability
   - Skilled workers lose opportunities due to lack of credentials

2. **Payment Disputes**
   - Informal agreements lead to payment conflicts
   - No standardized verification process
   - Workers vulnerable to exploitation

3. **Workforce Management**
   - Contractors manually track multiple sites and workers
   - No centralized system for gig management
   - Difficult to verify work completion

4. **Trust & Credibility**
   - No reputation system for workers
   - Contractors rely on word-of-mouth references
   - High risk in hiring unknown workers

---

## ✅ Solution

JengaPro provides a **two-sided platform** connecting workers and contractors:

### For Workers (Fundis):
- 📱 **Digital Portfolio** - Verifiable work history
- ⭐ **Credit Scoring** - Build reputation through verified gigs
- 💰 **Payment Tracking** - Monitor earnings and transactions
- 📊 **Analytics Dashboard** - Track performance metrics
- 🎯 **Job Matching** - Find gigs matching skills

### For Contractors (Supervisors):
- 👥 **Workforce Management** - Track workers across multiple sites
- ✅ **Gig Verification** - Approve and verify completed work
- 📈 **Analytics & Reports** - Business intelligence dashboards
- 🏗️ **Multi-Site Management** - Organize multiple construction sites
- 💳 **Payment Processing** - M-Pesa integration

![Solution Overview](./assets/solution-diagram.png)

---

## ⚡ Key Features

### 🔐 Authentication & Authorization
- JWT-based secure authentication
- Role-based access control (Fundi vs Contractor)
- Phone number verification with OTP
- Password reset functionality
- ID verification system

### 📊 Dual Dashboard System

#### Fundi Dashboard
- Personal work statistics
- Credit score display
- Recent gigs history
- Earnings analytics
- Work trends visualization

![Fundi Dashboard](./assets/fundi-dashboard.png)

#### Contractor Dashboard
- Organization performance metrics
- Worker management
- Gig verification queue
- Revenue analytics
- Multi-site overview

![Contractor Dashboard](./assets/contractor-dashboard.png)

### 💼 Gig Management
- Create and track gigs
- Multi-organization support
- Job type categorization
- Location-based tracking (County/Constituency/Ward)
- Duration tracking (days/weeks)
- Client information management

### ✅ Verification System
- Two-tier verification process
- Supervisor approval workflow
- Automated credit score updates
- Verification history tracking
- Dispute resolution flags

### 📈 Analytics Engine

#### For Workers:
- Work trends over time
- Earnings analytics
- Credit score history
- Organization performance
- Job type breakdown
- Location-based insights

#### For Contractors:
- Gig trends and forecasting
- Worker performance metrics
- Organization analytics
- Revenue tracking
- Verification rates
- Comparative analytics

![Analytics Dashboard](./assets/analytics-sample.png)

### 💳 Payment Integration
- M-Pesa STK Push integration
- Payment verification
- Transaction history
- Payment confirmation workflow
- Revenue tracking

### 🎯 Credit Scoring System
- Points for verified gigs (+5 points)
- Points for completed work (+10 points)
- Score history tracking
- Maximum score: 100 points
- Visual score indicators (Excellent/Good/Building)

### 📱 Responsive Design
- Mobile-first approach
- Progressive Web App (PWA) ready
- Touch-optimized interfaces
- Offline-capable features
- Native app-like experience

---

## 🛠️ Tech Stack

### Backend
```
🐍 Python 3.11+
🎯 Django 4.2+
🔌 Django REST Framework
🔐 JWT Authentication (djangorestframework-simplejwt)
📊 PostgreSQL Database
💳 M-Pesa Daraja API Integration
📦 Pillow (Image Processing)
```

### Frontend
```
⚡ Angular 17+
📱 Angular Material UI
🎨 Custom CSS3 Animations
📊 Chart.js / Recharts
🔄 RxJS for Reactive Programming
📡 HttpClient for API Communication
```

### DevOps & Tools
```
🐳 Docker (containerization)
🔧 Git (version control)
📝 Swagger/OpenAPI (API documentation)
🧪 Pytest (testing)
☁️ Cloud deployment ready
```

![Tech Stack](./assets/tech-stack-diagram.png)

---

## 🏗️ Architecture

### System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Angular Frontend (PWA)                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ Fundi Module │  │Contractor    │  │ Shared       │      │
│  │              │  │Module        │  │ Components   │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└────────────────────────┬────────────────────────────────────┘
                         │ REST API (JSON)
┌────────────────────────▼────────────────────────────────────┐
│                    Django REST Framework                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ Auth APIs    │  │ Gig APIs     │  │ Analytics    │      │
│  │              │  │              │  │ APIs         │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ Payment APIs │  │ Report APIs  │  │ Verify APIs  │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────┐
│                   PostgreSQL Database                        │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ Users │ Gigs │ Organizations │ Payments │ History   │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘

                         │
                         │ External API
                         ▼
              ┌──────────────────────┐
              │   M-Pesa Daraja API  │
              └──────────────────────┘
```

### Data Flow

```
User Action → Angular Component → Service Layer → HTTP Request
                                                        ↓
Backend View ← URL Router ← Django REST API ← Middleware
     ↓
Serializer Validation → Business Logic → Database Query
     ↓
Response Serialization → JSON Response → Frontend
     ↓
State Update → UI Rendering → User Feedback
```

![Architecture Diagram](./assets/architecture.png)

---

## 👥 User Roles

### 1. Fundi (Construction Worker)
**Account Type:** `01`

**Capabilities:**
- View personal work history
- Track credit score
- Monitor earnings
- View analytics dashboard
- Update profile information
- Verify gigs with supervisors
- Track payment status

**Dashboard Focus:**
- Personal performance metrics
- Work consistency tracking
- Credit score building
- Earnings optimization

### 2. Contractor (Supervisor)
**Account Type:** `02`

**Capabilities:**
- Manage multiple organizations/sites
- Create and assign gigs
- Verify worker gigs
- Track worker performance
- Generate reports
- Manage job types
- Process payments
- View comprehensive analytics

**Dashboard Focus:**
- Business intelligence
- Workforce management
- Revenue tracking
- Multi-site coordination

![User Roles](./assets/user-roles.png)

---

## 🎛️ Core Modules

### 1. Authentication Module

**Features:**
- JWT-based authentication
- Phone number verification (OTP)
- Email verification
- ID document upload
- Password reset via email code
- Account type selection

**Key Files:**
- `User` model with custom fields
- `PhoneOTP` model
- `PasswordResetCode` model
- `VerificationRequest` model

### 2. Gig Management Module

**Features:**
- Create gigs with detailed information
- Multi-organization support
- Job type categorization
- Location tracking (County/Constituency/Ward)
- Client information
- Duration tracking
- Amount tracking

**Models:**
- `Gig` - Core gig tracking
- `JobType` - Categorization
- `GigHistory` - Historical records
- `GigsAvailable` - Open positions

### 3. Organization Module

**Features:**
- Multi-site management
- Organization profiles
- Location-based organization
- Owner/supervisor assignment
- Active/inactive status

**Models:**
- `Organization` - Main organization entity
- Related gigs and job types

### 4. Verification Module

**Features:**
- Two-step verification process
- Supervisor approval
- Automated credit score updates
- Verification history
- Rejection reason tracking

**Workflow:**
```
Gig Created → Worker Submits → Supervisor Reviews → 
Approved/Rejected → Credit Score Updated → History Logged
```

### 5. Credit Scoring Module

**Features:**
- Point-based system (0-100)
- Action-based scoring
- History tracking
- Visual indicators

**Score Actions:**
- Gig Verified: +5 points
- Gig Completed: +10 points

**Models:**
- `CreditScoreHistory` - Track all score changes
- User.credit_score field

### 6. Payment Module

**Features:**
- M-Pesa integration
- STK Push functionality
- Payment verification
- Transaction tracking
- Payment history

**Models:**
- `Payment` - Manual payments
- `MpesaNewTransaction` - M-Pesa transactions
- `UserPaymentSession` - Session tracking

### 7. Analytics Module

**Fundi Analytics APIs:**
- Work trends
- Organization performance
- Job type analytics
- Credit score history
- Earnings breakdown
- Work consistency metrics

**Contractor Analytics APIs:**
- Gig trends
- Worker performance
- Job type analytics
- Organization performance
- Revenue analytics
- Verification metrics

### 8. Reporting Module

**Report Types:**
- Gigs report (with filtering)
- Workers performance report
- Organizations report
- Job types report
- Location-based report
- Date range report
- Payment report
- Export functionality (CSV/Excel ready)

---

## 📸 Screenshots

### Mobile Experience

#### Fundi Mobile Dashboard
![Fundi Mobile](./assets/screenshots/fundi-mobile-dashboard.png)

#### Contractor Mobile Dashboard
![Contractor Mobile](./assets/screenshots/contractor-mobile-dashboard.png)

### Desktop Experience

#### Fundi Analytics
![Fundi Analytics](./assets/screenshots/fundi-analytics-desktop.png)

#### Contractor Analytics
![Contractor Analytics](./assets/screenshots/contractor-analytics-desktop.png)

### Key Screens

#### Login & Registration
![Auth Screens](./assets/screenshots/auth-flow.png)

#### Gig Management
![Gig Management](./assets/screenshots/gig-management.png)

#### Verification Queue
![Verification](./assets/screenshots/verification-queue.png)

#### Credit Score Display
![Credit Score](./assets/screenshots/credit-score.png)

---

## 💻 Installation

### Prerequisites

```bash
- Python 3.11+
- Node.js 18+
- PostgreSQL 14+
- Git
```

### Backend Setup

```bash
# Clone repository
git clone https://github.com/yourusername/jengapro.git
cd jengapro/backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Setup environment variables
cp .env.example .env
# Edit .env with your configurations

# Run migrations
python manage.py makemigrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Load initial data (optional)
python manage.py loaddata initial_data.json

# Run development server
python manage.py runserver
```

### Frontend Setup

```bash
cd jengapro/frontend

# Install dependencies
npm install

# Setup environment
cp src/environments/environment.example.ts src/environments/environment.ts
# Edit environment.ts with API URL

# Run development server
ng serve

# Navigate to http://localhost:4200
```

### Environment Variables

**Backend (.env):**
```env
SECRET_KEY=your-secret-key
DEBUG=True
DATABASE_URL=postgresql://user:password@localhost:5432/jengapro

# M-Pesa Configuration
MPESA_CONSUMER_KEY=your-consumer-key
MPESA_CONSUMER_SECRET=your-consumer-secret
MPESA_SHORTCODE=your-shortcode
MPESA_PASSKEY=your-passkey
MPESA_CALLBACK_URL=https://yourdomain.com/api/mpesa/callback/

# Email Configuration
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password
```

**Frontend (environment.ts):**
```typescript
export const environment = {
  production: false,
  apiUrl: 'http://localhost:8000/'
};
```

---

## 📚 API Documentation

### Base URL
```
Development: http://localhost:8000/api/
Production: https://api.jengapro.com/api/
```

### Authentication Endpoints

```http
POST   /api/auth/register/          # Register new user
POST   /api/auth/login/             # Login (returns JWT)
POST   /api/auth/verify-phone/      # Send OTP
POST   /api/auth/confirm-otp/       # Verify OTP
POST   /api/auth/password-reset/    # Request password reset
POST   /api/auth/password-confirm/  # Confirm new password
GET    /api/auth/user/              # Get current user
PUT    /api/auth/user/update/       # Update user profile
```

### Fundi Endpoints

```http
GET    /api/fundi/dashboard/start/                    # Dashboard stats
GET    /api/fundi/dashboard/recent-gigs/              # Recent gigs
GET    /api/fundi/dashboard/calendar/                 # 7-day calendar
GET    /api/fundi/analytics/summary/                  # Analytics summary
GET    /api/fundi/analytics/work-trends/              # Work trends
GET    /api/fundi/analytics/credit-score/             # Credit score history
GET    /api/fundi/analytics/earnings/                 # Earnings analytics
```

### Contractor Endpoints

```http
GET    /api/contractor/dashboard/stats/               # Dashboard stats
GET    /api/contractor/dashboard/recent-gigs/         # Recent gigs
GET    /api/contractor/dashboard/top-sites/           # Top organizations
GET    /api/contractor/dashboard/top-workers/         # Top workers
GET    /api/contractor/dashboard/unverified-gigs/     # Verification queue
GET    /api/contractor/analytics/summary/             # Analytics summary
GET    /api/contractor/analytics/gig-trends/          # Gig trends
GET    /api/contractor/analytics/worker-performance/  # Worker metrics
```

### Gig Management Endpoints

```http
GET    /api/gigs/                   # List all gigs
POST   /api/gigs/                   # Create gig
GET    /api/gigs/{id}/              # Get gig detail
PUT    /api/gigs/{id}/              # Update gig
DELETE /api/gigs/{id}/              # Delete gig
POST   /api/gigs/{id}/verify/       # Verify gig
GET    /api/gigs/available/         # Available gigs
GET    /api/gigs/user-related/      # User's gigs
```

### Organization Endpoints

```http
GET    /api/organizations/          # List organizations
POST   /api/organizations/          # Create organization
GET    /api/organizations/{id}/     # Get organization
PUT    /api/organizations/{id}/     # Update organization
DELETE /api/organizations/{id}/     # Delete organization
```

### Report Endpoints

```http
GET    /api/contractor/reports/gigs/              # Gigs report
GET    /api/contractor/reports/workers/           # Workers report
GET    /api/contractor/reports/organizations/     # Organizations report
GET    /api/contractor/reports/job-types/         # Job types report
GET    /api/contractor/reports/location/          # Location report
GET    /api/contractor/reports/date-range/        # Date range report
GET    /api/contractor/reports/export/            # Export data
```

### Payment Endpoints

```http
POST   /api/payments/mpesa/initiate/     # Initiate M-Pesa payment
POST   /api/payments/mpesa/callback/     # M-Pesa callback
GET    /api/payments/history/            # Payment history
POST   /api/payments/verify/             # Verify payment
```

### Complete API Documentation
📖 Full interactive API docs available at: `/api/docs/` (Swagger/OpenAPI)

---

## 🗄️ Database Schema

### Core Tables

#### Users Table
```sql
- id (PK)
- username
- email
- phone (unique)
- account_type ('01': Fundi, '02': Contractor)
- full_name
- national_id
- county, constituency, ward
- profile_pic
- credit_score (0-100)
- is_verified
- created_at
```

#### Gigs Table
```sql
- id (PK)
- worker_id (FK → Users)
- job_type_id (FK → JobTypes)
- organization_id (FK → Organizations)
- start_date
- duration_value
- duration_unit
- client_name, client_phone
- county, constituency, ward
- amount_paid
- is_verified
- verified_by_id (FK → Users)
- is_complete
- logged_by_id (FK → Users)
- created_at
```

#### Organizations Table
```sql
- id (PK)
- name
- description
- owner_id (FK → Users)
- county, constituency, ward
- phone_number
- is_active
- created_at
```

#### JobTypes Table
```sql
- id (PK)
- organization_id (FK → Organizations)
- name
- code (auto-generated)
```

#### CreditScoreHistory Table
```sql
- id (PK)
- user_id (FK → Users)
- change (+5, +10, etc.)
- new_score
- action ('verify_gig', 'complete_gig')
- timestamp
```

#### Payments Table
```sql
- id (PK)
- user_id (FK → Users)
- amount
- transaction_code
- payment_date
- is_confirmed
```

### Entity Relationship Diagram

![ERD](./assets/database-erd.png)

```
Users 1──M Gigs (as worker)
Users 1──M Gigs (as verified_by)
Users 1──M Gigs (as logged_by)
Users 1──M Organizations (as owner)
Users 1──M CreditScoreHistory
Users 1──M Payments

Organizations 1──M Gigs
Organizations 1──M JobTypes

JobTypes 1──M Gigs
```

---

## 💼 Business Impact

### Metrics & KPIs

**For Workers:**
- ✅ **Digital Work History** - Permanent, verifiable record
- ⭐ **Reputation Building** - Credit scores increase opportunities
- 💰 **Fair Payment** - Transparent tracking reduces disputes
- 📈 **Career Growth** - Data-driven skill development

**For Contractors:**
- 👥 **Workforce Quality** - Hire based on verified history
- 📊 **Data-Driven Decisions** - Analytics for business growth
- ⏱️ **Time Savings** - Automated tracking and reporting
- 💵 **Cost Reduction** - Reduced payment disputes

### Market Opportunity

- **Target Market:** Kenya's construction industry
- **Primary Users:** ~500,000 informal construction workers
- **Secondary Users:** ~50,000 contractors/supervisors
- **Market Size:** $2B+ informal construction sector

### Competitive Advantage

1. **First-Mover** - No comprehensive solution exists
2. **Mobile-First** - Designed for smartphone users
3. **M-Pesa Integration** - Local payment method
4. **Dual-Sided Platform** - Value for both workers and contractors
5. **Credit Scoring** - Unique reputation system

---

## 🚀 Future Roadmap

### Phase 1 (Current)
- ✅ Core platform MVP
- ✅ Authentication & user management
- ✅ Gig tracking & verification
- ✅ Basic analytics
- ✅ M-Pesa integration

### Phase 2 (Q2 2026)
- 🔄 Mobile apps (iOS/Android)
- 🔄 Advanced analytics & AI insights
- 🔄 Worker certifications & training
- 🔄 Contractor marketplace
- 🔄 Multi-language support (Swahili)

### Phase 3 (Q3 2026)
- 📋 Insurance integration
- 📋 Loan/credit facilities for workers
- 📋 Equipment rental marketplace
- 📋 Supply chain integration
- 📋 Video verification

### Phase 4 (Q4 2026)
- 📋 Regional expansion (East Africa)
- 📋 Blockchain-based credentials
- 📋 AI job matching
- 📋 Payroll automation
- 📋 Government integration (NSSF, NHIF)

---

## 🤝 Contributing

We welcome contributions! Please follow these steps:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

### Coding Standards

**Python/Django:**
- Follow PEP 8
- Write tests for new features
- Document all functions/classes
- Use type hints where applicable

**TypeScript/Angular:**
- Follow Angular style guide
- Use TypeScript strict mode
- Write unit tests (Jest/Jasmine)
- Document complex logic

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 📞 Contact & Support

- **Email:** support@jengapro.com
- **Website:** https://jengapro.com
- **Documentation:** https://docs.jengapro.com
- **GitHub:** https://github.com/yourusername/jengapro
- **Twitter:** @JengaProApp

---

## 🙏 Acknowledgments

- Kenya's construction workers for insights and feedback
- Open source community for amazing tools
- M-Pesa Daraja API team
- All contributors and testers

---

## 📊 Project Stats

![GitHub stars](https://img.shields.io/github/stars/yourusername/jengapro?style=social)
![GitHub forks](https://img.shields.io/github/forks/yourusername/jengapro?style=social)
![GitHub watchers](https://img.shields.io/github/watchers/yourusername/jengapro?style=social)

**Made with ❤️ for Kenya's Construction Workforce**

---

*Last Updated: February 2026*