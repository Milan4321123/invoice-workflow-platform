# 🚀 Render Deployment - Database Configuration Fix

## 🚨 **Issue on Render Platform**

Your System Health Dashboard shows "GESUND" on Render but upload/fetching fails because:

### **The Problem:**
- **Environment variables are not configured in Render Dashboard**
- **Health checks pass** because they only verify if variables exist (they're set to placeholder values)
- **Database service fails** because Render can't connect to actual Supabase

---

## ✅ **Fix for Render Deployment**

### **Step 1: Configure Backend Service Environment Variables**

Go to your **Render Dashboard** > **ocr-invoice-backend** service > **Environment** tab and add:

```bash
# DATABASE CREDENTIALS (REQUIRED)
SUPA_URL=https://YOUR-PROJECT-ID.supabase.co
SUPA_SERVICE_ROLE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
SUPA_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9... (same as service role key)
SUPA_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9... (public anon key)

# AUTHENTICATION
JWT_SECRET=your-long-random-jwt-secret-here
ADMIN_USERNAME=admin
ADMIN_EMAIL=admin@yourcompany.com
ADMIN_PASSWORD=secure-admin-password
ADMIN_FULL_NAME=Administrator

# COMPANY INFO
COMPANY_NAME=Your Company Name
COMPANY_EMAIL=contact@yourcompany.com

# EMAIL SERVICE (Optional - can use mock)
SENDGRID_API_KEY=SG.your-sendgrid-key-here
FROM_EMAIL=noreply@yourcompany.com
FROM_NAME=Your Company Name

# RENDER-SPECIFIC
USE_MOCK_STORAGE=false
USE_MOCK_OCR=true
ENABLE_EMAIL_NOTIFICATIONS=true

# CORS CONFIGURATION (CRITICAL!)
FRONTEND_URL=https://ocr-invoice-frontend.onrender.com
```

### **Step 2: Configure Frontend Service Environment Variables**

Go to your **Render Dashboard** > **ocr-invoice-frontend** service > **Environment** tab and add:

```bash
# DATABASE ACCESS
NEXT_PUBLIC_SUPABASE_URL=https://YOUR-PROJECT-ID.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...

# API CONNECTION  
NEXT_PUBLIC_API_URL=https://ocr-invoice-backend.onrender.com

# ENVIRONMENT
NODE_ENV=production
```

### **Step 3: Get Your Supabase Credentials**

**Option A: If you have Supabase project:**
1. Go to https://supabase.com/dashboard
2. Select your project
3. Go to **Settings** > **API**
4. Copy:
   - **Project URL** → Use for `SUPA_URL`
   - **anon public key** → Use for `SUPA_ANON_KEY` 
   - **service_role secret key** → Use for `SUPA_SERVICE_ROLE_KEY`

**Option B: Create new Supabase project:**
1. Go to https://supabase.com
2. Sign up/login and create new project
3. Wait for setup (2-3 minutes)
4. Copy credentials from **Settings** > **API**

### **Step 4: Create Database Tables**

In your Supabase project, go to **SQL Editor** and run:

```sql
-- Create main invoices table
CREATE TABLE IF NOT EXISTS invoices_clean (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  file_name VARCHAR(255) NOT NULL,
  file_path VARCHAR(500),
  file_size BIGINT,
  mime_type VARCHAR(100),
  status VARCHAR(50) DEFAULT 'uploaded',
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Enable Row Level Security
ALTER TABLE invoices_clean ENABLE ROW LEVEL SECURITY;

-- Create policy for service role (backend access)
CREATE POLICY "Service role full access" ON invoices_clean
FOR ALL USING (true);

-- Create storage buckets
INSERT INTO storage.buckets (id, name, public) 
VALUES ('invoices', 'invoices', true)
ON CONFLICT (id) DO NOTHING;

INSERT INTO storage.buckets (id, name, public) 
VALUES ('folderwatcher', 'folderwatcher', true)
ON CONFLICT (id) DO NOTHING;

-- Allow storage access
CREATE POLICY "Service role storage access" ON storage.objects
FOR ALL USING (true);
```

### **Step 5: Deploy Services**

1. **Trigger Backend Redeploy:**
   - Go to your backend service in Render
   - Click **Manual Deploy** > **Deploy latest commit**

2. **Trigger Frontend Redeploy:**
   - Go to your frontend service in Render  
   - Click **Manual Deploy** > **Deploy latest commit**

---

## 🧪 **Test the Fix**

### **Check Backend Health:**
```bash
curl -s "https://ocr-invoice-backend.onrender.com/api/system-health"
```

**Expected:** Database shows "Connected" with real response times

### **Check Invoices Endpoint:**
```bash
curl -s "https://ocr-invoice-backend.onrender.com/api/invoices"
```

**Expected:** JSON with invoices array (not "Database service not available")

### **Check Frontend:**
Visit: `https://ocr-invoice-frontend.onrender.com`

**Expected:** Login page loads and you can authenticate

---

## 🔍 **Debugging on Render**

### **View Service Logs:**
1. Go to **Render Dashboard** > Your service
2. Click **Logs** tab
3. Look for:
   - ✅ `Database service connected to: https://...`
   - ❌ `Database credentials missing. Running in offline mode.`
   - ❌ `Failed to connect to database:`

### **Common Issues:**

**1. CORS Errors:**
Make sure `FRONTEND_URL` is set to your exact frontend URL:
```bash
FRONTEND_URL=https://ocr-invoice-frontend.onrender.com
```

**2. Database Connection Fails:**
- Verify Supabase credentials are correct
- Check if Supabase project is active
- Ensure service role key has proper permissions

**3. Services Can't Talk to Each Other:**
- Frontend `NEXT_PUBLIC_API_URL` must match backend service URL
- Backend `FRONTEND_URL` must match frontend service URL

---

## 📋 **Environment Variables Checklist**

### **Backend Service:**
- [ ] `SUPA_URL` - Your Supabase project URL
- [ ] `SUPA_SERVICE_ROLE_KEY` - Service role key from Supabase
- [ ] `SUPA_ANON_KEY` - Public anon key from Supabase
- [ ] `JWT_SECRET` - Random string for auth tokens
- [ ] `FRONTEND_URL` - Your frontend service URL (for CORS)
- [ ] `ADMIN_USERNAME`, `ADMIN_EMAIL`, `ADMIN_PASSWORD` - Admin login

### **Frontend Service:**
- [ ] `NEXT_PUBLIC_SUPABASE_URL` - Same as SUPA_URL
- [ ] `NEXT_PUBLIC_SUPABASE_ANON_KEY` - Same as SUPA_ANON_KEY  
- [ ] `NEXT_PUBLIC_API_URL` - Your backend service URL

Once all environment variables are configured, your System Health Dashboard will show actual connectivity status and upload/fetch will work properly!