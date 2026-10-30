# OCR Invoice Processor - Complete System Architecture & Sequence Diagrams

## 🎯 System Overview

The OCR Invoice Processor is a comprehensive invoice management system built with:
- **Frontend**: Next.js 15.3.4 with TypeScript and Tailwind CSS
- **Backend**: FastAPI (Python) with Supabase database
- **Storage**: Supabase Storage buckets
- **Authentication**: JWT-based auth system
- **Deployment**: Docker containers on Render cloud platform

---

## 🔄 Main Application Flow Sequence

```mermaid
sequenceDiagram
    participant U as User
    participant FE as Frontend (Next.js)
    participant BE as Backend (FastAPI)
    participant DB as Database (Supabase)
    participant ST as Storage (Supabase)

    Note over U,ST: 1. APPLICATION STARTUP FLOW
    U->>FE: Access http://localhost:3000
    FE->>FE: Check localStorage for auth token
    alt Token exists and valid
        FE->>U: Redirect to /dashboard
    else No token or invalid
        FE->>U: Redirect to /login
    end

    Note over U,ST: 2. AUTHENTICATION FLOW
    U->>FE: Enter credentials on /login
    FE->>BE: POST /api/auth/login (username, password)
    BE->>DB: Query user credentials
    DB-->>BE: Return user data
    BE->>BE: Verify password & generate JWT
    BE-->>FE: Return access_token + user info
    FE->>FE: Store token in localStorage
    FE->>U: Redirect to /dashboard

    Note over U,ST: 3. DASHBOARD LOADING
    FE->>BE: GET /invoices (with auth header)
    BE->>DB: SELECT * FROM invoices_clean
    DB-->>BE: Return invoice list
    BE-->>FE: JSON response with invoices
    FE->>U: Display dashboard with invoice cards
```

---

## 📤 File Upload Sequence Diagram

```mermaid
sequenceDiagram
    participant U as User
    participant FE as Frontend
    participant UE as Upload Endpoint
    participant US as Upload Service
    participant DB as Database
    participant ST as Supabase Storage

    Note over U,ST: DRAG & DROP UPLOAD FLOW
    U->>FE: Drag PDF file to upload zone
    FE->>FE: Validate file (PDF only, size limit)
    FE->>FE: Sanitize filename for security
    
    FE->>UE: POST /upload (multipart/form-data)
    Note right of UE: Rate limited: 10/minute per IP
    
    UE->>UE: Validate content-type = "application/pdf"
    UE->>UE: Check filename pattern (YYYYMMDD_ID_VENDOR_TYPE.pdf)
    UE->>UE: Read file content & validate not empty
    
    UE->>US: Call upload_service.upload_file(FileData)
    
    Note over US: UPLOAD SERVICE ORCHESTRATION
    US->>US: 1. Sanitize filename (XSS prevention)
    US->>US: 2. Validate file (size, type, format)
    US->>US: 3. Generate storage path based on source
    
    US->>ST: 4. Upload to bucket (invoices/drag_drop/)
    ST-->>US: Return public URL
    
    US->>US: 5. Generate UUID for invoice
    US->>DB: 6. Create invoice record with metadata
    DB-->>US: Confirm record created
    
    US-->>UE: Return UploadResult (success + invoice_id)
    UE-->>FE: HTTP 200 + upload details
    FE->>U: Show success notification
    FE->>FE: Refresh dashboard to show new invoice
```

---

## 🔍 Invoice Editor Workflow

```mermaid
sequenceDiagram
    participant U as User
    participant FE as Frontend
    participant ED as Editor Dashboard
    participant BE as Backend API
    participant DB as Database
    participant PDF as PDF Viewer

    Note over U,PDF: INVOICE EDITING SESSION
    U->>FE: Click "Edit" on invoice card
    FE->>ED: Navigate to /editor/[invoiceId]
    
    ED->>BE: GET /api/invoices/{id}/editor
    BE->>DB: Query invoice with extracted fields
    DB-->>BE: Return invoice data + OCR fields
    BE-->>ED: JSON with pdfUrl + form fields
    
    par Load PDF Viewer
        ED->>PDF: Initialize PDF viewer with URL
        PDF->>PDF: Load PDF document
        PDF-->>ED: PDF loaded & ready
    and Load Form Fields
        ED->>ED: Initialize form with OCR data
        ED-->>U: Show split-screen: PDF + Form
    end
    
    Note over U,PDF: EDITING INTERACTION
    U->>ED: Modify invoice fields (vendor, amount, etc.)
    ED->>ED: Mark hasUnsavedChanges = true
    
    U->>ED: Click "Save Progress"
    ED->>BE: PUT /api/invoices/{id}/editor (form data)
    BE->>DB: UPDATE invoices_clean SET fields = ?
    DB-->>BE: Confirm update
    BE-->>ED: HTTP 200 success
    ED->>U: Show "Changes saved" notification
    
    U->>ED: Click "Complete & Send for Approval"
    ED->>BE: POST /api/invoices/{id}/complete
    BE->>DB: UPDATE status = 'pending_approval'
    BE->>BE: Trigger email workflow
    BE-->>ED: HTTP 200 + workflow started
    ED->>U: Show completion success + redirect
```

---

## 📧 Email Workflow & Approval Process

```mermaid
sequenceDiagram
    participant U as User
    participant BE as Backend
    participant ES as Email Service
    participant DB as Database
    participant BL as Bauleiter
    participant EM as Email Provider

    Note over U,EM: APPROVAL WORKFLOW SEQUENCE
    U->>BE: POST /api/invoices/{id}/complete
    BE->>DB: UPDATE status = 'pending_approval'
    
    BE->>ES: send_bauleiter_approval_email(invoice_data)
    ES->>DB: Query invoice details + approval token
    ES->>ES: Generate approval email HTML
    ES->>EM: Send email via SendGrid API
    EM-->>BL: Deliver approval email
    
    Note over BL,EM: BAULEITER APPROVAL FLOW
    BL->>BE: Click email link /approval/{token}
    BE->>DB: Query invoice by approval_token
    BE->>BE: Render approval page with invoice details
    
    alt Approve Invoice
        BL->>BE: POST /api/approval/{token}/approve
        BE->>DB: UPDATE status = 'approved'
        BE->>ES: send_approval_confirmation_email()
        ES->>EM: Notify original submitter
    else Reject Invoice
        BL->>BE: POST /api/approval/{token}/reject (reason)
        BE->>DB: UPDATE status = 'rejected', rejection_reason
        BE->>ES: send_rejection_notification_email()
        ES->>EM: Notify original submitter with reason
    end
    
    BE-->>BL: Show success page
```

---

## 🏢 Multi-Source Upload Architecture

```mermaid
sequenceDiagram
    participant FW as Folder Watcher
    participant US as Upload Service
    participant DB as Database
    participant ST as Storage
    participant DD as Drag & Drop UI

    Note over FW,DD: MULTIPLE UPLOAD SOURCES
    
    par Folder Watcher Upload
        FW->>FW: Monitor /watched-folder/ directory
        FW->>FW: Detect new PDF file
        FW->>US: upload_file(source=FOLDER_WATCHER)
        US->>ST: Store in folderwatcher/ bucket
        US->>DB: INSERT with upload_source = 'folder-watcher'
    
    and Manual Upload
        DD->>DD: User drops file
        DD->>US: upload_file(source=DRAG_DROP)  
        US->>ST: Store in invoices/ bucket
        US->>DB: INSERT with upload_source = 'drag-drop'
    
    and Bulk Import
        DD->>DD: User selects multiple files
        loop For each file
            DD->>US: upload_file(source=MANUAL)
            US->>ST: Store in manual-invoices/ bucket
            US->>DB: INSERT with upload_source = 'manual'
        end
    end
    
    Note over FW,DD: UNIFIED PROCESSING
    US-->>DB: All sources use same invoice schema
    DB->>DB: Trigger common processing pipeline
```

---

## 🔐 Authentication & Security Flow

```mermaid
sequenceDiagram
    participant FE as Frontend
    participant MW as Auth Middleware
    participant AS as Auth Service
    participant DB as Database
    participant JWT as JWT Service

    Note over FE,JWT: AUTHENTICATION SECURITY
    FE->>MW: API Request with Authorization header
    MW->>MW: Extract Bearer token
    MW->>JWT: Verify token signature
    
    alt Valid Token
        JWT->>AS: Extract username from payload
        AS->>DB: Query user by username
        DB-->>AS: Return user data
        AS-->>MW: User object
        MW->>MW: Attach user to request context
        MW->>FE: Continue to endpoint handler
    else Invalid Token
        JWT-->>MW: Token verification failed
        MW-->>FE: HTTP 401 Unauthorized
    end
    
    Note over FE,JWT: TOKEN REFRESH FLOW
    FE->>FE: Check token expiry before requests
    alt Token expired
        FE->>AS: POST /auth/refresh (refresh_token)
        AS->>JWT: Generate new access_token
        JWT-->>AS: New token with extended expiry
        AS-->>FE: New access_token
        FE->>FE: Update localStorage
    end
```

---

## 💾 Database Operations Patterns

```mermaid
sequenceDiagram
    participant API as API Endpoint
    participant DS as Database Service
    participant SB as Supabase Client
    participant PG as PostgreSQL

    Note over API,PG: DATABASE SERVICE LAYER PATTERN
    API->>DS: Call database method
    DS->>DS: Validate input parameters
    DS->>DS: Build query with exact schema fields
    
    DS->>SB: Execute Supabase query
    SB->>PG: SQL query to invoices_clean table
    PG-->>SB: Result set
    SB-->>DS: Parsed response
    
    DS->>DS: Process & validate response
    DS->>DS: Handle errors gracefully
    DS-->>API: Standardized result format
    
    Note over API,PG: EXAMPLE OPERATIONS
    par Get All Invoices
        DS->>SB: .select('*').limit(1000)
        SB->>PG: SELECT * FROM invoices_clean LIMIT 1000
    and Create Invoice
        DS->>SB: .insert(invoice_data)
        SB->>PG: INSERT INTO invoices_clean (...)
    and Update Invoice
        DS->>SB: .update(changes).eq('id', invoice_id)
        SB->>PG: UPDATE invoices_clean SET ... WHERE id = ?
    end
```

---

## 🎛️ System Health & Monitoring

```mermaid
sequenceDiagram
    participant UI as Health Dashboard
    participant BE as Backend
    participant DB as Database
    participant ST as Storage
    participant ES as Email Service

    Note over UI,ES: HEALTH CHECK SEQUENCE
    UI->>BE: GET /health (periodic check)
    
    par Database Check
        BE->>DB: Test connection & query
        DB-->>BE: Response time & status
    and Storage Check  
        BE->>ST: Test bucket access
        ST-->>BE: Storage availability
    and Email Check
        BE->>ES: Verify email service config
        ES-->>BE: Service status
    end
    
    BE->>BE: Aggregate health metrics
    BE-->>UI: Combined health status
    
    alt All Services Healthy
        UI->>UI: Show green status indicators
    else Degraded Performance
        UI->>UI: Show yellow warnings
    else Critical Issues
        UI->>UI: Show red alerts + details
    end
```

---

## 🚀 Deployment & Container Orchestration

```mermaid
sequenceDiagram
    participant DEV as Developer
    participant GIT as Git Repository
    participant REN as Render Platform
    participant DOC as Docker Build
    participant CON as Containers

    Note over DEV,CON: DEPLOYMENT PIPELINE
    DEV->>GIT: git push origin main
    GIT->>REN: Webhook triggers deploy
    
    par Frontend Build
        REN->>DOC: Build frontend/Dockerfile
        DOC->>DOC: npm install & npm run build
        DOC->>CON: Create frontend container
    and Backend Build
        REN->>DOC: Build backend/Dockerfile
        DOC->>DOC: pip install requirements
        DOC->>CON: Create backend container
    end
    
    REN->>CON: Deploy containers with env vars
    CON->>CON: Start services on assigned ports
    
    Note over DEV,CON: SERVICE COMMUNICATION
    CON->>CON: Frontend: Port 10000 (Render assigned)
    CON->>CON: Backend: Port 8000 (Fixed)
    CON->>CON: Configure CORS for cross-origin requests
    
    REN-->>DEV: Deployment success notification
    DEV->>REN: Access live application URLs
```

---

## 🔄 Error Handling & Recovery Patterns

```mermaid
sequenceDiagram
    participant FE as Frontend
    participant BE as Backend
    participant DB as Database
    participant U as User

    Note over FE,U: ERROR HANDLING STRATEGY
    FE->>BE: API Request
    
    alt Network Error
        BE-->>FE: Connection timeout
        FE->>FE: Retry with exponential backoff
        FE->>U: Show "Connection issues, retrying..."
    else Server Error (5xx)
        BE-->>FE: HTTP 500 Internal Server Error
        FE->>FE: Log error details
        FE->>U: Show "Server error, please try again"
    else Database Error
        BE->>DB: Query operation
        DB-->>BE: Connection failed
        BE->>BE: Log error + fallback behavior
        BE-->>FE: HTTP 503 Service Unavailable
        FE->>U: Show "Database temporarily unavailable"
    else Validation Error
        BE-->>FE: HTTP 400 Bad Request + details
        FE->>FE: Parse validation errors
        FE->>U: Show field-specific error messages
    end
    
    Note over FE,U: RECOVERY ACTIONS
    U->>FE: User clicks "Retry" button
    FE->>FE: Clear error state
    FE->>BE: Repeat original request
```

---

## 🎯 Key Architectural Principles

### 1. **Separation of Concerns**
- Frontend handles UI/UX and user interactions
- Backend manages business logic and data operations
- Database layer handles persistence and queries

### 2. **Security by Design**
- JWT-based authentication with token validation
- Input sanitization and validation at all layers
- CORS configuration for cross-origin security
- File upload restrictions and path traversal protection

### 3. **Error Resilience**
- Graceful degradation when services are unavailable
- Retry mechanisms with exponential backoff
- User-friendly error messages with actionable guidance

### 4. **Scalability Patterns**
- Containerized microservices architecture
- Database connection pooling and optimization
- File storage in cloud buckets with CDN delivery
- Rate limiting to prevent abuse

### 5. **Monitoring & Observability**
- Structured logging throughout the application
- Health check endpoints for service monitoring
- Performance metrics and error tracking

This comprehensive sequence diagram architecture shows how every piece of your OCR Invoice Processor system works together, from user authentication to file processing, database operations, and deployment workflows.