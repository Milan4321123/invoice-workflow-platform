# 🔧 Database Configuration Fix Guide

## 🚨 **Problem Identified**

Your System Health Dashboard shows "GESUND" but upload/fetching doesn't work because:

### **The Issue:**
- **Health checks are too basic** - they only verify environment variables exist
- **Database credentials are placeholder values** - not real Supabase connection
- **Backend returns:** `"detail": "Database service not available"`

### **Why Health Checks Pass:**
```typescript
// Health check only tests if env vars exist:
env_config["SUPABASE_URL"] = "configured" if url_configured else "missing"
env_config["SUPABASE_KEY"] = "configured" if key_configured else "missing"
```

But doesn't test if they actually **connect to a working database**.

---

## ✅ **Solution Steps**

### **1. Set Up Real Supabase Database:**

**Option A: Use Existing Supabase Project**
```bash
# If you have Supabase account:
1. Go to https://supabase.com/dashboard
2. Open your project
3. Go to Settings > API
4. Copy your Project URL and Service Role Key
```

**Option B: Create New Supabase Project** 
```bash
1. Go to https://supabase.com
2. Sign up/login
3. Create new project
4. Wait for setup to complete (~2 minutes)
5. Copy credentials from Settings > API
```

### **2. Update Your .env File:**

Replace these placeholder values in `.env`:
```bash
# REPLACE THESE:
SUPA_URL=https://your-project.supabase.co
SUPA_SERVICE_ROLE_KEY=your-service-role-key-here

# WITH REAL VALUES:
SUPA_URL=https://abcdefghijklmnop.supabase.co
SUPA_SERVICE_ROLE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

### **3. Create Database Tables:**

Run this SQL in your Supabase SQL Editor:
```sql
-- Create invoices table
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

-- Create RLS policies (if needed)
ALTER TABLE invoices_clean ENABLE ROW LEVEL SECURITY;

-- Allow all operations for service role
CREATE POLICY "Service role can do everything" ON invoices_clean
FOR ALL USING (true);
```

### **4. Restart Your Application:**

```bash
# Stop current containers
docker-compose down

# Start with new configuration
docker-compose up --build -d
```

---

## 🧪 **Test the Fix:**

### **Check Database Connection:**
```bash
curl -s "http://localhost:8000/api/invoices"
```

**Expected:** JSON response with invoices array (not "Database service not available")

### **Check System Health:**
Visit: http://localhost:3000/health

**Expected:** Database should show "Connected" with actual response times

---

## 🔍 **Advanced Debugging:**

### **View Backend Logs:**
```bash
docker-compose logs backend
```

Look for these messages:
- ✅ `Database service connected to: https://...`
- ❌ `Database credentials missing. Running in offline mode.`

### **Test Supabase Connection Directly:**
```bash
# Install supabase CLI (optional)
npm install -g @supabase/cli

# Test connection
supabase projects list
```

---

## 📈 **Better Health Checks**

After fixing, consider adding **functional health checks** that test actual operations:

```python
# Instead of just checking config exists:
async def database_functional_health():
    try:
        # Actually query the database
        result = db_service.get_invoices(limit=1)
        return {"status": "healthy" if result.get("success") else "error"}
    except Exception as e:
        return {"status": "error", "details": str(e)}
```

This will prevent false positives where configuration exists but database is unreachable.

---

## 🎯 **Summary:**

Your health dashboard is **misleadingly optimistic** - it only checks if environment variables are set, not if they work. Configure real Supabase credentials to fix upload/fetch functionality.