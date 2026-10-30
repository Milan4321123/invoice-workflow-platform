# 🔍 Render Upload/Fetch Issues - Debugging Guide

## 🕵️ **Issue Analysis Based on Code Review**

Your health dashboard shows "GESUND" but upload/fetch doesn't work. After analyzing your code, here are the most likely causes:

### **🔐 Primary Issue: Authentication Problems**

Your upload endpoint requires authentication:
```python
@router.post("/upload")
async def upload_file(
    request: Request,
    file: UploadFile = File(...),
    current_user: Dict[str, Any] = Depends(require_auth)  # ← REQUIRES AUTH
):
```

If users aren't properly authenticated, uploads will fail silently or with authentication errors.

---

## 🧪 **Step-by-Step Debugging**

### **Test 1: Check Authentication Status**

Visit your frontend and open browser **Developer Tools** → **Console**:

```javascript
// Check if user is logged in
console.log('Auth token:', localStorage.getItem('authToken'));
console.log('User data:', localStorage.getItem('authUser'));
```

**Expected Result:** Should show valid token and user data

### **Test 2: Test Login Directly**

Try logging in with your admin credentials:

```bash
# Test with your configured admin credentials
curl -s "https://ocr-invoice-backend.onrender.com/api/auth/login" \
  -X POST \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=YOUR_ADMIN_USERNAME&password=YOUR_ADMIN_PASSWORD"
```

**Expected Result:** Should return access token, not "Incorrect username or password"

### **Test 3: Check Environment Variables**

In your Render backend service, verify these are set:
```bash
ADMIN_USERNAME=admin
ADMIN_EMAIL=admin@yourcompany.com  
ADMIN_PASSWORD=your-secure-password
JWT_SECRET=your-long-random-secret
```

### **Test 4: Test Authenticated Upload**

After getting a valid token:
```bash
# Replace YOUR_TOKEN with actual token from login
curl -s "https://ocr-invoice-backend.onrender.com/api/upload" \
  -X POST \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "file=@test.pdf"
```

**Expected Result:** Should upload successfully, not "Not authenticated"

---

## 🔧 **Most Common Issues & Fixes**

### **Issue 1: Admin Credentials Not Set**

**Problem:** `ADMIN_USERNAME`, `ADMIN_PASSWORD` not configured in Render
**Fix:** Add them in Render Dashboard → Backend Service → Environment

```bash
ADMIN_USERNAME=admin
ADMIN_EMAIL=admin@yourcompany.com
ADMIN_PASSWORD=SecurePassword123!
JWT_SECRET=your-64-character-random-string
```

### **Issue 2: JWT Secret Missing**

**Problem:** Authentication tokens can't be verified without JWT secret
**Fix:** Generate and add JWT_SECRET:

```bash
# Generate a secure JWT secret
openssl rand -base64 64

# Add to Render environment:
JWT_SECRET=the-generated-secret-here
```

### **Issue 3: Frontend Can't Store Auth Token**

**Problem:** Login works but token isn't persisted in localStorage
**Fix:** Check browser console for storage errors or CORS issues

### **Issue 4: Authentication Service Not Initialized**

**Problem:** Auth service fails to create admin user on startup
**Fix:** Check backend logs in Render Dashboard → Logs for auth setup errors

---

## 🎯 **Quick Fix Steps**

### **Step 1: Configure Missing Environment Variables**

In **Render Dashboard** → **ocr-invoice-backend** → **Environment**:

```bash
# Authentication (CRITICAL)
ADMIN_USERNAME=admin
ADMIN_PASSWORD=YourSecurePassword123!
ADMIN_EMAIL=admin@yourcompany.com
JWT_SECRET=your-long-random-jwt-secret

# Database (if not already set)
SUPA_URL=https://your-project.supabase.co
SUPA_SERVICE_ROLE_KEY=your-service-role-key
```

### **Step 2: Restart Backend Service**

1. Go to Render Dashboard → Backend Service
2. Click **Manual Deploy** → **Deploy latest commit**
3. Wait for deployment to complete

### **Step 3: Check Backend Logs**

Look for these messages in logs:
- ✅ `Admin user created: admin`
- ✅ `Database service connected`
- ❌ `Failed to create admin user`
- ❌ `JWT_SECRET not configured`

### **Step 4: Test Login Flow**

1. Visit your frontend URL
2. Try logging in with admin credentials
3. Check browser console for errors
4. Try uploading a file after successful login

---

## 🔍 **Advanced Debugging**

### **Check Network Tab in Browser**

When upload fails, check **Developer Tools** → **Network**:

1. **Authentication request** - Should return 200 with token
2. **Upload request** - Should include `Authorization: Bearer token`
3. **CORS errors** - Should show allowed origins including your frontend URL

### **Common Error Messages**

| Error | Likely Cause | Fix |
|-------|--------------|-----|
| "Not authenticated" | No auth token sent | Login first, check localStorage |
| "Incorrect username or password" | Admin credentials wrong | Check ADMIN_USERNAME/PASSWORD in Render |
| "JWT decode error" | Invalid/expired token | Check JWT_SECRET configuration |
| "Database service not available" | Supabase connection failed | Check SUPA_URL and SUPA_SERVICE_ROLE_KEY |
| "CORS error" | Frontend URL not allowed | Check FRONTEND_URL in backend env |

---

## 📋 **Final Checklist**

- [ ] **ADMIN_USERNAME** and **ADMIN_PASSWORD** set in Render backend
- [ ] **JWT_SECRET** configured (64-character random string)
- [ ] **SUPA_URL** and **SUPA_SERVICE_ROLE_KEY** set correctly
- [ ] **FRONTEND_URL** points to your frontend service URL
- [ ] Backend service restarted after env changes
- [ ] Can successfully login on frontend
- [ ] Auth token visible in browser localStorage
- [ ] Upload works after authentication

The root cause is most likely **missing authentication configuration** in your Render environment variables!