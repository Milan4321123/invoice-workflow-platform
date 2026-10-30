# 🏢 Company Setup Guide - OCR Invoice Processor

## 📋 Complete Setup Instructions for IT Administrators

This guide provides step-by-step instructions for setting up the OCR Invoice Processor in your company environment.

---

## 🎯 Overview

### **What This System Provides**
- Complete invoice processing workflow
- Automated OCR data extraction
- Email notifications and approvals
- Multi-user dashboard
- Docker-based deployment (no complex setup)

### **Deployment Time**
- **Setup Time**: 15-30 minutes
- **First Use**: Immediate after setup
- **User Training**: 5 minutes per user

---

## 🚀 Quick Deployment (Recommended)

### **Step 1: Clone Repository**
```bash
# Clone to company server or local machine
git clone https://github.com/YOUR-COMPANY-ORG/ocr-invoice-processor.git
cd ocr-invoice-processor
```

### **Step 2: Install Docker Desktop**
- Download: https://www.docker.com/products/docker-desktop
- Install on each machine that will run the system
- Start Docker Desktop (ensure green icon in system tray)

### **Step 3: Configure Environment**
```bash
# Copy configuration template
cp environment.template .env

# Edit .env with company-specific settings
nano .env  # or use any text editor
```

### **Step 4: Start Application**
```bash
# Windows
start-company.bat

# Mac/Linux
./start-company.sh
```

### **Step 5: Verify Installation**
1. Open http://localhost:3000
2. Login with admin credentials from `.env`
3. Upload test invoice
4. Verify all functions work

---

## ⚙️ Detailed Configuration

### **Required Services Setup**

#### **1. Database (Supabase)**
1. Go to https://supabase.com
2. Create new project
3. Get connection details:
   - Project URL
   - Service Role Key
   - Anon Key
4. Add to `.env` file

#### **2. Email Service (SendGrid)**  
1. Sign up at https://sendgrid.com
2. Create API key with full access
3. Verify sender email domain
4. Add API key to `.env` file

#### **3. Company Information**
Update `.env` with:
- Company name and contact info
- Admin user credentials
- Email addresses for notifications

### **Environment Configuration Example**
```bash
# Database (Supabase)
SUPA_URL=https://your-project-abc123.supabase.co
SUPA_KEY=eyJ0eXAiOiJKV1QiLCJhbGciOiJI...
SUPA_SERVICE_ROLE_KEY=eyJ0eXAiOiJKV1QiLCJhbGciOiJI...
SUPA_ANON_KEY=eyJ0eXAiOiJKV1QiLCJhbGciOiJIUz...

NEXT_PUBLIC_SUPABASE_URL=https://your-project-abc123.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJ0eXAiOiJKV1QiLCJhbGciOiJIUz...

# Email (SendGrid)
SENDGRID_API_KEY=SG.abcdef123456789...
FROM_EMAIL=noreply@yourcompany.com
FROM_NAME=Invoice System

# Security (generate with: openssl rand -base64 64)
JWT_SECRET=your-long-secure-jwt-secret-key-here

# Company Admin
ADMIN_USERNAME=admin
ADMIN_EMAIL=admin@yourcompany.com
ADMIN_PASSWORD=your-secure-admin-password-123
ADMIN_FULL_NAME=System Administrator

# Company Info
COMPANY_NAME=Your Company GmbH
COMPANY_EMAIL=info@yourcompany.com
```

---

## 🌐 Production Deployment Options

### **Option 1: Single Machine Deployment**
```bash
# Install on one company computer
# Access via http://localhost:3000
# Good for: Small teams, testing
```

### **Option 2: Server Deployment**
```bash
# Install on company server
# Access via http://server-ip:3000
# Configure firewall for port access
# Good for: Multiple users, always-on access
```

### **Option 3: Cloud Deployment**
```bash
# Deploy to AWS, Google Cloud, or Azure
# Use company cloud account
# Configure domain name and SSL
# Good for: Remote work, high availability
```

---

## 👥 User Management

### **Default Users**
- **Admin**: Full system access, user management
- **Editor**: Can process invoices, limited admin access
- **Viewer**: Read-only access to invoices

### **Adding New Users**
1. Login as admin
2. Go to user management section
3. Add user with appropriate role
4. User receives email with login instructions

### **User Roles & Permissions**
| Role | Upload | Edit | Approve | Admin | 
|------|--------|------|---------|-------|
| Admin | ✅ | ✅ | ✅ | ✅ |
| Editor | ✅ | ✅ | ❌ | ❌ |
| Viewer | ❌ | ❌ | ❌ | ❌ |

---

## 🔒 Security Considerations

### **Data Protection**
- All sensitive data in `.env` file (not in code)
- Database connections encrypted (Supabase)
- JWT tokens for secure authentication
- Role-based access control

### **Network Security**
- Run behind company firewall
- Use HTTPS in production (configure reverse proxy)
- Regular Docker image updates
- Monitor access logs

### **Backup Strategy**
- **Database**: Automatic Supabase backups
- **Configuration**: Backup `.env` file securely
- **Code**: Stored in company GitHub repository

---

## 📊 Monitoring & Maintenance

### **Health Monitoring**
```bash
# Check application health
curl http://localhost:8000/health

# View application logs
docker-compose logs -f

# Check container status
docker-compose ps
```

### **Regular Maintenance**
- **Weekly**: Check logs for errors
- **Monthly**: Update Docker images
- **Quarterly**: Review user access
- **Annually**: Update dependencies

### **Performance Tuning**
- Monitor resource usage (Docker stats)
- Scale containers if needed
- Optimize database queries
- Configure log rotation

---

## 🆘 Troubleshooting Guide

### **Installation Issues**

**Docker not starting**
```bash
# Check Docker Desktop is running
docker info

# If not running, start Docker Desktop
# Wait for green icon before continuing
```

**Port conflicts**
```bash
# Check what's using ports 3000, 8000
lsof -i :3000
lsof -i :8000

# Stop conflicting services or change ports in docker-compose.yml
```

### **Runtime Issues**

**Database connection errors**
- Verify Supabase URL and keys in `.env`
- Check internet connection
- Confirm Supabase project is active

**Email not sending**
- Verify SendGrid API key
- Check sender email is verified
- Confirm SendGrid account is active

**Login not working**
- Check admin credentials in `.env`
- Verify JWT_SECRET is set
- Clear browser cache and cookies

### **Performance Issues**

**Slow response times**
- Check Docker resource allocation
- Monitor database performance
- Review application logs for bottlenecks

**High resource usage**
- Increase Docker memory limits
- Optimize image sizes
- Consider container scaling

---

## 📈 Scaling & Growth

### **Adding More Users**
- No additional setup required
- System supports unlimited users
- Monitor database and server resources

### **Multiple Locations**
- Deploy separate instances per location
- Use central database if needed
- Configure VPN for secure access

### **Advanced Features**
- Enable real OCR (Google Cloud setup)
- Configure custom email templates
- Add company-specific workflows
- Integrate with existing systems

---

## 📞 Support & Resources

### **Internal Support**
1. Check this guide first
2. Review application logs
3. Contact IT administrator
4. Escalate to system developer if needed

### **External Resources**
- **Docker Documentation**: https://docs.docker.com
- **Supabase Documentation**: https://supabase.com/docs
- **SendGrid Documentation**: https://docs.sendgrid.com

### **Getting Help**
- **System Logs**: `docker-compose logs -f`
- **Health Check**: http://localhost:8000/health
- **Database Status**: Check Supabase dashboard
- **Email Status**: Check SendGrid dashboard

---

## ✅ Deployment Checklist

### **Pre-Deployment**
- [ ] Docker Desktop installed and running
- [ ] Repository cloned to target machine
- [ ] Supabase project created and configured
- [ ] SendGrid account set up with API key
- [ ] Firewall rules configured (if needed)

### **Configuration**
- [ ] `.env` file created from template
- [ ] All database settings configured
- [ ] Email service settings configured
- [ ] Company information updated
- [ ] Admin credentials set (secure password)
- [ ] JWT secret generated

### **Testing**
- [ ] Application starts successfully
- [ ] Can access http://localhost:3000
- [ ] Admin login works
- [ ] Can upload test invoice
- [ ] Email notifications work
- [ ] All core features tested

### **Production Ready**
- [ ] User accounts created
- [ ] Staff trained on system use
- [ ] Backup procedures documented
- [ ] Monitoring set up
- [ ] Support procedures established

---

**System is ready for company-wide deployment!** 🎉

All technical complexity is handled by Docker - your team just needs to run the startup script and begin processing invoices immediately.