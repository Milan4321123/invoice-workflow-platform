# 🚀 Render Deployment Guide for OCR Invoice Processor

This guide will help you deploy your OCR Invoice Processor to Render.com for production use.

## 📋 Prerequisites

Before deploying to Render, ensure you have:

1. **Supabase Project**: Set up and configured with the database schema
2. **SendGrid Account**: For email notifications  
3. **GitHub Repository**: Your code should be in a GitHub repository
4. **Render Account**: Sign up at https://render.com

## 🏗️ Step 1: Prepare Your Repository

### 1.1 Database Setup
First, set up your Supabase database:

1. Go to your Supabase project dashboard
2. Navigate to SQL Editor
3. Run the complete SQL setup from [`COMPLETE_SUPABASE_SETUP.sql`](../../COMPLETE_SUPABASE_SETUP.sql)
4. Create a storage bucket named `invoices` in Supabase Storage

### 1.2 Environment Variables
You'll need these environment variables for Render. Get them ready:

**From Supabase:**
- `SUPA_URL`: Your project URL (https://xxx.supabase.co)
- `SUPA_KEY`: Service role key (from API settings)
- `SUPA_SERVICE_ROLE_KEY`: Same as above
- `SUPA_ANON_KEY`: Anon public key (from API settings)

**From SendGrid:**
- `SENDGRID_API_KEY`: Your SendGrid API key (starts with SG.)

**Security (generate these):**
- `JWT_SECRET`: Generate with `openssl rand -base64 64`
- `ADMIN_PASSWORD`: Strong password for admin user

**Company Settings:**
- `ADMIN_USERNAME`: admin
- `ADMIN_EMAIL`: Your admin email
- `ADMIN_FULL_NAME`: Administrator Full Name
- `COMPANY_NAME`: Your Company Name
- `COMPANY_EMAIL`: Your company email
- `FROM_EMAIL`: Email for notifications (e.g., noreply@yourcompany.com)
- `FROM_NAME`: Display name for emails

## 🚀 Step 2: Deploy Backend Service

### 2.1 Create Backend Service
1. Go to Render Dashboard
2. Click "New" → "Web Service"
3. Connect your GitHub repository
4. Configure the service:

**Basic Settings:**
- **Name**: `ocr-invoice-backend` (or your preferred name)
- **Runtime**: Python 3
- **Build Command**: `pip install -r requirements_render.txt`
- **Start Command**: `python render_start.py`
- **Root Directory**: `backend`

**Advanced Settings:**
- **Plan**: Starter (or higher based on your needs)
- **Python Version**: 3.9.18
- **Health Check Path**: `/health`

### 2.2 Set Backend Environment Variables
In the Render dashboard for your backend service, add these environment variables:

```
NODE_ENV=production
SUPA_URL=https://your-project.supabase.co
SUPA_KEY=your-service-role-key
SUPA_SERVICE_ROLE_KEY=your-service-role-key
SUPA_ANON_KEY=your-anon-key
SENDGRID_API_KEY=SG.your-sendgrid-api-key
FROM_EMAIL=noreply@yourcompany.com
FROM_NAME=Your Company Name
JWT_SECRET=your-generated-jwt-secret
ADMIN_USERNAME=admin
ADMIN_EMAIL=admin@yourcompany.com
ADMIN_PASSWORD=your-secure-admin-password
ADMIN_FULL_NAME=System Administrator
COMPANY_NAME=Your Company Name
COMPANY_EMAIL=info@yourcompany.com
USE_MOCK_STORAGE=true
USE_MOCK_OCR=true
ENABLE_EMAIL_NOTIFICATIONS=true
```

### 2.3 Deploy Backend
1. Click "Create Web Service"
2. Wait for deployment to complete
3. Note your backend URL (e.g., `https://ocr-invoice-backend.onrender.com`)

## 🎨 Step 3: Deploy Frontend Service

### 3.1 Create Frontend Service
1. Go to Render Dashboard
2. Click "New" → "Web Service"  
3. Connect the same GitHub repository
4. Configure the service:

**Basic Settings:**
- **Name**: `ocr-invoice-frontend` (or your preferred name)
- **Runtime**: Node
- **Build Command**: `npm ci && npm run build`
- **Start Command**: `npm run start`
- **Root Directory**: `frontend`

**Advanced Settings:**
- **Plan**: Starter (or higher based on your needs)
- **Node Version**: 18.19.0
- **Health Check Path**: `/`

### 3.2 Set Frontend Environment Variables
In the Render dashboard for your frontend service, add these environment variables:

```
NODE_ENV=production
NEXT_PUBLIC_SUPABASE_URL=https://your-project.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=your-anon-key
NEXT_PUBLIC_API_URL=https://your-backend-service-name.onrender.com
```

**Important**: Replace `your-backend-service-name` with the actual name of your backend service from Step 2.3.

### 3.3 Deploy Frontend
1. Click "Create Web Service"
2. Wait for deployment to complete
3. Your app will be available at your frontend URL

## 🔧 Step 4: Post-Deployment Configuration

### 4.1 Update CORS Settings
After both services are deployed, you may need to update the backend's CORS settings:

1. Add your frontend URL to the `ADDITIONAL_CORS_ORIGINS` environment variable in the backend service
2. Or add `FRONTEND_URL` environment variable with your frontend URL

### 4.2 Test the Deployment
1. Visit your frontend URL
2. Try logging in with your admin credentials
3. Check the system health at: `https://your-backend-url.onrender.com/system-health`
4. Upload a test invoice to verify everything works

## 🐛 Troubleshooting

### Common Issues:

**Backend won't start:**
- Check environment variables are set correctly
- Verify Supabase credentials in the backend logs
- Ensure `requirements_render.txt` is being used (not `requirements.txt`)

**Frontend can't connect to backend:**
- Verify `NEXT_PUBLIC_API_URL` points to your backend service URL
- Check CORS configuration in backend logs
- Ensure both services are deployed and running

**Database connection issues:**
- Verify Supabase URL and keys are correct
- Check if database schema was set up properly
- Review backend startup logs for database initialization errors

**Email notifications not working:**
- Verify SendGrid API key is correct
- Check `FROM_EMAIL` is verified in SendGrid
- Review email service logs in backend

### Checking Logs:
- Go to your service in Render dashboard
- Click on "Logs" tab
- Look for error messages during startup

## 📊 Monitoring

After deployment, monitor your services:

1. **Backend Health**: `https://your-backend-url.onrender.com/system-health`
2. **Frontend Health**: Visit your frontend URL
3. **Render Dashboard**: Check service status and logs
4. **Database**: Monitor via Supabase dashboard

## 🔄 Updates and Maintenance

To update your deployment:
1. Push changes to your GitHub repository
2. Render will automatically redeploy both services
3. Monitor the deployment logs for any issues

## 💡 Tips for Success

1. **Use Render's Free Tier**: Both services can run on free tier for testing
2. **Environment Variables**: Double-check all environment variables are set correctly
3. **Health Checks**: Use the provided health endpoints to monitor service status
4. **Logs**: Always check logs if something isn't working
5. **Database**: Ensure your Supabase project is properly configured before deployment

---

**Need Help?** 
- Check the troubleshooting section above
- Review Render's documentation at https://render.com/docs
- Check service logs in the Render dashboard
