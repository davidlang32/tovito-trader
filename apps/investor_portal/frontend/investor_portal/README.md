# Tovito Trader - Investor Portal

A React-based web portal for fund investors to view their positions, returns, and transactions.

## Features

- 🔐 Secure JWT authentication
- 📊 Real-time portfolio overview
- 📈 Fund performance metrics (daily, MTD, YTD, since inception)
- 💰 Transaction history
- 📱 Responsive design (mobile-friendly)

## Screenshots

### Login Page
- Clean, professional login form
- Email/password authentication
- Error handling for invalid credentials

### Dashboard
- Portfolio value and shares
- Total return (dollars and percent)
- Current NAV per share
- Portfolio percentage of total fund
- Fund performance metrics
- Recent transactions
- Account summary

## Setup

### Prerequisites
- Node.js 18+ installed
- Fund API running on localhost:8000

### Installation

```bash
# Navigate to portal folder
cd apps/investor_portal/frontend

# Install dependencies
npm install

# Start development server
npm run dev
```

The portal will be available at: **http://localhost:3000**

### Build for Production

```bash
npm run build
```

Output will be in the `dist` folder.

## Configuration

The API URL is configured in `src/App.jsx`:

```javascript
const API_BASE_URL = 'http://localhost:8000';
```

For production, update this to your API server URL.

## Tech Stack

- **React 18** - UI framework
- **Vite** - Build tool
- **Tailwind CSS** - Styling
- **Lucide React** - Icons

## Security

- JWT tokens stored in localStorage
- Access tokens expire in 30 minutes
- Refresh tokens expire in 7 days
- All API calls require authentication

## API Endpoints Used

| Endpoint | Purpose |
|----------|---------|
| POST /auth/login | User authentication |
| GET /auth/me | Current user info |
| GET /investor/position | Portfolio position |
| GET /investor/transactions | Transaction history |
| GET /nav/current | Current NAV |
| GET /nav/performance | Fund performance |
